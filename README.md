# iowap-paperless

Document-management node for the [IOWAP mesh](https://github.com/iowap-org/iowap)
— wraps a Paperless-ngx instance as capabilities so agents file and
question documents through the standard seven MCP tools. No new MCP
server needed; the mesh extends instead.

The centerpiece is the **document-ingest pipeline** (a finished flow):

```
paper in consume dir → Paperless consumes it (Tesseract OCR, deu+eng)
  → node sees the successful consume task (API poll, no inotify)
  → fetches doc + content, hp-puts the PDF as an artifact
  → submits flow.run(document-ingest):
      step 1  doc.process (AI verdict: title, tags, correspondent)
      step 2  paperless.apply (writes title/tags back, doc_id from step 1)
  → paper is filed automatically, without any agent being involved
```

The paperless node carries both endpoint roles of the pipeline — watcher
(ingest) and writer (apply) — while the thinking happens on `doc.process`
(run on NovaForge, an LLM-based verdict via the Hermes API Server).

## Capabilities (this node)

| Capability | Purpose | result fields |
|---|---|---|
| `paperless.upload` | POST a local file to `post_document/`, poll the consume task to the doc id | `doc_id` |
| `paperless.search` | query documents (title/content), tag names resolved | `count`, `documents[]` |
| `paperless.tag` | append/replace tags by name or id on a doc | `doc_id`, `tag_ids` |
| `paperless.apply` | write flow verdicts (title + tags + optional correspondent) into a doc | `doc_id`, `applied` |
| `paperless.inbox` | count docs under the inbox tag (`PAPERLESS_INBOX_TAG`) | `inbox_tag`, `count` |
| `paperless.watch` | **long_run** ingest starter: consume-poll → artifact → flow-submit → keepalive notes | — |

Full handler contract (stdin JSON envelope, stdout result envelope):
[iowap-node handler contract](https://github.com/iowap-org/iowap-docs/blob/main/node/handlers/contract.md).

## The `doc.process` partner capability (NovaForge)

`novaforge/node.yaml` + `novaforge/doc_process.py` — merge the block into
the NovaForge node's profile and publish. It asks the local Hermes API
Server (the `agent.ai` pattern: `http://127.0.0.1:8642/v1/chat/completions`,
Bearer `API_SERVER_KEY`) for a strict-JSON verdict; fenced output is
stripped. Result fields: `title`, `tags[]`, `correspondent`, `summary`,
`confidence`.

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