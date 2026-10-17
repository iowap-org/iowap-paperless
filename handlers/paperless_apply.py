#!/usr/bin/env python3
"""paperless.apply — write back flow verdicts: title and/or tags (T-232).

Called as the LAST step of the document-ingest flow with the values the
AI step produced. correspondent goes through its own name→id map; pass
null to skip.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _paperless import api, emit, fail, read_stdin  # noqa: E402


def main() -> None:
    data = read_stdin()
    inp = data.get("input") or {}
    doc_id = inp.get("doc_id")
    if not isinstance(doc_id, int):
        fail("doc_id (integer) required")
        return
    patch: dict = {}
    title = inp.get("title")
    if title:
        patch["title"] = str(title)
    tags = inp.get("tags")
    if isinstance(tags, list):
        names = {t["name"]: t["id"] for t in api("/api/tags/").get("results", [])}
        resolved = [t if isinstance(t, int) else names.get(t) for t in tags]
        missing = [t for i, t in enumerate(tags) if resolved[i] is None]
        if missing:
            fail(f"unknown tag names {missing} (Paperless tag-creation is out of scope)")
            return
        patch["tags"] = list(dict.fromkeys(resolved))  # preserve order, dedupe
    else:
        patch["tags"] = None  # explicit signal: don't touch tags — keep from dict
        patch.pop("tags")
    correspondent = inp.get("correspondent")
    if correspondent:
        corr = {c["name"]: c["id"] for c in api("/api/correspondents/").get("results", [])}
        cid = corr.get(str(correspondent)) if not isinstance(correspondent, int) else correspondent
        if cid is None:
            fail(f"unknown correspondent {correspondent!r} (create it or pass null)")
            return
        patch["correspondent"] = cid
    if not patch:
        fail("nothing to apply (pass title, tags and/or correspondent)")
        return
    api(f"/api/documents/{doc_id}/", method="PATCH", body=patch)
    emit({"doc_id": doc_id, "applied": {k: patch[k] for k in patch}})


main()