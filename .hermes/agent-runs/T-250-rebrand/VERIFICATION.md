# T-250 — iowap-paperless Verification

- py_compile OK on paperless_watch.py.
- grep sweep post-edit: repo has zero `node-cli` refs outside gitignored novaforge/.
- NODE_CLI override preserved at paperless_watch.py:26; compose.yml sets no NODE_CLI → new default applies.
- Diff: 3 files, +5/−4 (README.md, compose.yml, handlers/paperless_watch.py).
- CI check: no `.github/workflows`, gh run list for iowap-org/iowap-paperless empty → no CI, noted.
- Push verified: `0c8ca03..a580d55 main -> main`.
