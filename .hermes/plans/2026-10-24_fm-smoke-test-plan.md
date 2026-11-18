# Smoke-Test-Plan: fm.chat / fm.extract / fm.ocr (Relay-Seite, noch NICHT ausgeführt)

Stand 24.10.2026 · Vorbereitung abgeschlossen, Ausführung erst nach Freigabe
(Agent meldet „ready" + Run-2-Bericht liegt vor).

## Ausgangslage (verifiziert, read-only)

- Capabilities am Relay publiziert, Owner = **NovaForge `RYBFNMET`** (online, queue 0).
- `fm.chat` v1.1.0 · `fm.extract` v1.1.0 · `fm.ocr` v1.1.0
- Handler auf dem Mac: `~/.relay/handlers/fm_{chat,extract,ocr}.py` (Stand 10:30–10:33, Run 2)
- `~/.relay/node.yaml` 10:33:55 (v1.1.0)
- Ausführung über die IOWAP-MCP-Tools (`task_submit` + `task_result`), Target-Capability
  mit `owner_node_id=RYBFNMET` (Mac-Node), damit der Task dort landet.

## Test 1 — fm.chat (Basispfad)

```json
{
  "capability": "fm.chat",
  "owner_node_id": "RYBFNMET",
  "payload": {
    "prompt": "Antworte in einem Satz: Was ist 3 plus 4?"
  }
}
```
**Erwartung:** `result.answer` enthält „7"; `result.model` = `system`;
`result.tokens_out` > 0; `result.latency_ms` < 30.000. Kein `chunked` (Input klein).

## Test 2 — fm.extract (native Schema-Route)

```json
{
  "capability": "fm.extract",
  "owner_node_id": "RYBFNMET",
  "payload": {
    "text": "Mietvertrag Wohnung 3b am Stadtpark, 12 Seiten, Autor Anna Weber,_keywords: miete, wohnung",
    "fields": {
      "titel": { "type": "string" },
      "seiten": { "type": "integer" },
      "autor": { "type": "string" }
    }
  }
}
```
**Erwartung:** `result.json` ist **valides JSON** (Prüfung: `json.loads`, nicht per Augen),
mit `titel`/`seiten`/`autor`; `seiten` ist ein **Integer** (nicht String) — das ist der
Test der nativen Schema-Erzeugung; `result.schema_tokens` > 0.

## Test 3 — fm.ocr (Bild-Pfad)

```json
{
  "capability": "fm.ocr",
  "owner_node_id": "RYBFNMET",
  "payload": {
    "image_path": "/tmp/fm_ocr_test.png",
    "mode": "text"
  }
}
```
**Erwartung:** `result.text` enthält die 4 Rechnungszeilen des Testbilds;
`result.model` = `system`; `result.latency_ms` < 30.000.
**Vorbedingung:** Datei muss auf dem Mac existieren (`/tmp/fm_ocr_test.png` — laut
Run-1-Bericht vorhanden; **vorher auf dem Mac prüfen**, `/tmp` wird bei Reboot geleert).

## Test 4 — Token-Grenze (der eigentliche Run-2-Zweck)

```json
{
  "capability": "fm.chat",
  "owner_node_id": "RYBFNMET",
  "payload": {
    "prompt": "<ca. 8.000 Zeichen Text, auf dem Mac als Fixture erzeugen und hier einsetzen>"
  }
}
```
**Erwartung:** `result.chunked` = true, `result.chunks` > 1, `result.strategy` benannt,
Antwort inhaltlich sinnvoll, **kein** stillschweigender Datenverlust.
**Vorbedingung:** 8k-Fixture auf dem Mac anlegen (Agent-Run 2 hat evtl. eins erzeugt —
Pfad vorher erfragen/prüfen, nicht erfinden).

## Abbruch- und Meldekriterien

- Bei Timeout/Fehler: **exakte Relay-Fehlermeldung** notieren, Task-Result mitnehmen.
- Bei `result.chunked` fehlend obwohl Input > 3400 Token: Das ist ein **Befund**, kein
  Testfehler → melden, nicht „reparieren“.
- Nicht testen in diesem Durchgang: doc.process-Umstieg, Paperless-Anbindung,
  Vergleich gegen Hermes-API-Server (A/B-Messung), Performance unter Parallel-Last.

## Reihenfolge

1. Vorbedingungen auf dem Mac prüfen (Testbild vorhanden? 8k-Fixture?).
2. Test 1 → Test 2 → Test 3 → Test 4.
3. Pro Task: task_submit, dann task_result abholen, Rohresultat festhalten.
4. Bericht: 4 × (Befehl, Payload, Rohresultat, Bewertung gegen Erwartung).
