#!/usr/bin/env python3
"""Shared Paperless REST client for iowap-paperless handlers (T-232).

Auth: `Authorization: Token <key>` (NOT Bearer). post_document answers
only {"task_id": ...} — the doc id arrives later via related_document_ids
inside the consume task; poll it with poll_consume_task().
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import time
import urllib.parse
import uuid


def cfg() -> tuple[str, str]:
    base = os.environ.get("PAPERLESS_URL", "http://127.0.0.1:8000").rstrip("/")
    tok = os.environ.get("PAPERLESS_TOKEN", "")
    return base, tok


def _host_port() -> tuple[str, int]:
    base, _ = cfg()
    parts = urllib.parse.urlsplit(base)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return host, port


def _headers(body: bytes | None, extra: dict | None = None) -> dict:
    _, tok = cfg()
    h = {"Authorization": f"Token {tok}"}
    if body is not None:
        h["Content-Type"] = "application/json"
    if extra:
        h.update(extra)
    return h


def _json_or_text(raw: bytes):
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return raw.decode("utf-8", "replace")


def _roundtrip(method: str, path: str, body: bytes | None = None,
               extra_headers: dict | None = None, timeout: int = 60):
    """http.client roundtrip, 200-299 -> parsed body, else RuntimeError(HTTP n).

    urllib is NOT used here: its HTTPError path raised
    'ValueError: I/O operation on closed file' in this unprivileged LXC
    (verified live 2026-10-18), masking the real status.
    """
    host, port = _host_port()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=_headers(body, extra_headers))
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status
    finally:
        conn.close()
    parsed = _json_or_text(raw)
    if 200 <= status < 300:
        return status, parsed
    detail = parsed if isinstance(parsed, str) else json.dumps(parsed)[:200]
    raise RuntimeError(f"HTTP {status} from {path}: {detail}")


def api(path: str, *, method: str = "GET", body: dict | None = None, timeout: int = 60):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    return _roundtrip(method, path, data, None, timeout)[1]


def api_binary(path: str, *, timeout: int = 60) -> bytes:
    host, port = _host_port()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path, headers=_headers(None))
        resp = conn.getresponse()
        status = resp.status
        raw = resp.read()
        if not 200 <= status < 300:
            raise RuntimeError(f"HTTP {status} from {path}: {raw[:200]}")
        return raw
    finally:
        conn.close()


def post_document(path: str, *, title: str | None = None, timeout: int = 120) -> dict:
    """POST /api/documents/post_document/ (multipart) → {"task_id": ...}."""
    boundary = f"iowap{uuid.uuid4().hex}"
    fname = os.path.basename(path)
    chunks: list[bytes] = []

    def field(name: str, content: str | None = None, is_file: bool = False):
        disp = f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
        if is_file:
            disp += f"; filename=\"{fname}\""
        prefix = disp + "\r\n\r\n"
        blob = open(path, "rb").read() if is_file else (content or "").encode("utf-8")
        chunks.append(prefix.encode("utf-8") + blob + b"\r\n")

    field("document", is_file=True)
    if title:
        field("title", title)
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    host, port = _host_port()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("POST", "/api/documents/post_document/", body=body,
                     headers=_headers(body, headers))
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status >= 300:
            raise RuntimeError(f"HTTP {resp.status} from post_document: {raw[:200]}")
        out = json.loads(raw or b"{}")
        # Paperless >= 2.x antwortet teils mit der nackten UUID als JSON-String
        # (statt {"task_id": ...}) — beide Formen akzeptieren.
        if isinstance(out, str):
            return {"task_id": out}
        return out
    finally:
        conn.close()


def poll_consume_task(task_id: str, *, timeout: int = 180) -> dict:
    """Consume status lives in /api/tasks/ — success carries related_document_ids."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = api(f"/api/tasks/?task_id={urllib.parse.quote(task_id)}")
        results = out.get("results") or []
        if results:
            task = results[0]
            status = (task.get("status") or "").lower()
            if status == "success":
                rids = task.get("related_document_ids") or []
                if rids:
                    return {"ok": True, "doc_id": rids[0]}
                return {"ok": False, "error": "consume succeeded but task carried no related_document_ids"}
            if status in ("failure", "failed"):
                return {"ok": False, "error": f"consume task failed: {task.get('result')}"}
        time.sleep(2.0)
    return {"ok": False, "error": f"consume task poll timed out after {timeout}s"}


def read_stdin() -> dict:
    return json.load(sys.stdin)


def emit(result: dict) -> None:
    print(json.dumps({"status": "completed", "result": result, "error": None}))


def fail(message: str) -> None:
    print(json.dumps({"status": "error", "result": None, "error": message}))