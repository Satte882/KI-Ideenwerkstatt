# #118 C2a: v20 Variant / echter v19 Control

Diese Anleitung beschreibt das spätere reale Experiment. **In C2a wurden keine
realen Provider-Runs ausgeführt.** Harness-Einführung ist keine Experimentmessung
und keine Übernahmeentscheidung. Parent #106 bleibt Entscheidungsgate.

## Eingefrorener Messvertrag

Experiment-ID: `issue106-exp118-source-coverage-v1`. Genau 20 Variant-Slots
(fünf Golden Cases × vier Wiederholungen), fünf Control-Slots und höchstens 25
primäre Runs. Kein Ersatzlauf. Auch FAILED, langsame und unterbrochene Runs bleiben
im Nenner und in der Population.

| Case | Vorab versionierte Reihenfolge |
|---|---|
| AP4-01 | V1 → C1 → V2 → V3 → V4 |
| AP4-02 | C1 → V1 → V2 → V3 → V4 |
| AP4-04 | V1 → C1 → V2 → V3 → V4 |
| AP4-05 | C1 → V1 → V2 → V3 → V4 |
| AP4-06 | V1 → C1 → V2 → V3 → V4 |

Variant läuft auf dem **dann gemergten C2a-Commit auf main**, Loop v20.
Control läuft ausschließlich auf `b37e25b6508a6e5769785c72c2fc35ac1177fae2`,
Loop v19. Alle anderen Prompt-, Schema-, Tool-, Policy-, Transport-, Modell-,
Timeout-, Reasoning-, Dependency- und Runtime-Eigenschaften bleiben gebunden.
Kein Zurücksetzen von Versionskonstanten. Keine Änderung des Quellbestands.

## 1. Zwei Checkouts vorbereiten

PowerShell, Pfade außerhalb des Repositorys für Messdateien. Das Control-Beispiel
ist austauschbar; der Harness hat keinen hardcodierten Checkout-Pfad.

```powershell
$ErrorActionPreference = 'Stop'
$variantRoot = 'C:\Users\user\Documents\GitHub\KI-Ideenwerkstatt'
$controlRoot = 'C:\Users\user\Documents\GitHub\KI-Ideenwerkstatt-control-v19'
$evidenceRoot = 'C:\Users\user\Documents\issue118-evidence'
Set-Location -LiteralPath $variantRoot
git fetch origin
if ($LASTEXITCODE -ne 0) { throw 'Fetch fehlgeschlagen' }
git switch main
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Main konnte nicht aktualisiert werden' }
if (git status --porcelain) { throw 'Variant-Worktree ist nicht sauber' }
$variantCommit = (git rev-parse HEAD).Trim()
# Vorher prüfen: Dies ist der gemergte C2a-Harness-Commit, nicht der alte C1-Stand.
git log -1 --oneline
if (-not (Test-Path -LiteralPath $controlRoot)) {
    git worktree add --detach $controlRoot b37e25b6508a6e5769785c72c2fc35ac1177fae2
    if ($LASTEXITCODE -ne 0) { throw 'Control-Worktree konnte nicht erstellt werden' }
}
git -C $controlRoot rev-parse HEAD
git -C $controlRoot status --porcelain
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
uv sync --frozen --dev
if ($LASTEXITCODE -ne 0) { throw 'Dependency-Setup fehlgeschlagen' }
$python = Join-Path $variantRoot '.venv\Scripts\python.exe'
$plan = Join-Path $evidenceRoot 'plan.json'
$fixtureProof = Join-Path $evidenceRoot 'c1-state-fixtures.json'
$experiment = Join-Path $evidenceRoot 'experiment.json'
$review = Join-Path $evidenceRoot 'review.json'
```

Beide Checkouts müssen beim Prepare und bei jedem Run sauber sein, einschließlich
unversionierter Dateien. Plan und JUnit-Proof liegen deshalb außerhalb beider
Checkouts. Keine `uv sync`-Änderungen an `uv.lock` zulassen. Dieselbe Variant-venv
führt auch die historische Control aus; im Control-Checkout wird nichts installiert
oder kopiert.

## 2. PostgreSQL und Isolation

**Gemeinsame bestehende PostgreSQL-Datenbank verwenden.** Nachweis am Ausgangsstand
`6f89e4fedc1e12ad96f1ef1894646b55f2f4d580`: Seit dem historischen Control-Commit
änderten sich produktiv nur `investigation_llm.py` und die Loop-Versionskonstante
in `investigation_runtime.py`. Alle Models, alle Migrationen sämtlicher Apps,
Settings, `pyproject.toml` und `uv.lock` sind identisch. Prepare prüft diesen
Nachweis erneut am tatsächlich getesteten Commit und verweigert inkompatible
Änderungen. Keine zusätzliche Migration und keine Volumenlöschung.

Getrennte ProcessAnalysis-/Snapshot-IDs, Campaign-/Idempotency-Keys enthalten Arm,
Case, Wiederholung und Experimentversion. Metadaten binden Experiment, Phase,
Arm, Commit, Source-Pack, Plan-Digest und Execution Contract. Run-Fortsetzung
prüft alle bestehenden Slots gegen diesen Plan. Der Produktworker selektiert
ausschließlich `evidence_campaign__isnull=True`; Evidence-Campaign-Runs gelangen
nicht in seine Queue, Claim- oder Reaper-Pfade (auch im v19-Code).

```powershell
# Bestehende lokale Konfiguration verwenden; keine Secrets in Dateien/Commits schreiben.
# Beide Arme erhalten dieselben Prozess-Environment-Variablen.
$env:DJANGO_SETTINGS_MODULE = 'config.settings.dev'
$env:DATABASE_URL = Read-Host 'Bestehende lokale PostgreSQL-URL'
$env:ISSUE106_OWNER_USERNAME = Read-Host 'Aktiver Benchmark-Owner'
& $python manage.py check
& $python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Schema-Prüfung fehlgeschlagen' }
```

Nicht `migrate` im historischen Checkout ausführen. Keine SQLite-Ausführung:
PostgreSQL-Advisory-Lock `(106,111)` schützt gleichzeitig beide #118-Arme und AP1.
Das ist bewusst derselbe Projekt-Lock wie im unveränderten AP1-Runner.
DB-Fingerprint ohne Passwort wird im Plan eingefroren. Unterschiedliche URLs,
DB-Namen oder Nutzer dürfen nicht still ein zweites Experiment-Ledger schaffen.

Die Runtime-Umgebung muss der AP1-Referenz entsprechen: Python, Django,
PostgreSQL-Version und lokale Dependency-Dateihashes werden geprüft. Abweichungen
führen zu einem erklärten Prepare-Abbruch und benötigen eine neue methodische
Entscheidung im Parent; Preise oder Umgebungswerte werden nicht angepasst, um
eine Prüfung zu umgehen.

## 3. Pricing einfrieren

Keine Beispielpreise. Aktuelle Accounting-Basis **vor** Prepare separat festlegen.
Der Provider-Istpreis bleibt unabhängige Evidence. Beide Arme nutzen dieselben vier
expliziten Werte; fehlende, negative, NaN- oder Infinity-Werte werden abgelehnt.

```powershell
$env:ISSUE106_PRICE_INPUT_PER_MILLION = Read-Host 'Freigegebener Inputpreis pro Million Token'
$env:ISSUE106_PRICE_OUTPUT_PER_MILLION = Read-Host 'Freigegebener Outputpreis pro Million Token'
$env:ISSUE106_PRICING_CURRENCY = 'USD'
$env:ISSUE106_PRICING_VERSION = Read-Host 'Eindeutige Version dieser Accounting-Basis'
```

Plan und Campaign-Budgetrevisionen binden diese Basis. Nachträgliches Pricing oder
Campaign-Cap-Erhöhen wird abgelehnt. Gemeinsam maximal **20 USD** für Variant und
Control, einschließlich offener/uncertain Reservierungen. Zusätzlich global
**60 USD für #106**. AP1 zählt nur global; aus Live-Ledger und archivierter
AP1-Kostensumme wird das Maximum verwendet, um restaurierte AP1-Historie weder
zu vergessen noch doppelt abzurechnen. Weitere #106-Ausgaben müssen in derselben
authoritativen DB liegen; niemals auf eine leere DB wechseln, um Budget freizumachen.
Unter dem Projekt-Lock erhält jeder Slot nur den kleineren verbleibenden Betrag
beider Caps. Die unveränderte Runtime reserviert jeden Provider-Attempt atomar
gegen seine Campaign.

## 4. Deterministische Fixtures und Prepare — ohne Provider

```powershell
& $python manage.py check_issue118_fixtures --expected-variant-commit $variantCommit --output $fixtureProof
if ($LASTEXITCODE -ne 0) { throw 'C1-State-Fixtures nicht grün' }
& $python manage.py prepare_issue118_experiment --expected-variant-commit $variantCommit --control-checkout $controlRoot --fixture-evidence $fixtureProof --plan $plan
if ($LASTEXITCODE -ne 0) { throw 'Prepare fehlgeschlagen; nicht starten' }
```

Fixture-Command führt exakt die beiden C1-Replays AP4-02/R4 und AP4-04/R5 aus.
Die Tests blockieren echte Provider explizit; das Subprocess-Environment löscht
zusätzlich Provider-Keys. JSON-Proof enthält Git-Commit, Testselector, Testdateihash
und JUnit-Ergebnis mit genau zwei bestandenen, nicht übersprungenen Tests.
Prepare und Export validieren diese Evidence; ein caller-provided `true` genügt nicht.
Prepare erstellt nur neutrale fachlich identische Domain-Eingaben und eingefrorene
Snapshots. Bestehende AP1-Objekte/Artefakte bleiben unangetastet. Wiederholung
von Prepare ist nur bei identischen Bindungen idempotent; ein vorhandener Plan wird
niemals überschrieben.

## 5. Dry-run / Slot-Check

```powershell
& $python manage.py run_issue118_variant --plan $plan --case AP4-01 --repeat 1 --check-only
if ($LASTEXITCODE -ne 0) { throw 'Slot-Check fehlgeschlagen' }
& $python scripts/issue118_control.py --plan $plan --case AP4-01 --inspect-runtime
if ($LASTEXITCODE -ne 0) { throw 'Historische Runtime-Isolation nicht bestätigt' }
```

Der Slot-Check startet keinen Run und keinen Provider. Vorab darf nur der nächste
Slot geprüft werden. Controls starten über die **externe Brücke** aus der Variant:
`scripts/issue118_control.py`. Sie prüft beide Git-HEADs, lädt Django und sämtliche
Produktmodule zuerst aus dem historischen Checkout, erweitert nur die Suchpfade
für die neuen #118-Harness-Module und prüft Importherkunft. Das direkte aktuelle
`manage.py run_issue118_control` verweigert Ausführung im v20-Checkout.

## 6. Reale Sequenz — ausschließlich im später freigegebenen Block

**Diesen Abschnitt nicht in C2a ausführen.** Provider-Key und eingefrorenes Modell
erst beim autorisierten realen Experiment bereitstellen. Kein OpenRouter-Testcall.
Kein `run_issue106_baseline`.

```powershell
# Erst nach Freigabe des REALEN Experiments ausführen.
$frozenPlan = Get-Content -LiteralPath $plan -Raw | ConvertFrom-Json
foreach ($slot in $frozenPlan.slots) {
    if ($slot.arm -eq 'variant') {
        & $python manage.py run_issue118_variant --plan $plan --case $slot.case_id --repeat $slot.repetition --check-only
    } else {
        & $python scripts/issue118_control.py --plan $plan --case $slot.case_id --repeat $slot.repetition --check-only
    }
    if ($LASTEXITCODE -ne 0) { throw 'Check verweigert; Sequenz stoppen' }
    if ($slot.arm -eq 'variant') {
        & $python manage.py run_issue118_variant --plan $plan --case $slot.case_id --repeat $slot.repetition --confirm-real-provider
    } else {
        & $python scripts/issue118_control.py --plan $plan --case $slot.case_id --repeat $slot.repetition --confirm-real-provider
    }
    if ($LASTEXITCODE -ne 0) { throw 'Runner unterbrochen; Recovery durchführen' }
}
```

Keine zweite parallele Sequenz. Ein normal terminales FAILED beendet einen Slot,
nicht seine Evidence-Zugehörigkeit. Auf menschlich bestätigtem Hard Fail stoppen
und im Parent neu entscheiden. Bei Prozessabbruch den nächsten Abschnitt nutzen.

## 7. Recovery

Dieselbe eingefrorene Sequenz erneut ausführen. Bestehende terminale Slots werden
ohne Provider wiederverwendet. Ein RUNNING-Slot ohne offene Reservation/laufenden
Call/Step wird mit demselben Run, Token, Commit und Campaign fortgesetzt. RUNNING
mit offenem Inflight-Zustand wird auf **dem bestehenden Run** als
`FAILED / execution_interrupted` gefenced: offene Reservierungen werden uncertain,
laufende Calls/Steps discarded, Executor-Generation/Token wechseln. Kein Ersatzslot,
kein Löschen, kein Umbenennen und keine manuelle DB-Reparatur. Der nächste Slot
darf erst nach diesem gespeicherten System-Boundary starten. Auch bei erschöpftem
Budget bleiben terminale Reuse und Fencing zugänglich.
Wenn zwischen Unterbrechung und Resume andere #106-Ausgaben das globale Budget
verkleinerten, verweigert ein zu großer bestehender Campaign-Spielraum die
Fortsetzung. Keine stillschweigende Cap-Erweiterung; im Parent neu entscheiden.

## 8. Export und Human Review

```powershell
& $python manage.py export_issue118_experiment --plan $plan --output $experiment --review-template $review
if ($LASTEXITCODE -ne 0) { throw 'Export inkonsistent' }
```

Export zeigt immer das Raster aller 25 Slots, einschließlich fehlender Slots ohne
erfundenen Run. Reviews werden für tatsächlich vorhandene Evidence generiert;
`expected_slots` zeigt die gesamte Population. Für den endgültigen Review erst
nach allen 25 terminalen Slots exportieren. Ein früher Partial-Export sollte eigene
Dateipfade verwenden, damit kein bereits bearbeiteter Review überschrieben wird.

Pro Run: Arm/Commit/Contract, Endzustand, Runtime, Rollen-Calls/Sekunden, Tool-Calls/
Sekunden, Timeout/Retry/Repair/Invalid-Response/No-Progress/Contract-Error, sämtliche
Fehlercodes, actual und budget-accounted Kosten, uncertain Attempts, Claims/Brief/
Verifier/Quellenrelevanz, Snapshot-/Dateihashes und deterministische Bindungen.
Pro Arm/Case: Gesamtpopulation und READY/WAITING_HUMAN/FAILED getrennt.

Menschen bewerten **alle 25 Runs** nach unveränderter AP1-Rubrik (`pass`, `fail`,
`unassessed`), einschließlich Reviewer und Review-Zeit. Hard-Fail-Checks separat.
LLM-Vorannotation darf die menschliche Bewertung nicht ersetzen. READY erzeugt
niemals automatisch PASS. Review bindet Arm, Commit, Plan und gesamten Record-Digest;
ein Review für geänderte Evidence wird abgelehnt.

```powershell
& $python manage.py export_issue118_experiment --plan $plan --output $experiment --review-template $review --assessments $review --require-complete
if ($LASTEXITCODE -ne 0) { throw 'Population/Review unvollständig oder Hard Fail' }
```

`--require-complete` bestätigt vollständige valide Evidence, keine Adoption.
Adoption benötigt zusätzlich die ausgewiesenen Gates und menschliche Parent-Entscheidung.
Reale `experiment.json`/`review.json` erst im späteren Messblock unter
`artifacts/issue106/exp118/` versionieren, zusammen mit dem eingefrorenen Plan.
In C2a gibt es dort keine echten oder synthetisch als real ausgegebenen Artefakte.

## 9. Gates lesen

- AP1 wird read-only geladen, Rubrik validiert und Summary exakt nachgerechnet.
  Baseline-Median/2×MAD und `.184652 USD / 16 Quality PASS` stammen aus Evidence.
- Drift: absoluter Control-Abstand zum AP1-Median > case-spezifisches 2×MAD.
  Ab zwei auffälligen Fällen: `comparison_status = not_sufficiently_proven`.
  Fehlende Population ebenfalls nicht ausreichend bewiesen. Control-Endzustände
  bleiben sichtbar, ohne ein neues No-Progress-Control-Gate zu erfinden.
- Runtime: AP1-Median minus Variant-Median je vorab betroffenem Case AP4-02/AP4-04;
  Median der Effekte und Median ihrer Noise Floors. Contract-Gate: mindestens 10 %
  **und** 30 Sekunden **und** mehr als Noise. Ein heterogener oder geänderter
  Endzustandsmix begründet keinen Runtime-Gewinn; Statusverteilungen und getrennte
  Runtime-Strata zeigen insbesondere FAILED→READY als Reliability-Effekt.
- G0.3: acht betroffene Variant-Runs, null `no_progress_loop`, keine neue technische
  Fehlerkategorie gegenüber AP1, beide gebundenen deterministischen C1-Fixtures grün.
- Timeout/Retry/Repair je Arm: alle gestarteten Runs im Nenner, auch FAILED.
  Variant jeweils höchstens AP1 +5 Prozentpunkte; Control separat.
- G0.2: ausschließlich Variant-accounted Kosten / **menschliche Quality PASS** über
  fünf Cases. Null PASS → `undefined`/JSON `null`. Control-Kosten sind nur im gemeinsamen
  Cap, nicht im Variant-Quotienten. Quotient höchstens AP1 ×1.05.
- Zusätzliche konservative Qualitätsprüfung: pro Case keine geringere menschliche
  PASS-Rate als AP1. Vollständige Review, null Hard Fail und gemeinsame Budget-/Event-
  Guards bleiben Pflicht. G0.3 oder methodisch belegter Runtime-Gewinn ist nur ein
  Kandidatennutzen; `adoption_eligible` ist kein automatischer Produktwechsel.

Nicht beobachtbar bleiben Provider-interne Queue/Inference-Anteile und ggf. Cache-
Effekte. Uncertain Kosten bleiben konservativ angerechnet, nicht als gemessener
Provider-Istpreis ausgegeben. Fehlerkategorien umfassen alle beobachteten Codes;
`new_failure_types` macht zusätzliche Kategorien ausdrücklich sichtbar.
