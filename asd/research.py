"""Recherche-Agent: Suchplanung (LLM) -> Abruf (Code: arXiv, Europe PMC) -> Sichtung (LLM, gebündelt) ->
Extraktion mit wörtlichen Zitaten (LLM) -> Zitat-Prüfer (Code) -> Leck-Filter (Code) -> Wissensstand + Hypothesen.

Grundsätze aus research/evidence.md: Jede Aussage trägt ihre Herkunft (Kosmos 2025); erfundene Zitate sind der
häufigste Fehler von LLM-Recherche (Walters & Wilder 2023: 18-55 %), deshalb wird jedes Zitat per Code im
Original-Abstract gesucht. Was nicht gefunden wird, fliegt raus oder wird als UNVERIFIED markiert.

  python -m asd.research buchwald     # Literatur-Hypothesen als GP-Prior für die Buchwald-Hartwig-Domäne
  python -m asd.research lattice      # Wissensstand für die Gitter-Domäne
"""
import argparse, hashlib, json, os, re, time, unicodedata, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from .llm import ask_json

KB = "research/kb"
UA = {"User-Agent": "hacknation-ai-lab/0.1 (research agent)"}

TOPICS = {
    "buchwald": {
        "ziel": ("Welche Liganden, Basen, Arylhalogenide und Additive erhöhen oder senken die Ausbeute Pd-katalysierter "
                 "Buchwald-Hartwig-Aminierungen von Arylhalogeniden mit Anilinen (z. B. p-Toluidin) unter milden Bedingungen "
                 "mit organischen Basen (BTMG, MTBD, Phosphazene wie P2Et) und Biarylphosphin-Liganden (XPhos, t-BuXPhos, "
                 "t-BuBrettPhos, AdBrettPhos)? Welche Heteroaromaten (z. B. Isoxazole, Pyridine) vergiften den Katalysator?"),
        # Leck-Schutz: das Paper zum Testdatensatz und alle Arbeiten, die ihn auswerten, sind ausgeschlossen
        "sperre": ["ahneman", "rxnpredict", "yield prediction", "predicting reaction performance", "machine learning",
                   "random forest", "neural network", "high-throughput experimentation data", "dataset", "doyle"],
        "faktoren": ["ligand", "base", "aryl_halide", "additive"],
    },
    "lattice": {
        "ziel": ("Welche Bravais-Gitter minimieren Gitterenergien (Epstein-Zeta, Riesz-, Lennard-Jones-, Dreikörper- und "
                 "Mehrkörper-Energien) in 2, 3 und 4 Dimensionen; welche Phasenübergänge zwischen optimalen Gittern sind "
                 "bekannt; welche offenen Vermutungen gibt es (z. B. Sarnak-Strömbergsson, Kristallisationsvermutung)?"),
        "sperre": ["suleman"],          # Antwortschlüssel des Benchmarks bleibt verdeckt
        "faktoren": [],
    },
}


def _get(url, timeout=30, retries=4):
    """HTTP GET mit Backoff bei 429/503 (öffentliche APIs drosseln geteilte IPs)."""
    import urllib.error
    for j in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r: return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or j == retries: raise
            time.sleep(3 * 2 ** j)


def search_arxiv(q, n=25):
    terms = " AND ".join(f"all:{w}" for w in re.findall(r"[\w\-]+", q) if len(w) > 2)        # alle Wörter müssen vorkommen
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": terms, "max_results": n, "sortBy": "relevance"})
    ns = {"a": "http://www.w3.org/2005/Atom"}; out = []
    for e in ET.fromstring(_get(url)).findall("a:entry", ns):
        out.append({"id": "arXiv:" + e.find("a:id", ns).text.rsplit("/", 1)[-1], "titel": " ".join(e.find("a:title", ns).text.split()),
                    "abstract": " ".join(e.find("a:summary", ns).text.split()), "jahr": e.find("a:published", ns).text[:4],
                    "autoren": ", ".join(a.find("a:name", ns).text for a in e.findall("a:author", ns)), "url": e.find("a:id", ns).text})
    return out


def search_europepmc(q, n=25):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": f"{q} AND HAS_ABSTRACT:y", "format": "json", "pageSize": n, "resultType": "core"})
    out = []
    for r in json.loads(_get(url)).get("resultList", {}).get("result", []):
        ab = re.sub(r"<[^>]+>", " ", r.get("abstractText", "")); ab = " ".join(ab.split())
        if not ab: continue
        doi = r.get("doi"); out.append({"id": f"doi:{doi}" if doi else f"pmid:{r.get('pmid', r.get('id'))}", "titel": " ".join(r.get("title", "").split()),
                                        "abstract": ab, "jahr": str(r.get("pubYear", "")), "autoren": r.get("authorString", ""),
                                        "url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}"})
    return out


def _pmap(fn, items, workers=6):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex: return list(ex.map(fn, items))


def _crossref_doc(m):
    ab = re.sub(r"<[^>]+>", " ", m.get("abstract", "") or ""); ab = " ".join(ab.split())
    title = " ".join((m.get("title") or [""])[0].split())
    year = str(((m.get("issued") or {}).get("date-parts") or [[""]])[0][0])
    aut = ", ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (m.get("author") or [])[:8])
    return {"id": f"doi:{m['DOI']}", "titel": title, "abstract": ab, "jahr": year, "autoren": aut, "url": f"https://doi.org/{m['DOI']}",
            "journal": " ".join((m.get("container-title") or [""])[0].split()), "volume": m.get("volume", ""), "seiten": m.get("page", ""),
            "quelle_api": "crossref", "refs": [r["DOI"] for r in (m.get("reference") or []) if r.get("DOI")]}


def search_crossref(q, n=25):
    """Crossref: Zeitschriftenartikel mit DOI (Abstract oft vorhanden, sonst nur Metadaten). Der DOI ist der Tool-Beleg."""
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": q, "rows": n})
    return [_crossref_doc(m) for m in json.loads(_get(url))["message"]["items"] if m.get("title")]


def search_inspire(q, n=25):
    """INSPIRE-HEP (hep-th, hep-ph, hep-lat, gr-qc, Teile von cond-mat/math-ph): Abstracts mit arXiv-ID oder DOI als Tool-Beleg.
    Opt-in über spec["inspire"] bzw. Domain.recherche_inspire = True."""
    url = "https://inspirehep.net/api/literature?" + urllib.parse.urlencode(
        {"q": q, "size": n, "sort": "bestmatch", "fields": "titles,abstracts,arxiv_eprints,dois,authors.full_name,earliest_date,control_number"})
    out = []
    for h in json.loads(_get(url)).get("hits", {}).get("hits", []):
        m = h.get("metadata", {}); ab = " ".join(((m.get("abstracts") or [{}])[0].get("value") or "").split())
        if not ab or not m.get("titles"): continue
        ax = (m.get("arxiv_eprints") or [{}])[0].get("value"); doi = (m.get("dois") or [{}])[0].get("value")
        rid = f"arXiv:{ax}" if ax else (f"doi:{doi}" if doi else f"inspire:{m.get('control_number')}")
        out.append({"id": rid, "titel": " ".join(m["titles"][0].get("title", "").split()), "abstract": ab, "jahr": str(m.get("earliest_date", ""))[:4],
                    "autoren": ", ".join(a.get("full_name", "") for a in (m.get("authors") or [])[:12]),
                    "url": f"https://arxiv.org/abs/{ax}" if ax else (f"https://doi.org/{doi}" if doi else f"https://inspirehep.net/literature/{m.get('control_number')}")})
    return out


def arxiv_meta(aid):
    """Metadaten eines arXiv-Eintrags per ID (Autoren, Titel, Jahr)."""
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": aid.replace("arXiv:", "")})
    ns = {"a": "http://www.w3.org/2005/Atom"}; e = ET.fromstring(_get(url)).find("a:entry", ns)
    if e is None or e.find("a:title", ns) is None: raise ValueError("arXiv-ID nicht gefunden")
    return {"id": aid, "titel": " ".join(e.find("a:title", ns).text.split()), "jahr": e.find("a:published", ns).text[:4],
            "autoren": ", ".join(a.find("a:name", ns).text for a in e.findall("a:author", ns)), "journal": f"arXiv:{aid.replace('arXiv:', '')}"}


def crossref_doi(doi):
    return _crossref_doc(json.loads(_get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"])


def chain(corpus, top_ids, max_new=150, log=print):
    """Zitationskette: Referenzlisten (Crossref) der wichtigsten Quellen auflösen und als neue Quellen aufnehmen."""
    new = 0; refs = []
    for i in top_ids:
        doc = corpus.get(i)
        if not doc or not i.startswith("doi:"): continue
        try: d = crossref_doi(i[4:]) if not doc.get("refs") else doc
        except Exception: continue
        refs += d.get("refs", [])
    for doi in dict.fromkeys(refs):
        if new >= max_new: break
        if f"doi:{doi}" in corpus: continue
        try: corpus[f"doi:{doi}"] = crossref_doi(doi) | {"aus_kette": True}; new += 1
        except Exception: continue
        time.sleep(0.2)
    log(f"Zitationskette: {len(set(refs))} Referenzen gefunden, {new} neue Quellen aufgenommen")
    return new


def local_docs(folder="literature", chunk_words=250):
    """Eigene Quellen des Teams (Markdown, Text, PDF via pdftotext) als zusätzliche Dokumente. Jeder Abschnitt wird wie ein
    Abstract behandelt: gleiche Sichtung, gleiche Zitatprüfung, gleicher Leck-Filter."""
    import subprocess
    out = []
    if not os.path.isdir(folder): return out
    for fn in sorted(os.listdir(folder)):
        path = os.path.join(folder, fn)
        if fn.lower().endswith((".md", ".txt")): text = open(path, encoding="utf-8", errors="replace").read()
        elif fn.lower().endswith(".pdf"):
            try: text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, timeout=120).stdout
            except (OSError, subprocess.TimeoutExpired): continue
        else: continue
        words = text.split()
        for j in range(0, len(words), chunk_words):
            part = " ".join(words[j:j + chunk_words])
            out.append({"id": f"lokal:{fn}#{j // chunk_words}", "titel": f"{fn} (Abschnitt {j // chunk_words + 1})", "abstract": part,
                        "jahr": "", "autoren": "", "url": f"literature/{fn}"})
    return out


def _norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("‐", "-").replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"[^a-z0-9%+\-.,()' ]", " ", re.sub(r"\s+", " ", s)).strip()


def quote_ok(quote, abstract):
    """Zitat-Prüfer (Code): das Zitat muss (normalisiert) wörtlich im Abstract stehen und mindestens 6 Wörter haben."""
    q = _norm(quote)
    return len(q.split()) >= 6 and re.sub(r"\s+", " ", q) in re.sub(r"\s+", " ", _norm(abstract))


def blocked(doc, sperre):
    t = (doc["titel"] + " " + doc["abstract"] + " " + doc["autoren"]).lower()
    return next((w for w in sperre if w in t), None)


def run(topic, n_queries=10, per_query=25, keep=60, model_cheap="haiku", model_main="sonnet", log=print, spec=None, kette=0):
    """spec: {"ziel": str, "sperre": [..], "faktoren": [..]} für beliebige Themen; sonst TOPICS[topic]."""
    T = spec or TOPICS[topic]; T.setdefault("sperre", []); T.setdefault("faktoren", []); d = f"{KB}/{topic}"; os.makedirs(d, exist_ok=True); stats = {"start": time.strftime("%H:%M:%S")}
    # 1. Suchplanung (günstiges Modell)
    qs = ask_json(f"Forschungsziel: {T['ziel']}\n\nErzeuge {n_queries} verschiedene, kurze englische Suchanfragen (3-6 Wörter) für "
                  "arXiv bzw. Europe PMC, die unterschiedliche Aspekte abdecken (Mechanismus, einzelne Faktoren, Gegenbeispiele, Übersichten). "
                  'JSON: {"queries": ["...", ...]}', model=model_cheap, salt=f"research-{topic}-q{n_queries}")["queries"][:n_queries]
    qs = list(dict.fromkeys(qs + list(T.get("klassiker", []))))
    log(f"Suchanfragen: {qs}")
    # 2. Abruf (Code)
    corpus, seen = {}, set(); klassiker_hits = {k: [] for k in T.get("klassiker", [])}
    cpath = f"{d}/korpus_cache.json"
    if os.path.exists(cpath):                                   # fortsetzbar: Abruf nicht wiederholen
        c = json.load(open(cpath)); corpus, klassiker_hits = c["korpus"], c.get("klassiker", klassiker_hits); qs = c["suchanfragen"]; seen = None
        log(f"Korpus aus Cache: {len(corpus)} Quellen")
    for q in (qs if seen is not None else []):
        for src in (search_arxiv, search_europepmc) + ((search_crossref,) if T.get("crossref") else ()) + ((search_inspire,) if T.get("inspire") else ()):
            try: docs = src(q, per_query)
            except Exception as e: log(f"Abruf-Fehler {src.__name__} '{q}': {e}"); docs = []
            if q in klassiker_hits: klassiker_hits[q] += [f"{d['id']} — {d['titel'][:90]} ({d['jahr']})" for d in docs[:3]]
            for doc in docs:
                k = _norm(doc["titel"])[:120]
                if k in seen: continue
                seen.add(k); corpus[doc["id"]] = doc
            time.sleep(1.0)                                  # arXiv-Richtlinie: höflich abfragen
    for doc in local_docs():                                  # eigene Dateien des Teams in literature/
        corpus.setdefault(doc["id"], doc)
    json.dump({"korpus": corpus, "klassiker": klassiker_hits, "suchanfragen": qs}, open(cpath, "w"), ensure_ascii=False)
    stats_abgerufen_direkt = len(corpus)
    gesperrt = {i: w for i, doc in corpus.items() if (w := blocked(doc, T["sperre"]))}
    pool = {i: doc for i, doc in corpus.items() if i not in gesperrt}
    stats.update(abgerufen=len(corpus), gesperrt=len(gesperrt)); log(f"{len(corpus)} Quellen, {len(gesperrt)} durch Leck-Filter gesperrt")
    # 3. Sichtung (günstiges Modell, 25 Titel+Kurzabstract pro Aufruf)
    ids = list(pool); scores = {}
    def screen(b):
        batch = ids[b:b + 25]
        listing = "\n".join(f"[{j}] {pool[i]['titel']} — {pool[i]['abstract'][:300]}" for j, i in enumerate(batch))
        try: r = ask_json(f"Forschungsziel: {T['ziel']}\n\nBewerte jede Quelle 0-10 nach Relevanz für das Ziel.\n{listing}\n\n"
                          'JSON: {"scores": [{"j": 0, "s": 7}, ...]}', model=model_cheap, salt=f"research-{topic}-screen-{b}")
        except Exception: return []
        out = []
        for e in r.get("scores", []):
            try: out.append((batch[int(e["j"])], float(e["s"])))
            except (KeyError, ValueError, IndexError, TypeError): pass
        return out
    for res in _pmap(screen, list(range(0, len(ids), 25))): scores.update(dict(res))
    log(f"Sichtung: {len(scores)} Quellen bewertet")
    top = sorted(scores, key=scores.get, reverse=True)[:keep]
    if kette:                                                  # Zitationskette ab den relevantesten Quellen, neue Quellen ebenfalls sichten
        before = set(corpus); chain(corpus, top[:kette], log=log)
        added = {i: corpus[i] for i in set(corpus) - before if not blocked(corpus[i], T["sperre"])}
        pool.update(added); ids2 = list(added)
        for b in range(0, len(ids2), 25):
            batch = ids2[b:b + 25]
            listing = "\n".join(f"[{j}] {pool[i]['titel']} — {pool[i]['abstract'][:300]}" for j, i in enumerate(batch))
            r = ask_json(f"Forschungsziel: {T['ziel']}\n\nBewerte jede Quelle 0-10 nach Relevanz für das Ziel.\n{listing}\n\n"
                         'JSON: {"scores": [{"j": 0, "s": 7}, ...]}', model=model_cheap, salt=f"research-{topic}-screen-kette-{b}")
            for e in r.get("scores", []):
                try: scores[batch[int(e["j"])]] = float(e["s"])
                except (KeyError, ValueError, IndexError, TypeError): pass
        top = sorted(scores, key=scores.get, reverse=True)[:keep]
    top = [i for i in top if len(pool[i]["abstract"]) >= 150] or top        # Extraktion braucht Text (Zitat muss aus dem Abstract kommen)
    stats.update(abgerufen=len(corpus), gesichtet=len(scores), ausgewählt=len(top))
    # 4. Extraktion mit wörtlichen Zitaten (Hauptmodell, 6 Abstracts pro Aufruf)
    facts = []
    fac = f" Wenn ein Befund einen der Faktoren {T['faktoren']} betrifft, gib zusätzlich 'faktor' und 'stufe' (Name der Substanz) und 'richtung' (+1 höhere, -1 niedrigere Ausbeute) an." if T["faktoren"] else ""
    def extract(b):
        batch = top[b:b + 6]
        listing = "\n\n".join(f"<<{i}>>\nTitel: {pool[i]['titel']}\nAbstract: {pool[i]['abstract']}" for i in batch)
        try: r = ask_json(f"Forschungsziel: {T['ziel']}\n\n{listing}\n\nExtrahiere die für das Ziel wichtigsten Befunde. Achte besonders auf OFFENE FRAGEN: Formulierungen wie 'remains open', 'it is unknown whether', 'we conjecture', 'open problem', 'has not been proven', 'left for future work', 'it would be interesting', 'numerically but not analytically'; diese als typ 'offene_frage'. Jeder Befund braucht ein "
                     "WÖRTLICHES Zitat (mindestens 6 Wörter, exakt kopiert) aus dem jeweiligen Abstract." + fac +
                     ' JSON: {"befunde": [{"quelle": "<id>", "aussage": "<deutsch, ein Satz>", "zitat": "<wörtlich>", "typ": "ergebnis|methode|offene_frage"}]}',
                     model=model_main, salt=f"research-{topic}-extract-{b}")
        except Exception: return []
        return r.get("befunde", [])
    for fs in _pmap(extract, list(range(0, len(top), 6))): facts += fs
    # 5. Zitat-Prüfer (Code)
    ok = verify_facts(facts, pool); stats.update(befunde=len(facts), verifiziert=len(ok))
    classify(ok, T, model_cheap, topic)
    log(f"{len(facts)} Befunde extrahiert, {len(ok)} Zitate per Code bestätigt, {len(facts) - len(ok)} verworfen")
    stats["klassiker_gefunden"] = sum(bool(v) for v in klassiker_hits.values()); stats["klassiker_gesamt"] = len(klassiker_hits)
    json.dump({"thema": topic, "ziel": T["ziel"], "suchanfragen": qs, "stats": stats, "klassiker": klassiker_hits, "gesperrt": gesperrt,
               "korpus": corpus, "scores": scores, "befunde": facts}, open(f"{d}/kb.json", "w"), ensure_ascii=False, indent=1)
    write_md(topic, T, qs, stats, ok, gesperrt, corpus)
    with open(f"{d}/known_results.md", "a") as f:
        f.write("\n## Klassiker-Abdeckung (Suche nach Autor + Thema; Treffer = per Tool abgerufene Einträge)\n\n")
        for k, v in klassiker_hits.items():
            f.write(f"- **{k}**: " + ("; ".join(v) if v else "NICHT GEFUNDEN") + "\n")
    return ok, stats


def classify(facts, T, model, topic):
    """Evidenzstatus je bestätigtem Befund: bewiesen | numerisch | experimentell | vermutet (aus dem Wortzitat beurteilt)."""
    for b in range(0, len(facts), 20):
        batch = facts[b:b + 20]
        listing = "\n".join(f"[{j}] {f['aussage']} — Zitat: „{f['zitat']}“" for j, f in enumerate(batch))
        try:
            r = ask_json(f"Ordne jedem Befund seinen Evidenzstatus zu, nur nach dem Zitat: 'bewiesen' (mathematischer Beweis/Theorem), 'numerisch' "
                         "(Simulation/Rechnung), 'experimentell' (Messung), 'vermutet' (Behauptung, Hypothese, Modellargument ohne Beweis).\n"
                         f'{listing}\n\nJSON: {{"status": [{{"j": 0, "s": "bewiesen"}}, ...]}}', model=model, salt=f"research-{topic}-classify-{b}")
            for e in r.get("status", []): batch[int(e["j"])]["status"] = e["s"]
        except Exception: pass


def _resolve(qid, pool):
    """Quellen-ID robust zuordnen (das LLM lässt Präfixe wie 'doi:' oder 'arXiv:' gern weg)."""
    qid = str(qid or "").strip().strip("<>")
    for k in (qid, f"doi:{qid}", f"arXiv:{qid}", f"pmid:{qid}"):
        if k in pool: return pool[k]
    return next((d for k, d in pool.items() if k.split(":", 1)[-1] == qid.split(":", 1)[-1]), None)


def verify_facts(facts, pool):
    for f in facts:
        doc = _resolve(f.get("quelle"), pool); f["verifiziert"] = bool(doc and quote_ok(f.get("zitat", ""), doc["abstract"]))
        if doc: f.update(quelle=doc["id"], titel=doc["titel"], jahr=doc["jahr"], url=doc["url"])
    return [f for f in facts if f["verifiziert"]]


def reverify(topic):
    """Zitatprüfung auf gespeicherten Befunden neu ausführen (ohne neue LLM-Aufrufe)."""
    T = TOPICS.get(topic) or json.load(open(f"{KB}/{topic}/kb.json")); path = f"{KB}/{topic}/kb.json"; kb = json.load(open(path))
    pool = {i: d for i, d in kb["korpus"].items() if i not in kb["gesperrt"]}
    ok = verify_facts(kb["befunde"], pool); kb["stats"]["verifiziert"] = len(ok)
    json.dump(kb, open(path, "w"), ensure_ascii=False, indent=1)
    write_md(topic, T, kb["suchanfragen"], kb["stats"], ok, kb["gesperrt"], kb["korpus"]); return ok, kb["stats"]


def write_md(topic, T, qs, stats, ok, gesperrt, corpus):
    L = [f"# Wissensstand: {topic}", "", f"**Ziel:** {T['ziel']}", "",
         f"**Ablauf:** {len(qs)} Suchanfragen → {stats['abgerufen']} Quellen (arXiv, Europe PMC) → {stats['gesperrt']} durch Leck-Filter gesperrt → "
         f"{stats['ausgewählt']} nach Relevanz ausgewählt → {stats['befunde']} Befunde extrahiert → **{stats['verifiziert']} mit per Code bestätigtem Wortzitat**.", "",
         "Nur Befunde mit bestätigtem Zitat stehen hier. Gesperrte Quellen (Leck-Schutz) sind unten aufgeführt.", ""]
    for typ in ("ergebnis", "methode", "offene_frage"):
        items = [f for f in ok if f.get("typ") == typ]
        if not items: continue
        L += [f"## {dict(ergebnis='Ergebnisse', methode='Methoden', offene_frage='Offene Fragen')[typ]}", ""]
        for f in items:
            extra = f" *(Faktor {f['faktor']}={f['stufe']}, Richtung {f.get('richtung')})*" if f.get("faktor") else ""
            L.append(f"- {f['aussage']}{extra}  \n  > „{f['zitat']}“ — {f['titel']} ({f['jahr']}), [{f['quelle']}]({f['url']})")
        L.append("")
    refs = {f["quelle"]: f for f in ok}
    L += ["## Literaturverzeichnis (nur per Tool abgerufene Quellen mit Befund)", ""] + [f"- {f['titel']} ({f['jahr']}). [{q}]({f['url']})" for q, f in sorted(refs.items(), key=lambda x: x[1]["jahr"])] + [""]
    K = ["# Bekannte Resultate (known_results.md)", "", f"Thema: {T['ziel']}", "",
         "Jede Zeile: Befund, Evidenzstatus (aus dem Wortzitat beurteilt), Quelle (DOI bzw. arXiv-ID, per Tool abgerufen). Zitat per Code im Abstract bestätigt.", "",
         "| Status | Befund | Quelle |", "|---|---|---|"]
    for f in sorted(ok, key=lambda f: ["bewiesen", "numerisch", "experimentell", "vermutet"].index(f.get("status", "vermutet")) if f.get("status", "vermutet") in ["bewiesen", "numerisch", "experimentell", "vermutet"] else 4):
        K.append(f"| {f.get('status', '?')} | {f['aussage'].replace('|', '/')} | [{f['quelle']}]({f['url']}) |")
    open(f"{KB}/{topic}/known_results.md", "w").write("\n".join(K) + "\n")
    L += ["## Durch Leck-Filter gesperrt", ""] + [f"- {corpus[i]['titel']} ({corpus[i]['jahr']}) — Treffer: „{w}“" for i, w in list(gesperrt.items())[:40]]
    open(f"{KB}/{topic}/wissensstand.md", "w").write("\n".join(L) + "\n")


def literature_hypotheses(topic="buchwald", model="sonnet"):
    """Literaturgestützte Hypothesen für den GP-Prior: das LLM sieht nur per Code bestätigte Befunde [F..] und die exakten
    Stufen des Datensatzes (keine Ausbeuten). Jede Hypothese muss Befund-IDs als Beleg nennen; der Code prüft Stufen und Belege."""
    from .data import load, component_view
    from .hypotheses import parse, Hypothesis
    kb = json.load(open(f"{KB}/{topic}/kb.json")); ds = load()
    facts = [f for f in kb["befunde"] if f.get("verifiziert")]; fid = {f"F{j + 1}": f for j, f in enumerate(facts)}
    levels = {f: [r["level"] for r in rows] for f, rows in component_view(ds, "named").items()}
    listing = "\n".join(f"[{k}] {f['aussage']} (Zitat: „{f['zitat']}“, {f['quelle']})" for k, f in fid.items())
    prompt = (f"Datensatz-Stufen (exakte Namen):\n{json.dumps(levels, ensure_ascii=False)}\n\nBelegte Literaturbefunde:\n{listing}\n\n"
              "Leite 4 bis 12 Hypothesen ab, welche dieser Stufen die Ausbeute einer Buchwald-Hartwig-Aminierung mit p-Toluidin erhöhen "
              "oder senken. Nur Hypothesen, die sich direkt auf die Befunde stützen; jede nennt ihre Belege. Übertrage nichts, was "
              "die Befunde nicht hergeben (andere Substrate, andere Katalysatoren nur mit Vorsicht und kleinerem Effekt).\n"
              'JSON: {"hypotheses": [{"id": "H1", "text": "<ein Satz>", "belege": ["F3", ...], "effect": {"<faktor>=<stufe>": <Zahl -2..2>}}]}')
    raw = ask_json(prompt, model=model, salt=f"lit-hyp-{topic}")
    hyps = parse(json.dumps(raw), "named", ds); belege = {h.get("id"): h.get("belege", []) for h in raw.get("hypotheses", [])}
    out = []
    for h in hyps:
        b = [x for x in belege.get(h.id.split("-", 1)[-1], []) if x in fid]
        if not b: continue                                             # ohne gültigen Beleg keine Hypothese
        out.append(Hypothesis(id=h.id.replace("named-", "lit-"), text=h.text, effect=h.effect, view="named",
                              meta={"belege": [{"id": x, "quelle": fid[x]["quelle"], "zitat": fid[x]["zitat"], "url": fid[x]["url"]} for x in b]}))
    json.dump({"view": "named", "generator": f"Recherche-Agent + Hypothesen-Schritt ({model}); nur per Code bestätigte Befunde",
               "prompt": prompt, "raw_response": raw, "hypotheses": [h.__dict__ for h in out]},
              open("hypotheses/literature.json", "w"), ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("topic", choices=list(TOPICS)); ap.add_argument("--queries", type=int, default=10)
    a = ap.parse_args(); ok, st = run(a.topic, a.queries); print(json.dumps(st, ensure_ascii=False))
    if a.topic == "buchwald": print(f"{len(literature_hypotheses())} Literatur-Hypothesen -> hypotheses/literature.json")
