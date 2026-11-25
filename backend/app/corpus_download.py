"""Download the corpus data on the server from the corpus-v1 release (the Tablets page's button).

The same download as `python scripts/fetch_corpus.py`: transcriptions, the scholars' boxes and
the tablet drawings, into fraction-solver/. It runs in a background thread, one at a time; the
page polls `status()` until it ends. Files already present are kept.
"""
import logging
from threading import Lock, Thread

from backend.app import corpus, glyph_index
from scripts import fetch_corpus

log = logging.getLogger(__name__)
_lock = Lock()
_state = {"state": "idle", "log": [], "error": None}
LOG_LINES = 20


def status() -> dict:
    with _lock:
        return {**_state, "log": list(_state["log"])}


def start() -> bool:
    """Start a download; False when one is already running."""
    with _lock:
        if _state["state"] == "running":
            return False
        _state.update(state="running", log=[], error=None)
    Thread(target=_run, name="corpus-download", daemon=True).start()
    return True


def _line(text: str) -> None:
    with _lock:
        _state["log"] = [*_state["log"], text][-LOG_LINES:]


def _run() -> None:
    try:
        fetch_corpus.fetch(log=_line)
    except fetch_corpus.FetchError as error:
        _finish("failed", str(error))
    except Exception as error:  # noqa: BLE001  (a network or disk failure: report it, keep the server up)
        log.exception("Corpus download failed")
        _finish("failed", f"The download failed ({type(error).__name__}). See the server log.")
    else:
        _finish("done", None)


def _finish(state: str, error: str | None) -> None:
    # New drawings, transcriptions or boxes: list and index them again on the next request.
    corpus._drawn.clear()
    glyph_index._index = None
    with _lock:
        _state.update(state=state, error=error)
