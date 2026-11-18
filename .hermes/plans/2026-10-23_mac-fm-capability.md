# Mac-Mini-Node: Apple Foundation Models als IOWAP-Capability

Stand 23.10.2026 · Ziel: on-device, privat, 0 Cloud-Kosten — erste Use-Cases
`doc.process` (Paperless) lokal + Paperless-V2-OCR, optional Hermes-Provider.

## Verifizierter Ist-Stand (live auf dem Mac 100.64.0.5, 23.10.)

| Check | Ergebnis |
|---|---|
| Host | macOS 27.0.1, Apple M4, 16 GB RAM, `/usr/bin/fm` vorhanden (CLI im OS) |
| `fm available` | „System model available" |
| `fm respond 'Antworte in einem Satz: Was ist 3 plus 4?'` | „3 plus 4 ist 7." — **1,2 s**, on-device, deutschsprachig |
| `fm serve --port 1976` | OpenAI-kompatibel: `/health`, `/v1/models` (id `system`), `/v1/chat/completions` (SSE-Streaming) — live getestet, Test-Server danach gestoppt |
| `fm schema object --name DocVerdict --string title --string tags --int pages` | valides JSON-Schema (`additionalProperties: false`) → **schema-getriebene Extraktion** |
| `fm count-tokens 'Hallo Welt'` | 3 (Token-Zählung verfügbar) |
| Python-SDK `apple-fm-sdk` (pip) | existiert — Requirements: macOS 26+ **und Xcode 26+** + SDK-Agreement; **auf dem Mac ist kein Xcode installiert** → Weg B gesperrt |
| Utilities-Package | Swift (Apple + Ubuntu): custom skills, context-management helpers, ChatCompletions-Client → Swift-only, ohne Xcode nutzlos |

## Zwei Integrationswege

**Weg A (empfohlen, heute machbar, ohne Xcode):** iowap-node-Handler auf dem Mac
ruft `fm respond` / `fm schema` / `fm serve` per Subprocess; Result als normaler
IOWAP-Task-Result.

- `mac.fm.chat` — Text → Text (Streaming optional)
- `mac.fm.extract` — Text → JSON nach Schema (`fm schema` → Guided Generation)
- `mac.fm.ocr` — Bild/PDF → Text (AFM image understanding + Vision-OCR;
  **Bild-Eingabe via `fm` erst verifizieren**, Annahme nicht belegt)

**Weg B (optional):** Python-SDK in-process (sauberer, kein Subprocess) —
Voraussetzung: Xcode 26+ installieren + Xcode/SDK-Agreement akzeptieren.
**Ronny-Entscheidung** (Installationsgröße, Agreement, Update-Last).

## Pflicht-Schritte

1. **Node-Spec + `node.yaml`** auf dem Mac-Mini (analog iowap-storage / iowap-flow),
   Handler `handlers/fm_*.py` mit Envelope-Contract (stdin JSON → stdout result).
2. **A/B-Messung `doc.process`**: lokales AFM vs. aktueller Hermes-API-Server
   (GLM-5.3) auf 20–30 echten Paperless-Dokumenten — Titel/Tags/Correspondent
   als JSON; Precision/Recall + Latenz + Kosten. **Ohne diese Messung kein
   Umbau der Pipeline** (3B-On-Device ≠ Cloud-Modell).
3. **Datenschutz als Kriterium:** Dokumente verlassen den Mac nicht — für
   Rechnungen/Verträge ein echtes Auswahlargument.
4. **AUM / Legal Notice:** `fm license` — **rechtliche Entscheidung → Ronny,
   nicht der Worker.** Private Cloud Compute (Claude/Gemini) ist für uns nicht
   nutzbar (App-Store-Small-Business-Programm + <2M First-time-Downloads) →
   nur on-device.

## Haken und Risiken

- **RAM-Konkurrenz** auf dem 16-GB-Mac: mflux-Node + Ollama-Reserve + Hermes.
  AFM-Inferenz belegt RAM/ANE — mit dem mflux-Node (Video) konkurrieren.
- **Latenz bei langen Dokumenten:** 1,2 s galt für ein Ein-Satz-Prompt. Ein
  10k-Zeichen-Dokument ist ungetestet → messen (`count-tokens` + Zeit).
- **Betrieb:** `fm serve` als launchd-Dienst nötig — oder direkt `fm respond`
  ohne Server (einfacher, kein Port, kein Health-Check).
- **Qualitätsgrenze:** On-Device (~3B) reicht für Extraktion/OCR/Klassifikation,
  nicht für Agentik/Mehrschritt-Verdicts. `doc.process` (Titel/Tags/Correspondent
  aus OCR-Text) liegt in der passenden Klassengröße.
- **Kein Xcode** = der native Python-Weg ist zu (kein Xcode vorhanden).

## Abhängigkeiten

`iowap-paperless` (doc.process-Partner auf NovaForge — siehe deren README-Block
`The doc.process partner capability`), `iowap-node` (Handler-Contract,
Envelope v2), Deployment des Mac-Mini-Nodes (Daemon/launchd).
