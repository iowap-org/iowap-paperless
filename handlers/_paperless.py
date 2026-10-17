#!/usr/bin/env python3
"""Shared Paperless REST client for iowap-paperless handlers (T-232).

Auth: `Authorization: Token <key>` (NOT Bearer). post_document answers
only {"task_id": ...} — the doc id arrives later via related_document_ids
inside the consume task; poll it with poll_consume_task().
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid


def cfg() -> tuple[str, str]:
    base = os.environ.get("PAPERLESS_URL", "http://127.0.0.1:8000").rstrip("/")
    tok = os.environ.get("PAPERLESS_TOKEN", "")
    return base, tok


def _request(path: str, *, method: str = "GET", data: bytes | None = None,
             headers: dict | None = None, timeout: int = 30):
    base, tok = cfg()
    h = {"Authorization": f"Token {tok}"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(f"{base}{path}", data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp


def api(path: str, *, method: str = "GET", body: dict | None = None, timeout: int = 30):
    data = None
    headers = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
    with _request(path, method=method, data=data, headers=headers, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else {}


def api_binary(path: str, *, timeout: int = 60) -> bytes:
    with _request(path, timeout=timeout) as resp:
        return resp.read()


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
    with _request("/api/documents/post_document/", method="POST",
                  data=body, headers=headers, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


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