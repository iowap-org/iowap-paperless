# iowap-paperless

Document-management node for the [IOWAP mesh](https://github.com/iowap-org/iowap).
It wraps a Paperless-ngx instance as ordinary IOWAP capabilities — no MCP
server, no new protocol on this node: tasks arrive through the standard IOWAP
claim/SSE path, handlers talk to the local Paperless API.

The centerpiece is the **document-ingest pipeline** (a finished flow):

```text
paper in consume dir → Paperless consumes it (Tesseract OCR, deu+eng)
  → node sees the successful consume task (API poll, no inotify)
  → fetches doc + content, http-puts the PDF as an artifact
  → submits flow.run(document-ingest):
      step 1  doc.process (AI verdict: title, tags, correspondent)
      step 2  paperless.apply (writes title/tags back, doc_id from step 1)
  → paper is filed automatically, without any agent being involved
```

End-to-end the pipeline touches seven capabilities across two nodes: six on
this node (`paperless.upload/search/tag/apply/inbox/watch`) plus the
`doc.process` verdict capability on NovaForge. Only step 1 is agent software —
the ingest watcher, artifact transfer and file-back happen without any agent
in the loop.

## Roles and local infrastructure

| Piece | Where | What it does |
| --- | --- | --- |
| Paperless-ngx (OCR deu+eng) | CT 106 | consumes paper, produces text |
| iowap-paperless node | CT 106 | watcher + writer role |
| NovaForge node | Mac mini | `doc.process` LLM verdict |
| relay | LXC 903 | routes tasks, carries artifacts, runs the flow |

The NovaForge verdict asks the local Hermes API Server (not MCP: a direct
`agent.ai`-pattern HTTP call,
`http://127.0.0.1:8642/v1/chat/completions`, Bearer `API_SERVER_KEY`) for a
strict-JSON verdict; fenced output is stripped. The key lives only in the
NovaForge environment. Result fields: `title`, `tags[]`, `correspondent`,
`summary`, `confidence`.

## Capabilities (this node)

| Capability | Purpose | result fields |
| --- | --- | --- |
| `paperless.upload` | POST to `post_document/`, poll to doc | `doc_id` |
| `paperless.search` | search by title/content | `count`, `documents[]` |
| `paperless.tag` | append/replace tags by name or id | `doc_id`, `tag_ids` |
| `paperless.apply` | write verdicts into a doc | `doc_id`, `applied` |
| `paperless.inbox` | count docs under inbox tag | `inbox_tag`, `count` |
| `paperless.watch` | **long_run** ingest starter | — |

The node runs in the Paperless compose network. `upload` polls the
consume task to its doc id; `watch` runs
consume-poll → artifact upload → flow-submit → keepalive notes until
stopped. The full handler contract (stdin envelope, stdout envelope) lives
in iowap-docs at `node/handlers/contract.md`.

## Deploy (CT 106, next to Paperless)

```bash
docker compose -p iowap-paperless -f compose.yml up -d
# approve the node in the relay dashboard once
# start the ingest watcher (long_run task — runs until stopped):
docker compose exec iowap-paperless node-cli task submit --stage 'paperless.watch:{"input":{}}'
```

Env: `PAPERLESS_URL` (default `http://paperless:8000` in the compose
network), `PAPERLESS_TOKEN` (required), `PAPERLESS_INBOX_TAG` (default
`Posteingang`), `IOWAP_INGEST_TASK` (the fixed flow task text —
placeholders `{doc_id} {title} {name} {text}`).

## Honest notes

- Paperless does its own OCR on consume (Tesseract, `deu+eng`) — the
  pipeline reads that text and does NOT run a second OCR. Hard cases
  (handwriting, layout chaos) are a planned V2: a VLM-OCR capability on
  the Mac mini node.
- Tag/correspondent CREATION is out of scope: names must already exist
  in Paperless (deterministic writes only).
- The ingest task text is fixed but planner-planned (agent.ai proposes
  the steps live); after the first live run, promote the kept plan into
  a catalog flow (`mode: save_flow`) for a stable repeatable pipeline.
