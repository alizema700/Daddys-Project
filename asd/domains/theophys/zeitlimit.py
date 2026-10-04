"""Harte Zeitlimits für Rechnungen des Prüfers und der Experimente: die Funktion läuft in einem eigenen Prozess (forkserver, damit das
Forken aus einem Prozess mit Threads sicher ist) und wird bei Überschreitung beendet. Zeitüberschreitung ist nie "bestanden"."""
import multiprocessing as mp
import os

_CTX = None


def _ctx():
    global _CTX
    if _CTX is None:
        _CTX = mp.get_context("forkserver")
        _CTX.set_forkserver_preload(["sympy", "numpy", "flint", "asd.domains.theophys.ausdruck"])
    return _CTX


def _lauf(q, fn, args, kwargs):
    try: q.put(("ok", fn(*args, **kwargs)))
    except BaseException as e: q.put(("fehler", f"{type(e).__name__}: {str(e)[:400]}"))


class _OhneMain:
    """Während des Starts das Hauptskript verbergen: sonst importiert multiprocessing es im Kindprozess erneut (ein Skript ohne
    `if __name__ == "__main__"` würde sich dann selbst wieder ausführen). Die Rechenfunktionen liegen in asd/, nicht im Hauptskript."""
    def __enter__(self):
        import sys
        self.m = sys.modules.get("__main__"); self.f = getattr(self.m, "__file__", None); self.s = getattr(self.m, "__spec__", None)
        if self.m is not None:
            if self.f is not None: del self.m.__file__
            self.m.__spec__ = None
        return self
    def __exit__(self, *a):
        if self.m is not None:
            if self.f is not None: self.m.__file__ = self.f
            self.m.__spec__ = self.s
        return False


class Zeitueberschreitung(RuntimeError):
    pass


def mit_zeitlimit(fn, *args, sek=None, **kwargs):
    """fn(*args, **kwargs) mit Zeitlimit sek (Standard THEOPHYS_ZEIT, 300 s). THEOPHYS_OHNE_PROZESS=1 rechnet im selben Prozess (Tests)."""
    sek = float(sek or os.environ.get("THEOPHYS_ZEIT", "300"))
    if os.environ.get("THEOPHYS_OHNE_PROZESS") == "1": return fn(*args, **kwargs)
    ctx = _ctx(); q = ctx.Queue(); p = ctx.Process(target=_lauf, args=(q, fn, args, kwargs), daemon=True)
    with _OhneMain(): p.start()
    try:
        art, wert = q.get(timeout=sek)
    except Exception:
        p.kill(); p.join(5)
        raise Zeitueberschreitung(f"Zeitüberschreitung (> {sek:.0f} s)")
    p.join(5)
    if art == "fehler": raise RuntimeError(wert)
    return wert
