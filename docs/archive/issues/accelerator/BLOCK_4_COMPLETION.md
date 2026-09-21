# Block 4 – Abschlussnachweis

**Issue:** #120  
**Übergeordneter Plan:** #116, unverändert  
**Ziel:** Antworten abgeschlossener Capture Sessions ausdrücklich analysieren und ausschließlich serverseitig validierte, quellennachweisbare Feldvorschläge anzeigen, ohne reguläre Fachobjekte zu verändern.

## Arbeitspakete

| AP | Pull Request | Konkretes Ergebnis | CI |
| --- | --- | --- | --- |
| AP 1 | #152 | Gap-Analyse, Wiederverwendungsgrenzen, eingefrorene Katalogversion, Block-5-Anschluss und Retention verbindlich dokumentiert. | #910 |
| AP 2 | #154 | Versionierter Extraktionsvertrag mit Zielpfad-, Quellfrage-, Scope- und Feldtyp-Whitelist eingeführt. | #920 |
| AP 3 | #155 | Persistente Analyse-, Vorschlags- und Tagesquotenmodelle einschließlich nullable Zielobjekt-ID und Constraints eingeführt. | #922 |
| AP 4 | #156 | Gemeinsamen begrenzten OpenRouter-Transport extrahiert und bestehenden Review-Copilot regressionsfrei umgestellt. | #924 |
| AP 5 | #157 | Expliziten Analysepfad für abgeschlossene Sessions mit Source Snapshot, minimiertem Payload, Quoten und Doppellaufschutz implementiert. | #926 |
| AP 6 | #158 | Providerergebnisse vollständig, quellennah, typisiert und atomar validiert; degenerierte Inhalte und erfundene Gruppen werden abgewiesen. | #932 |
| AP 7 | #159 | Serverseitige Review-Aktion und Vorschau mit Quellen, Unsicherheit, Findings, Fehlerzuständen und Laufhistorie integriert. | #934 |
| AP 8 | #160 | Metadaten-only-Logging, sensible Fehlerpfade und konfigurierbare 90-Tage-Retention mit siebentägiger Löschkarenz abgeschlossen. | #936 |
| AP 9 | #161 | Anonymisierte `[Real-DEMO]`-Golden-Fixture mit SHA-256-Driftschutz und Erfolgs-, Provider-, Quoten- und Ablehnungsregressionen eingeführt. | #948 |
| AP 10 | #162 | Vollständige Regression, ergänzende Randfallnachweise, Desktop-/Mobile-Abnahme und Abschlussdokumentation. | CI #966 · UI #17 |

## Inhaltsprüfung AP 6 bis AP 9

Die verspätete Pflege der Issue-Checkliste wurde nicht als fachlicher Nachweis verwendet. Vor AP 10 wurden Workplan, tatsächliche PR-Diffs und Tests erneut gegeneinander geprüft.

- AP 6 belegt Schema-, Quellen-, Gruppierungs-, Enum-, Ganzzahl- und deutsche Dezimal-/Einheitenprüfung sowie atomare Ablehnung. AP 10 ergänzt explizite Ablehnung der in Version 1 für konkrete Zielpfade nicht anwendbaren Typen `text_list`, `boolean`, `date`, `uuid` und `reference`.
- AP 7 enthält die ausdrücklich gestartete POST-Aktion, owner-gebundene Vorschau, Laufhistorie, Quellen, Unsicherheit, offene Fragen, Widersprüche und kontrollierte Fehlerzustände. Block-5-Aktionen fehlen bewusst.
- AP 8 enthält konfigurierbare 30- bis 365-Tage-Retention mit Standard 90, Verlängerung je Analyseversuch, Ablauf abgeschlossener Sessions, siebentägige Karenz, Kaskadenlöschung sowie technische Logs ohne Prompt- oder Antwortinhalt.
- AP 9 enthält deterministische Value-Stream- und Use-Case-Golden-Pfade, Fixture-Driftschutz, JSON-/Schema-/Evidenz-/Taxonomieablehnung, Rate-Limit-/Timeout-/Provider-/Größenfehler, alle drei Quotentypen mit Tageswechsel, Ergebnis-Wiederanzeige und maximale Vorschlagsanzahl. AP 10 ergänzt Prompt-Injection, echte HTTP-401-/403-/500- und Netzwerkpfade sowie den Erhalt früherer erfolgreicher Vorschläge nach leerer Providerantwort.

Damit werden AP 6 bis AP 9 gemeinsam mit dem grünen AP-10-Nachweis als vollständig abgenommen.

## Abnahmematrix für Issue #120

| Wörtliches Abnahmekriterium | Nachweis |
| --- | --- |
| Gap-Analyse dokumentiert. | `docs/accelerator/BLOCK_4_GAP_ANALYSIS.md`, PR #152. |
| Analyse nur nach ausdrücklicher Benutzeraktion. | POST-only-Route und Review-Schaltfläche in PR #159; GET startet nachweislich keinen Provideraufruf in `tests/test_capture_analysis_views.py`. |
| Ausgabe serverseitig gegen versioniertes Schema validiert. | `extraction_contract.py`, `extraction_validation.py`, Vertrags- und Golden-Tests aus PR #154, #158 und #161. |
| Unbekannte Felder und ungültige Typen werden abgewiesen. | Zielpfad-/Feldprüfung in AP 2 und AP 6; ergänzende Typ-Randfälle in `tests/test_block4_completion.py`. |
| Vorschläge zeigen Quelle, Unsicherheit und offene Fragen. | `templates/accelerator/analysis_detail.html`, Viewtests und reproduzierbare Browserabnahme in AP 10. |
| Rate-Limit-, Timeout- und Provider-Ausfälle sind kontrolliert und ohne Datenverlust behandelt. | Gemeinsamer Transport, kontrollierte Laufstatus, Quoten- und Providerregressionen in AP 4, AP 5, AP 9 und AP 10; frühere erfolgreiche Vorschläge bleiben erhalten. |
| Reguläre Fachobjekte bleiben unverändert. | Analyse- und Golden-Tests prüfen unveränderte `ValueStream`- und `UseCase`-Bestände; keine Schreibroute aus Block 5 vorhanden. |
| Keine Rohtexte oder Prompts in Standardlogs. | Metadaten-only-Logging und Negativtests in AP 4 und AP 8. |
| Lösung bleibt schlank und auf einen Providerpfad begrenzt. | Genau ein OpenRouter-Transport, serverseitiger Django-Pfad, keine Queue-, Streaming-, Gateway-, Cache-, Vektor- oder Billing-Plattform. |

## Vollständige Regression

Die unveränderte Repository-CI #966 ist vollständig grün. Sie umfasst:

1. Lockfile-Prüfung und Installation,
2. repo-weites Ruff-Linting,
3. `ruff format --check .`,
4. Django-Systemcheck,
5. Migrationsprüfung und Migrationen,
6. vollständige Pytest-Suite,
7. Bandit und Dependency Audit,
8. lokale, Produktions- und Staging-Compose-Validierung,
9. Produktions- und Entwicklungsimage-Build.

Zusätzlich führt `.github/workflows/block4-ui-verification.yml` eine fokussierte Block-4-Regression und eine reale Chromium-Abnahme aus.

## Desktop-/Mobile-Abnahme

Die reproduzierbare Prüfung verwendet:

- Desktop: `1440 × 1000` Pixel,
- Mobile: `390 × 844` Pixel mit Touch-/Mobile-Kontext.

Je Viewport werden geprüft und als vollständige Screenshots gespeichert:

1. abgeschlossene Value-Stream-Review-Seite,
2. abgeschlossene Use-Case-Review-Seite,
3. erfolgreiche gruppierte Vorschau mit offenen Fragen und Widersprüchen,
4. erfolgreiche leere Vorschau,
5. erfolgreiche Vorschau mit langem Inhalt,
6. fehlgeschlagene Vorschau,
7. erfolgreiche Use-Case-Vorschau.

Automatisch geprüft werden HTTP 200, unveränderte Viewportbreite, fehlender horizontaler Überlauf, keine unzugänglichen interaktiven Elemente des Block-4-Hauptinhalts außerhalb des Viewports, erwartete Inhalte und das Fehlen von Übernahme-, Verwerf- oder Sammelaktionen. Bedienelemente in responsiven Tabellen bleiben über deren eigenen horizontalen Scrollcontainer erreichbar. Die Screenshots und der JSON-Bericht werden als GitHub-Actions-Artefakt gespeichert und zusätzlich visuell geprüft.

**Finaler UI-Lauf und Sichtprüfung:** UI #17 vollständig grün. 38 fokussierte Regressionen und 14 Seitenzustände wurden geprüft. Alle Seiten lieferten HTTP 200; es gab keinen Dokumentüberlauf, keine Viewportabweichung, keine unzugänglichen Bedienelemente und keine Block-5-Aktionen. Der Artefaktbericht und repräsentative Desktop-/Mobile-Screenshots wurden visuell geprüft; lange, gruppierte und fehlerhafte Vorschauen blieben lesbar und vollständig bedienbar.

## Migrationen und Datenhaltung

Block 4 führt mit `ki_radar/accelerator/migrations/0002_capture_analysis_and_quotas.py` ausschließlich technische Modelle für Analyseläufe, Vorschläge und Quoten ein. Reguläre Architektur-, Use-Case-, Governance-, Delivery- und Lifecycle-Modelle werden nicht migriert.

Abgeschlossene Capture Sessions erhalten eine konfigurierbare Retention von 30 bis 365 Tagen, Standard 90 Tage. Jeder ausdrückliche Analyseversuch setzt das Ablaufdatum neu. Nach Ablauf wird die Session in `expired` überführt und nach sieben Tagen zusammen mit Analysen und Vorschlägen physisch gelöscht. Laufende Analysen verhindern den Ablauf.

## Vollständige Dateiliste der Block-4-PRs

### PR #151 – Arbeitsplan

- `docs/accelerator/BLOCK_4_WORKPLAN.md`

### PR #152 – AP 1

- `docs/accelerator/BLOCK_4_GAP_ANALYSIS.md`

### PR #154 – AP 2

- `ki_radar/accelerator/extraction_contract.py`
- `tests/test_extraction_contract.py`

### PR #155 – AP 3

- `ki_radar/accelerator/migrations/0002_capture_analysis_and_quotas.py`
- `ki_radar/accelerator/models.py`
- `tests/test_capture_analysis_models.py`

### PR #156 – AP 4

- `ki_radar/core/openrouter.py`
- `ki_radar/use_cases/copilot.py`
- `tests/test_accelerator_llm.py`

### PR #157 – AP 5

- `ki_radar/accelerator/analysis_service.py`
- `tests/test_capture_analysis_service.py`

### PR #158 – AP 6

- `ki_radar/accelerator/extraction_validation.py`
- `tests/test_extraction_validation.py`

### PR #159 – AP 7

- `ki_radar/accelerator/urls.py`
- `ki_radar/accelerator/views.py`
- `templates/accelerator/analysis_detail.html`
- `templates/accelerator/capture_review.html`
- `tests/test_capture_analysis_views.py`

### PR #160 – AP 8

- `.env.example`
- `config/settings/base.py`
- `ki_radar/accelerator/analysis_service.py`
- `ki_radar/accelerator/extraction_validation.py`
- `ki_radar/accelerator/management/commands/purge_capture_sessions.py`
- `ki_radar/accelerator/retention.py`
- `ki_radar/accelerator/retention_policy.py`
- `ki_radar/accelerator/services.py`
- `tests/test_capture_analysis_retention_privacy.py`

### PR #161 – AP 9

- `ki_radar/accelerator/extraction_contract.py`
- `tests/fixtures/accelerator/real_demo_capture.v1.json`
- `tests/fixtures/accelerator/real_demo_capture.v1.sha256`
- `tests/test_capture_analysis_golden.py`

### PR #162 – AP 10

- `.github/workflows/block4-ui-verification.yml`
- `docs/accelerator/BLOCK_4_COMPLETION.md`
- `scripts/block4_ui_verification.py`
- `tests/test_block4_completion.py`

## Bestätigte Nicht-Ziele

- keine Übernahme oder Anlage regulärer Fachobjekte,
- keine Sammelaktion,
- keine generativen Lösungsoptionen,
- keine automatische Entscheidung, Validierung, Freigabe oder Lifecycle-Änderung,
- keine Audio-, Datei- oder Connector-Extraktion,
- keine Queue-, Streaming-, AI-Gateway-, Prompt-Management-, Cache-, Vektor- oder Billing-Plattform,
- keine Änderung von Issue #116.

## Nachtrag: Reale Structured-Output-Integration

Nach dem formalen Block-4-Abschluss zeigte ein realer OpenRouter-Aufruf eine Integrationslücke, die von den vollständig simulierten Providerantworten der ursprünglichen Regression nicht erkannt wurde. Die Nachverfolgung erfolgt transparent in Issue #163 und dem separaten Fix-PR #164.

Der Nachtrag korrigiert keine fachliche Scope-Entscheidung aus Block 4, sondern den realen Providervertrag:

- das Ausgabelimit wird von 700 auf 4096 Tokens angehoben und der Timeout auf 60 Sekunden gesetzt,
- der vorhandene versionierte Extraktionsvertrag wird als striktes JSON Schema an OpenRouter übermittelt,
- `provider.require_parameters=true` schließt Provider aus, die das Schema ignorieren würden,
- abgeschnittene Antworten werden als `output_truncated` statt als generisches `invalid_response` protokolliert,
- ein fehlender kompatibler Schema-Provider wird als `provider_schema_unsupported` ausgewiesen,
- die bestehende atomare serverseitige Validierung bleibt als zweite, maßgebliche Schutzschicht unverändert bestehen.

Die Ergänzung wird durch Transport-, Vertrags- und Analyse-Service-Regressionen abgesichert. Issue #120 bleibt als historischer Blockabschluss geschlossen; dieser Nachtrag stellt den später erkannten Realbetrieb-Fix nachvollziehbar daneben.
