# Issue #106 / AP1 – Baseline-Runbook

Issue: #111  
Parent: #106  
Contract: `docs/planning/ISSUE_106_PERFORMANCE_CONTRACT.md`

## Ziel

AP1 misst den unveränderten Post-AP4-Investigation-Pfad. Es werden **keine
Performance-Optimierungen** vorgenommen.

Die Baseline besteht aus fünf Golden-Set-Fällen mit je fünf Wiederholungen. Jeder Slot
besitzt einen eigenen `ProcessAnalysis`- und Snapshot-Kontext, damit insbesondere
`WAITING_HUMAN` als unveränderter Rohzustand erhalten bleiben kann.

Historische AP4-Runs werden nicht in die 5×5-A/A-Population gemischt.

## 1. Voraussetzungen

Der Checkout muss sauber und committed sein. Alle 25 Runs müssen auf demselben Commit
laufen.

Benötigte Konfiguration:

```text
OPENROUTER_API_KEY=<secret>
OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash

ISSUE106_PRICE_INPUT_PER_MILLION=<aktuelle Preisbasis>
ISSUE106_PRICE_OUTPUT_PER_MILLION=<aktuelle Preisbasis>
ISSUE106_PRICING_CURRENCY=USD
ISSUE106_PRICING_VERSION=<Quelle/Datum oder andere eindeutige Versionskennung>
```

Die Preiswerte dienen der bestehenden persistenten EvidenceCampaign-Budgetierung.
Der Provider meldet den tatsächlichen Verbrauch je Call; dieser wird über
`InvestigationProviderReservation.actual_cost_microunits` exportiert.

## 2. Slots vorbereiten

Der Prepare-Schritt startet **keinen** Provider-Call:

```powershell
uv run python manage.py prepare_issue106_baseline
```

Er erzeugt genau 25 isolierte Baseline-Slots:

```text
AP4-01 R1..R5
AP4-02 R1..R5
AP4-04 R1..R5
AP4-05 R1..R5
AP4-06 R1..R5
```

Nochmaliges Ausführen ist erlaubt, solange die eingefrorenen Slots unverändert sind.

## 3. Reale Baseline ausführen

Alle noch leeren Slots seriell:

```powershell
uv run python manage.py run_issue106_baseline --all --confirm-real-provider
```

Oder genau ein Slot:

```powershell
uv run python manage.py run_issue106_baseline --case AP4-01 --repeat 1 --confirm-real-provider
```

Schutzregeln:

- dirty worktree → Abbruch;
- anderer Commit als bereits vorhandene Baseline-Runs → Abbruch;
- bereits belegter Slot → keine neue Provideranfrage;
- gleichzeitig RUNNING Baseline-Run → Abbruch;
- aktueller Source-Pack-Hash weicht vom AP0-Contract ab → Abbruch;
- globales AP1-Providerkostenbudget von 20 USD wird über persistierte Reservations
  vor jedem neuen Slot berücksichtigt;
- FAILED, langsame und WAITING_HUMAN-Runs bleiben erhalten.

## 4. Rohdaten und Review-Vorlage exportieren

```powershell
uv run python manage.py export_issue106_baseline
```

Erzeugt standardmäßig:

- `artifacts/issue106/ap1/baseline.json`
- `artifacts/issue106/ap1/review.json`

`baseline.json` enthält je Run unter anderem:

- aktive Investigation-Laufzeit;
- Model-/Non-Model-Zeit;
- Planner-/Synthesizer-/Verifier-Aufrufe;
- Prompt-/Completion-/Reasoning-Tokens;
- Call-Limits und Context-Metadaten;
- Tool-Zeiten und doppelte Reads;
- tatsächliche Providerkosten je Call/Rolle/Run;
- Repair-/Retry-/Fehlerindikatoren;
- Quellenabdeckung, Counterevidence, Critical Claims, Unknowns und Human Escalation;
- exakten getesteten Commit und Execution Contract.

Bei `WAITING_HUMAN` endet die aktive Runtime am gespeicherten Übergang in diesen
Zustand; spätere menschliche Wartezeit wird nicht addiert.

## 5. Menschliche Qualitätsbewertung

Die Review-Datei enthält für jeden Run:

- erwartete Schlüsselfunde;
- notwendige Gegenbelege;
- die sechs semantischen Rubrikpunkte;
- Hard-Fail-Markierung.

Zulässige Werte:

```text
pass
fail
unassessed
```

Für den finalen AP1-Abschluss müssen alle Runs autoritativ bewertet sein.
`unassessed` darf nicht als bestanden interpretiert werden.

Nach ausgefüllter Review-Datei:

```powershell
uv run python manage.py export_issue106_baseline \
  --assessments artifacts/issue106/ap1/review.json \
  --require-complete
```

## 6. A/A-Auswertung

Für jeden Fall werden aus den fünf Runs mindestens berechnet:

- Median aktive Runtime;
- MAD;
- `2 × MAD` als vorab definierter Engineering-Noise-Floor;
- Min/Max;
- Statusverteilung;
- Kosten;
- Timeout-/Retry-/Repair-Rate.

Es werden keine p95- oder Signifikanzbehauptungen aus fünf Wiederholungen abgeleitet.

## 7. AP1-Exit

#111 darf erst geschlossen werden, wenn:

1. alle 25 Slots als Rohdaten vorliegen;
2. die A/A-Auswertung erzeugt wurde;
3. die menschliche Qualitätsbewertung vollständig ist;
4. Providerkosten, Fehler/Retry/Repair und nicht beobachtbare Größen dokumentiert sind;
5. die Artefakte den exakten getesteten Commit nennen;
6. keine Performance-Änderung Teil dieses Arbeitspakets war.

Erst danach beginnt #112 mit der Kandidatenentscheidung.
