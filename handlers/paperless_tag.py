#!/usr/bin/env python3
"""paperless.tag — append/replace tags (by name or id) on a document (T-232)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paperless import api, emit, fail, read_stdin  # noqa: E402


def main() -> None:
    data = read_stdin()
    inp = data.get("input") or {}
    doc_id = inp.get("doc_id")
    tags = inp.get("tags") or []
    mode = (inp.get("mode") or "append").lower()
    if not isinstance(doc_id, int):
        fail("doc_id (integer) required")
        return
    if not tags:
        fail("tags[] required")
        return
    names = {t["name"]: t["id"] for t in api("/api/tags/").get("results", [])}
    resolved = []
    bad = []
    for tag in tags:
        if isinstance(tag, int):
            resolved.append(tag)
        elif tag in names:
            resolved.append(names[tag])
        else:
            bad.append(tag)
    if bad:
        fail(f"unknown tag names: {bad} (create them in Paperless first)")
        return
    current = []
    if mode == "append":
        current = list(api(f"/api/documents/{doc_id}/").get("tags") or [])
    merged = sorted(set(current) | set(resolved)) if mode == "append" else sorted(set(resolved))
    api(f"/api/documents/{doc_id}/", method="PATCH", body={"tags": merged})
    emit({"doc_id": doc_id, "tag_ids": merged})


main()