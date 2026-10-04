"""Neuheitsprüfung.

1. Pro bestätigtem Claim (aus der Labor-Schleife direkt nach dem Red-Team): Ein LLM formuliert 3-5 gezielte Suchanfragen für genau
   dieses Resultat; ausgeführt über arXiv, Europe PMC und Crossref. "Steht schon in der Literatur" zählt NUR mit einem wörtlichen
   Zitat, das quote_ok() im Abstract bestätigt. Status: bekannt (Quelle + Zitat) | offen_laut_literatur (eine Quelle nennt es
   ausdrücklich offen, Zitat bestätigt) | nicht_gefunden (Suchanfragen + Trefferzahl gespeichert). Das Wort "neu" vergibt nie ein LLM.
2. CLI für ein ganzes Projekt:  python -m asd.novelty <projekt> [--domain <domain>]   (füllt claim["neuheit"] und schreibt neuheit.md)
"""
import json, re, sys, time


def check_claim(D, claim, salt=""):
    from .llm import ask_json
    from .research import search_arxiv, search_europepmc, search_crossref, search_inspire, quote_ok
    try: aussage = D.describe(claim["pruefung"], lang="en")
    except TypeError: aussage = D.describe(claim["pruefung"])
    q = ask_json(f"Research field: {D.kontext}\n\nVerified result: {aussage}\n\nFormulate 3-5 short, specific English search queries (3-7 words) "
                 "that would find a paper stating exactly this result or stating that it is open. JSON: {\"queries\": [\"...\"]}",
                 "You are a careful literature searcher. Answer with valid JSON only.", model="haiku", salt=f"novelty-q-{salt}")["queries"][:5]
    docs, treffer = {}, {}
    for qq in q:
        n = 0
        for src in (search_arxiv, search_europepmc, search_crossref) + ((search_inspire,) if getattr(D, "recherche_inspire", False) else ()):
            try:
                for d in src(qq, 8):
                    if d.get("abstract") and len(d["abstract"]) > 150: docs.setdefault(d["id"], d); n += 1
            except Exception: pass
        treffer[qq] = n
    listing = "\n\n".join(f"<<{i}>> {d['titel']}\n{d['abstract'][:1500]}" for i, d in list(docs.items())[:30])
    r = ask_json(f"Result to check: {aussage}\n\nCandidate abstracts:\n{listing}\n\nDoes any abstract state THIS result (same model class, same statement) or "
                 "state explicitly that it is open? Only answer with a verbatim quote (at least 8 words, copied exactly). "
                 'JSON: {"befund": "bekannt|offen|keiner", "quelle": "<id>", "zitat": "<verbatim>"}',
                 "You judge literature overlap strictly. Answer with valid JSON only.", model="sonnet", salt=f"novelty-j-{salt}")
    st = {"suchanfragen": q, "treffer": treffer, "quellen_geprueft": len(docs), "datum": time.strftime("%Y-%m-%d")}
    d = docs.get(r.get("quelle", ""))
    if r.get("befund") in ("bekannt", "offen") and d and quote_ok(r.get("zitat", ""), d["abstract"]):
        st.update(status="bekannt" if r["befund"] == "bekannt" else "offen_laut_literatur", quelle=d["id"], zitat=r["zitat"], titel=d["titel"])
    else:
        st["status"] = "nicht_gefunden"
    return st


def main():
    import argparse
    from .domains.base import get_domain
    ap = argparse.ArgumentParser(); ap.add_argument("projekt"); ap.add_argument("--domain", default=""); ap.add_argument("--neu", action="store_true")
    a = ap.parse_args(); D = get_domain(a.domain or a.projekt); p = f"projects/{a.projekt}/state.json"; s = json.load(open(p))
    L = [f"# Novelty check ({time.strftime('%Y-%m-%d')})", "", "Status per verified claim: bekannt (verbatim quote confirmed) | offen_laut_literatur | nicht_gefunden.", "",
         "| Claim | Status | Evidence / queries |", "|---|---|---|"]
    for c in s["claims"]:
        if c.get("status") != "bestätigt": continue
        if a.neu or not c.get("neuheit"): c["neuheit"] = check_claim(D, c, salt=c["id"])
        n = c["neuheit"]
        ev = (f"{n['quelle']}: \"{n['zitat'][:120]}\"" if n["status"] != "nicht_gefunden" else
              f"{n['quellen_geprueft']} abstracts checked; queries: " + "; ".join(n["suchanfragen"]))
        L.append(f"| {c['id']} | {n['status']} | {ev.replace('|', '/')} |")
        json.dump(s, open(p, "w"), ensure_ascii=False, indent=1)
    open(f"projects/{a.projekt}/neuheit.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    main()
