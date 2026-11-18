# T-250 — iowap-paperless Rebrand status

## Done
- `handlers/paperless_watch.py`:26 — default `CLI = os.environ.get("NODE_CLI", "iowap-cli")` (env override kept).
- Docstring :12 + compose.yml:9 + README.md:65 — node-cli → iowap-cli comments/examples.
- `python3 -m py_compile handlers/paperless_watch.py` OK.
- Commit `a580d55` pushed to origin/main.

## Not done / flagged
- **No CI in iowap-paperless** — no `.github/` dir, `gh run list` empty. Rebrand ships via iowap-node-base image refresh (`ghcr.io/iowap-org/iowap-node-base:latest`, compose pins `:latest`), NAS recreate needed to take effect — out of scope here.
- `novaforge/node.yaml:3-4` still comment `node-cli capabilities …` — **gitignored (machine-specific, .gitignore:7)**, intentionally not touched.
- No test suite in repo (handlers run inside base image).
