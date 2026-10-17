#!/usr/bin/env python3
"""paperless.upload — upload a local file into Paperless (T-232)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paperless import emit, fail, poll_consume_task, post_document, read_stdin  # noqa: E402


def main() -> None:
    data = read_stdin()
    inp = data.get("input") or {}
    path = (inp.get("path") or "").strip()
    title = (inp.get("title") or "").strip() or None
    if not path or not os.path.isfile(path):
        fail(f"path not found: {path!r}")
        return
    out = post_document(path, title=title)
    task_id = out.get("task_id")
    if not task_id:
        fail(f"post_document returned no task_id: {out}")
        return
    poll = poll_consume_task(task_id)
    if not poll.get("ok"):
        fail(poll.get("error") or "consume vanished")
        return
    emit({"doc_id": poll["doc_id"]})


main()