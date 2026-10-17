#!/usr/bin/env python3
"""paperless.search — query documents, resolve tag names (T-232)."""
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paperless import api, emit, read_stdin  # noqa: E402


def main() -> None:
    data = read_stdin()
    inp = data.get("input") or {}
    query = (inp.get("query") or "").strip()
    limit = max(1, min(int(inp.get("limit") or 10), 100))
    params = [f"page_size={limit}"]
    if query:
        params.append(f"query={urllib.parse.quote(query)}")
    out = api("/api/documents/?" + "&".join(params))
    tag_names = {t["id"]: t["name"] for t in api("/api/tags/").get("results", [])}
    docs = []
    for d in out.get("results", [])[:limit]:
        docs.append({
            "id": d.get("id"),
            "title": d.get("title"),
            "tags": [tag_names.get(tid, tid) for tid in (d.get("tags") or [])],
            "created": d.get("created"),
        })
    emit({"count": out.get("count", len(docs)), "documents": docs})


main()