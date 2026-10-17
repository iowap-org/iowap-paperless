#!/usr/bin/env python3
"""doc.process — LLM verdict for a document (NovaForge, T-232).

Input (paperless-watch flow step): document_text (OCR text), filename,
pdf (optional transfer envelope — informational in V1, the verdict works
from the text). Calls the local Hermes API Server (agent.ai pattern:
http://127.0.0.1:8642/v1/chat/completions, Bearer API_SERVER_KEY) with a
JSON-only instruction; fenced output is tolerated and stripped.

Result: {title, tags[], correspondent?, summary, confidence}.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

PROMPT = (
    "You file scanned documents for a home documentation system. Read the "
    "document text below and answer with ONLY a JSON object, no markdown, "
    "no extra keys:\n"
    '{"title": "<short descriptive title, German>", "tags": ["<2-5 short lowercase tags, German>, '
    '"correspondent": "<sender/company or null>", "summary": "<one sentence>", "confidence": <0-100>}\n\n'
    "DOCUMENT"
)


def strip_fences(raw: str) -> str:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    return m.group(1) if m else raw


def main() -> None:
    data = json.load(sys.stdin)
    inp = data.get("input") or {}
    text = (inp.get("document_text") or "")[:6000]
    name = inp.get("filename") or "document"
    if not text.strip():
        print(json.dumps({"status": "error", "result": None,
                          "error": "document_text empty — OCR text required"}))
        return
    key = os.environ.get("API_SERVER_KEY", "")
    body = json.dumps({
        "messages": [{"role": "user",
                      "content": f"{PROMPT} ({name}):\n\n{text}"}],
        "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8642/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        answer = json.loads(resp.read())
    raw = answer["choices"][0]["message"]["content"]
    try:
        verdict = json.loads(strip_fences(raw))
    except ValueError as exc:
        print(json.dumps({"status": "error", "result": None,
                          "error": f"model returned non-JSON verdict ({exc}); raw tail: {raw[-200:]!r}"}))
        return
    result = {"title": verdict.get("title"), "tags": verdict.get("tags") or [],
              "correspondent": verdict.get("correspondent"),
              "summary": verdict.get("summary"), "confidence": verdict.get("confidence")}
    if not result["title"] or result["tags"] is None:
        print(json.dumps({"status": "error", "result": None,
                          "error": f"verdict missing title/tags: {verdict}"}))
        return
    print(json.dumps({"status": "completed", "result": result, "error": None}))


main()