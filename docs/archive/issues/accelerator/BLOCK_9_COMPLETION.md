# Block 9 – Abschlussnachweis AP 9 und AP 10

**Messvertrag:** `block9-v2`

**Kanonischer Fixture-Hash:** `d4f7431ac68bb94b05885ae25f323e4147cf68fb20977ecd18c2acdeef74e6d1`

**Gewertetes Modell:** `openai/gpt-5-mini` über OpenRouter

**Rohdaten:** `artifacts/block9/raw-interactive.jsonl`, `artifacts/block9/raw-technical.jsonl`

**Maschinenlesbare Auswertung:** `artifacts/block9/ap10-summary.json`

## Ergebnis

Die sieben gewerteten Slots wurden in der eingefrorenen Reihenfolge und ohne Ersatz eines
fehlgeschlagenen Erstversuchs ausgeführt. Der manuelle A-Pfad erreichte in allen drei Läufen den
21/21-Endzustand. Der Accelerator erreichte ihn in zwei von drei A-Läufen; der zweite A-Slot
scheiterte mit `invalid_extraction`. Auch der Robustheitslauf B scheiterte mit
`invalid_extraction`. Damit ist die Messung abgeschlossen, belegt aber **keinen
Beschleunigungsvorteil und keine hinreichend stabile Modellzuverlässigkeit**.

| Slot | Status | End-to-End | Fachliches Ergebnis |
|---|---:|---:|---|
| `manual-A-1` | abgeschlossen | 80,654 s | 21/21 |
| `accelerator-A-1` | abgeschlossen | 306,471 s | 21/21 |
| `accelerator-A-2` | fehlgeschlagen | 98,522 s | `invalid_extraction`, kein Retry |
| `manual-A-2` | abgeschlossen | 11,048 s | 21/21 |
| `manual-A-3` | abgeschlossen | 10,087 s | 21/21 |
| `accelerator-A-3` | abgeschlossen | 245,952 s | 21/21 |
| `accelerator-B-1` | fehlgeschlagen | 99,722 s | `invalid_extraction`, kein Retry |

## AP-10-Auswertung

### Zeiten und Erfolgsrate

Für A beträgt der Manual-Median 11,048 s (Minimum 10,087 s, Maximum 80,654 s). Der Median
der drei primären Accelerator-Slots einschließlich des fehlgeschlagenen Erstversuchs beträgt
245,952 s (Minimum 98,522 s, Maximum 306,471 s). Betrachtet man nur die beiden erfolgreichen
Accelerator-Läufe, beträgt der Median 276,2115 s. Der primäre Accelerator-Median liegt damit beim
22,262-Fachen des Manual-Medians. Die Accelerator-Erfolgsrate in A ist 2/3; die Fehlerrate 33,3 %.

Alle abgeschlossenen Einzelpfade blieben im kontrollierten Aufbau unter 30 Minuten. Wegen des
kleinen Samples, der Modellfehler und der deutlich längeren Accelerator-Zeit ist daraus weder eine
allgemeine Bedienbarkeits- noch eine Produktivitätsaussage abzuleiten.

### Qualität, Korrektur und Kosten

- Manual A: 63/63 korrekte Zielfelder, keine fachlichen Fehler.
- Accelerator A: 47/63 Felder über alle primären Slots; die erfolgreichen Läufe erreichten 42/42.
- In den erfolgreichen Accelerator-A-Läufen wurden 18 Vorschläge direkt und 8 bearbeitet
  übernommen; es gab keine Verwerfungen.
- Accelerator A: 3 LLM-Aufrufe, 24.563 Tokens, geschätzte LLM-Kosten 0,038980 USD,
  227.272 ms Providerdauer und 1 technischer Fehler.
- Alle vier gewerteten Accelerator-Slots: 32.640 Tokens, geschätzte LLM-Kosten 0,051802 USD,
  293.563 ms Providerdauer und 2 technische Fehler (50 %).

Die Kosten sind die vom Provider gelieferten, geschätzten LLM-Kosten in USD. Die Analyseansicht
benennt sie entsprechend; der unklare Begriff „Kostenwert“ wird nicht mehr verwendet.

### Robustheitsfall B

Die fehlende Support-Verantwortung blieb offen und es wurden keine Angaben zu Provider, Modell
oder Support erfunden. Der absichtlich veraltete Zielwertkonflikt konnte wegen
`invalid_extraction` nicht bis in den Review-Pfad gelangen und zählt deshalb als ein verpasster
Konflikt. Der Fehlschlag bleibt der gewertete Slot; es gab keinen Recovery-Ersatzlauf.

### Technische Kontrollen

Die bereits vor `block9-v2` erhobenen technischen Kontrollen bleiben unverändert als
`block9-v1` gekennzeichnet. Der Blueprint-Kontrolllauf endete nach 0,192325 s mit dem Checksum
`a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5`. Die drei
Delivery-Kontrollen hatten einen Median von 0,020315 s (Minimum 0,020126 s, Maximum 0,028886 s),
je 16 deterministische Felder, 0 LLM-Felder und 1 offene Lücke. Diese Werte sind technische
Kontrollen und keine interaktive Produktivitätsmessung.

## Modellhistorie und Limitationen

Die Warm-up-Diagnose begann mit DeepSeek-Modellen; schema-konforme Antworten scheiterten dabei
wiederholt an der zusätzlichen semantischen Extraktionsprüfung. Zwischenversuche mit Luna und
GPT-4.1 Mini erreichten ebenfalls keinen vollständigen Review-Pfad. Erst der Warm-up mit
`openai/gpt-5-mini` erreichte 21/21, weshalb ausschließlich dieses Modell in den gewerteten
Slots verwendet wurde. Das Ergebnis ist modellspezifisch; Laufzeit, Tokenmenge, Kosten,
Fehlerrate und Vorschlagsqualität sind nicht auf ein anderes Modell übertragbar.

Weitere Grenzen:

- ein einzelner systemkundiger, Codex-gestützter Browser-Operator; keine repräsentative
  menschliche Eingabe- oder Usability-Messung;
- lokaler Docker-Aufbau, kleines Sample (`n=3` für A je Hauptpfad) und Warm-up-/Lerneffekt;
- `manual-A-1` enthält einen längeren Review-/Werkzeugübergang;
- `accelerator-A-1` enthält zwei Browser-Verbindungsunterbrechungen; die Zeit blieb vollständig
  enthalten und Kategorien wurden aus persistierten HTTP-/Session-Zeitpunkten rekonstruiert;
- vorgebundene Capture-Sessions und eine reguläre Use-Case-Edit-Initialisierung sind als
  Protokollabweichungen in den Rohdaten ausgewiesen;
- kleine Timer-Bridge-Lücken wurden nicht geglättet; End-to-End-Zeiten blieben unverändert.

## Value-Stream-Ableitung

Der reale DEMO-Pfad „Use Case direkt aus Phase ableiten“ wurde zusätzlich geprüft. Er legt vor
dem Speichern noch keinen Use Case an, übernimmt aber aus der gewählten Value-Stream-Phase bereits
Titel, Business Unit, Problem, Domäne/Capability, betroffene Prozessphase, Zusammenfassung,
Zielnutzer und Quellsysteme. Business Owner werden mit Herkunft vorgeschlagen. Benefit,
Metriken, Datenquellen, Lösung und Human Oversight bleiben offen, wenn die Phase dafür keine
belastbare Information enthält. Nach erfolgreichem Anlegen wird die Herkunft über `UseCaseOrigin`
gespeichert. Die Ableitung nutzt bewusst die ausgewählte Phase und kopiert nicht pauschal den
gesamten Value Stream.

## Abnahme

- Fixture und Reihenfolge unverändert: erfüllt.
- Erster gewerteter Versuch zählt; keine Retry-Schleife: erfüllt.
- Rohdaten inklusive Zeiten, Qualität und LLM-Telemetrie unverändert gesichert: erfüllt.
- Manual- und Accelerator-Pfade real ausgeführt: erfüllt.
- Robustheitsfall mit Pflichtlücke und Zielwertkonflikt gewertet: erfüllt, mit dokumentiertem
  technischem Fehlschlag.
- Median/Minimum/Maximum, Qualität, Korrektur, Kosten und Fehler ausgewertet: erfüllt.
- Modellhistorie, Drift-/DEMO-Nachweis und Limitationen dokumentiert: erfüllt.
- Kein unbelegter Beschleunigungs- oder Zuverlässigkeitsclaim: erfüllt.

AP 9 und AP 10 sind damit methodisch abgeschlossen. Das Ergebnis ist ein negativer bzw. gemischter
Benchmarkbefund und kein Freigabenachweis für eine automatische, unbeaufsichtigte Übernahme.
