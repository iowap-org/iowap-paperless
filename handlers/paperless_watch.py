#!/usr/bin/env python3
"""paperless.watch — long_run pipeline starter (T-232).

Loops: poll recent consume-tasks in Paperless → a success we haven't
seen yet = its related_document_ids carry the fresh doc id → fetch doc +
content → hp put the PDF as an artifact → submit the document-ingest
flow (doc.process on the AI node, paperless.apply writes back) → keep
the watcher's own lease alive with keepalive notes.

Env: PAPERLESS_URL, PAPERLESS_TOKEN, PAPERLESS_POLL_SECONDS (default 15),
IOWAP_INGEST (task text template; {doc_id},{title},{content},{filename}
placeholders). Flow submission goes through node-cli (node identity).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paperless import api, api_binary, fail, read_stdin  # noqa: E402

CLI = os.environ.get("NODE_CLI", "node-cli")
POLL = max(5, int(os.environ.get("PAPERLESS_POLL_SECONDS", "15")))
NOTE_EVERY = 600

INGEST_TASK = os.environ.get(
    "IOWAP_INGEST_TASK",
    "document-ingest for paperless doc {doc_id} ({name}): "
    "step 1 run doc.process with document_text: {text!r} (document: {name}); "
    "it returns title and tags. "
    "step 2 run paperless.apply with doc_id={doc_id}, "
    "tags=${{step1.result.tags}}, title=${{step1.result.title}}, "
    "correspondent=${{step1.result.correspondent}}",
)

# GLM-OCR-Route: vorgeschaltet, wenn Paperless' content zu dünn ist
# (Scan-PDF ohne brauchbaren Tesseract-Text, Bild-Dokumente).
INGEST_TASK_OCR = os.environ.get(
    "IOWAP_INGEST_OCR_TASK",
    "document-ingest (OCR route) for paperless doc {doc_id} ({name}): "
    "step 1 run doc.ocr with image_path {ocr_path!r} and mode text; "
    "it returns the recognized text. "
    "step 2 run doc.process with document_text: ${{step1.result.text!r}} (document: {name}); "
    "it returns title and tags. "
    "step 3 run paperless.apply with doc_id={doc_id}, "
    "tags=${{step2.result.tags}}, title=${{step2.result.title}}, "
    "correspondent=${{step2.result.correspondent}}",
)

MEDIA_DIR = os.environ.get("PAPERLESS_MEDIA_DIR", "")
MIN_CONTENT_CHARS = int(os.environ.get("IOWAP_GATE_MIN_CHARS", "120"))
VERBATIM_EXT = {".txt", ".md", ".csv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".webp", ".bmp"}


def doc_gate(doc: dict, content: str) -> tuple[str, str]:
    """Flow-route decision (doc.gate): returns (route, ocr_path-or-empty).

    - verbatim/text-rich → INGEST_TASK (Tesseract/paperless content ist die Quelle)
    - content-arm (Scan-PDF/Hände-Layout) oder Bild → INGEST_TASK_OCR
      (GLM-OCR fressen die paperless-Thumbnails-Seite)
    digital PDFs mit Text-Layer landen automatisch in der Text-Route,
    weil Paperless' consume sie OHNE OCR liest („OCR the document, if it
    has no text") — der content ist dann der embedded Text.
    """
    name = doc.get("original_filename") or f"doc-{doc.get('id')}"
    ext = os.path.splitext(name)[1].lower()
    if ext in VERBATIM_EXT:
        return "verbatim", ""
    if ext in IMAGE_EXT:
        thumb = thumbnail_path(doc, name)
        if thumb:
            return "image-vlm", thumb
        return "image-vlm", ""
    # PDF & unbekannt: Content-Länge entscheidet (digitale PDFs = reicher Text!)
    if len(content.strip()) < MIN_CONTENT_CHARS:
        thumb = thumbnail_path(doc, name)
        if thumb:
            return "ocr-route", thumb
        return "ocr-route", ""
    return "text-rich", ""


def thumbnail_path(doc: dict, name: str) -> str:
    """Paperless erzeugt je Doc ein Seiten-PNG (media/thumbnails/…) — der
    GLM-OCR-Input. Ohne MEDIA_DIR-Mount bleibt die Route nur textbasiert."""
    if not MEDIA_DIR:
        return ""
    doc_id = doc.get("id")
    padded = f"{doc_id:07d}"  # Paperless thumbnails sind zero-padded (0000004.webp)
    for cand in (os.path.join(MEDIA_DIR, "documents", "thumbnails", f"{padded}.webp"),
                 os.path.join(MEDIA_DIR, "documents", "thumbnails", f"{padded}.png"),
                 os.path.join(MEDIA_DIR, "thumbnails", f"{padded}.webp")):
        if os.path.isfile(cand):
            return cand
    import glob
    hits = sorted(glob.glob(os.path.join(MEDIA_DIR, "thumbnails", f"{doc_id}.*")))
    return hits[0] if hits else ""


def cli(*args: str, capture: bool = True) -> str:
    argv = [CLI, *args, "--json"]
    out = subprocess.run(argv, text=True, capture_output=True, timeout=240)
    return out.stdout.strip() if capture else ""


def hp_put(path: str, cap: str) -> dict:
    envelope = cli("hp", "put", path, "--cap", cap)
    try:
        return json.loads(envelope)
    except ValueError:
        return {"__iowap_ref__": None}


def main() -> None:
    data = read_stdin()
    inp = data.get("input") or {}
    text_cap = int(inp.get("text_chars") or 6000)
    seen: set[int] = set()
    last_note = 0.0
    processed = 0
    started = time.time()
    errors = 0

    while True:
        try:
            out = api("/api/tasks/")
            for task in (out.get("results") or []):
                if (task.get("status") or "").lower() != "success":
                    continue
                rids = task.get("related_document_ids") or []
                if not rids:
                    continue
                doc_id = rids[0]
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                processed += 1
                doc = api(f"/api/documents/{doc_id}/")
                content = (doc.get("content") or "")[:text_cap]
                title = doc.get("title") or f"doc {doc_id}"
                pdf_name = doc.get("original_filename") or f"doc-{doc_id}.pdf"
                route, ocr_path = doc_gate(doc, content)
                try:  # note the branch — sichtbar im task & im Log
                    cli("task", "note", f"doc.gate doc_id={doc_id}: route={route}, ocr_path={ocr_path or '-'}")
                except Exception:  # noqa: BLE001
                    pass
                if ocr_path:
                    text_for_template = ""
                else:
                    text_for_template = content.replace('"', "'")
                with tempfile.TemporaryDirectory() as tmp:
                    pdf_path = os.path.join(tmp, pdf_name)
                    open(pdf_path, "wb").write(api_binary(f"/api/documents/{doc_id}/download/"))
                    ref = hp_put(pdf_path, "paperless.watch")
                template = INGEST_TASK_OCR if ocr_path else INGEST_TASK
                if ocr_path:
                    body_text = template.format(
                        doc_id=doc_id, name=pdf_name, ocr_path=ocr_path, title=title,
                        text=text_for_template)
                else:
                    body_text = template.format(
                        doc_id=doc_id, title=title, name=pdf_name, text=text_for_template)
                stage = json.dumps({
                    "mode": "ad_hoc",
                    "task": body_text,
                    "options": {"pdf": ref, "route": route},
                })
                submit = cli("task", "submit", "--stage", f"flow.run:{stage}")
                try:
                    sub = json.loads(submit) if submit else {}
                except ValueError:
                    sub = {"raw": submit}
                if sub.get("task_id"):
                    errors = 0
                else:
                    errors += 1
        except Exception:  # noqa: BLE001 — watcher must survive upstream hiccups
            errors += 1
        if time.time() - last_note >= NOTE_EVERY:
            cli("task", "note", f"watcher alive; processed={processed}, uptime={int(time.time()-started)}s")
            last_note = time.time()
        if errors >= 12:  # ~3 min of failures → honest death, daemon retries later
            try:
                cli("task", "note", f"watcher aborting: {errors} consecutive poll failures")
            except Exception:  # noqa: BLE001
                pass
            fail(f"watcher aborting after {errors} consecutive upstream failures")
            return
        time.sleep(POLL)


if __name__ == "__main__":
    main()