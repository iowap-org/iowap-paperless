#!/usr/bin/env python3
"""paperless.inbox — count documents in the configured inbox tag (T-232)."""
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paperless import api, emit, fail, read_stdin  # noqa: E402


def main() -> None:
    read_stdin()
    inbox_tag = os.environ.get("PAPERLESS_INBOX_TAG", "Posteingang")
    names = {t["name"]: t["id"] for t in api("/api/tags/").get("results", [])}
    if inbox_tag not in names:
        fail(f"inbox tag {inbox_tag!r} not found in Paperless (set PAPERLESS_INBOX_TAG)")
        return
    out = api(f"/api/documents/?tags={names[inbox_tag]}&page_size=1")
    emit({"inbox_tag": inbox_tag, "count": out.get("count", 0)})


main()