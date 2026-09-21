# Block 2: Blueprint-Format Version 1

**Issue:** #118  
**Vertrag:** `ki_radar/core/scenario_blueprints/contract.v1.json`  
**Schema-Version:** `1.0`

## Zweck

Version 1 beschreibt ausschließlich den vorhandenen KI-Radar-Entwurfspfad:

- Value Stream,
- Value-Stream-Phasen,
- eine Prozessanalyse,
- mehrere Lösungsoptionen,
- einen Use Case mit einer primären Metrik,
- Rollen- und Organisationseinheitsreferenzen,
- die Herkunftsbeziehung zwischen Discovery und Use Case.

Das Format ist keine allgemeine Import- oder Workflow-DSL.

## Top-Level-Struktur

| Feld | Bedeutung |
|---|---|
| `schema_version` | Muss exakt `1.0` sein. |
| `scenario_key` | Stabiler fachlicher Schlüssel des gesamten Szenarios. |
| `scenario_name` | Menschenlesbarer Szenarioname. |
| `references` | Vorbestehende Organisationseinheit und Benutzerreferenzen. |
| `value_stream` | Ein Value Stream mit Fokus-Default und Phasen. |
| `process_analysis` | Genau eine Entwurfs-Prozessanalyse für eine referenzierte Phase. |
| `solution_options` | Zwei bis acht unbewertete Kandidaten. |
| `use_case` | Ein Use-Case-Entwurf einschließlich Klassifikation und Metrik. |
| `origin` | Verknüpfung des Use Cases mit Phase, Prozessanalyse und Quelloption. |

Unbekannte Felder werden abgelehnt. Der maschinenlesbare Vertrag enthält für jeden Bereich eine Positivliste.

## Zulässige Entwurfszustände

Version 1 akzeptiert ausschließlich:

- Value Stream: `draft`
- Value-Stream-Fokus: `not_screened`
- Prozessanalyse: `draft`
- Lösungsoption: `recommendation=candidate`
- Lösungsoption: `evaluation_status=draft`
- Use Case: `status=idea`
- Use Case: `decision_status=clarification`

Diese Werte sind Teil des Vertrags und keine frei wählbaren Statusfelder.

## Technisch ausgeschlossene Zustände und Objekte

Nicht darstellbar sind insbesondere:

- Fokusentscheidung `selected`, `deferred` oder `not_selected`,
- Prozessvalidierung und Status `validated`,
- Zielbildstatus `target_defined`,
- bevorzugte oder verworfene Lösungsoption,
- bewertete Lösungsoption,
- DecisionAssessment,
- ApprovalDecision,
- GovernanceAssessment oder GovernanceReview,
- Freigabe und Zweitfreigabe,
- DeliveryPackage und Delivery-Bestätigungen,
- Übergabe,
- Pilot, Betrieb, Beendigung oder Go-live.

Der Validator arbeitet zusätzlich mit einer Positivliste. Später hinzukommende Modellfelder werden dadurch nicht automatisch importierbar.

## Schlüssel und Referenzen

### Fachliche Schlüssel

- `scenario_key`, Value-Stream-`key` und Use-Case-`key` entsprechen stabilen Slug-Schlüsseln.
- Phasen, Prozessanalyse und Optionen besitzen lokale Blueprint-Schlüssel.
- Phasen müssen zusätzlich innerhalb des Value Streams eine eindeutige `sequence` besitzen.
- Lokale Schlüssel sind innerhalb des Blueprint-Dokuments eindeutig.

### Externe Referenzen

Der Blueprint erzeugt keine Referenzobjekte.

- Organisationseinheit: Auflösung über exakten, eindeutigen Namen.
- Benutzer: Auflösung über exakten `username`.
- Alle Benutzer müssen aktiv und nicht anonymisiert sein.
- Die Organisationseinheit muss aktiv sein.
- Der Value-Stream-Owner muss die vorhandene Berechtigungsregel des `ValueStreamForm` erfüllen.

Für die mitgelieferte Demo-Referenz müssen Demo-Identitäten und Demo-Organisationseinheit bereits über den bestehenden Seed-/Identitätspfad angelegt sein. Eine Datenbank ohne diese Referenzen liefert einen Validierungsfehler; der Blueprint ergänzt sie nicht.

## Zahlen und Prüfsumme

JSON-Zahlen werden beim Laden als exakte Dezimalwerte behandelt. Für die Prüfsumme wird das Dokument kanonisch serialisiert:

- UTF-8,
- sortierte Objektschlüssel,
- keine bedeutungslose Einrückung,
- feste Separatoren,
- unveränderte Array-Reihenfolge,
- keine binären Gleitkommawerte,
- normalisierte Dezimalschreibweise ohne Exponent und ohne überflüssige Nachkommastellen.

Damit erzeugen etwa `11.0` und `11.00` dieselbe kanonische Zahl. Textwerte bleiben unverändert.

Die SHA-256-Prüfsumme wird ausschließlich über diese kanonische Bytefolge gebildet.

## Wiederholungs- und Konfliktverhalten

Für jedes unterstützte Objekt wird ein stabil sortierter Diff mit einem der Zustände erzeugt:

- `CREATE`: Der vollständige Szenariograph ist noch nicht vorhanden.
- `NO_CHANGE`: Der vollständige Graph entspricht dem Blueprint.
- `CONFLICT`: Ein Teilgraph, Feldwert, Status, Beziehung oder Referenzzustand weicht ab.

Ein einzelner Konflikt blockiert den gesamten Apply. Teilanwendung, Update, Merge, Replace oder konfliktfreies Überspringen einzelner Objekte sind in Version 1 ausgeschlossen.

## Schreibpfad

Vor jeder Änderung werden vollständig geprüft:

1. JSON-Struktur und Version,
2. erlaubte Felder, Typen und Enum-Werte,
3. lokale Referenzen und Eindeutigkeit,
4. externe Benutzer- und Organisationseinheitsreferenzen,
5. alle maßgeblichen Django-Forms,
6. bestehender Datenbankzustand und graphweiter Diff.

Erst danach darf eine einzige `transaction.atomic()`-Apply-Phase beginnen.

Die fachliche Validierung erfolgt über:

- `ValueStreamForm`,
- `ValueStreamStageForm`,
- `ProcessAnalysisForm`,
- `SolutionOptionForm`,
- `UseCaseForm`.

Technische Felder wie `demo_key`, `created_by`, `submitter`, `analyzed_by` und Herkunfts-Snapshots werden erst nach erfolgreicher Formvalidierung kontrolliert ergänzt.

## Prüfsummen-Governance

Die erwartete Prüfsumme eines Referenz-Blueprints darf nur geändert werden, wenn:

1. die Schema-/Blueprint-Version bewusst erhöht wird, oder
2. eine fachlich bestätigte Korrektur des Referenzszenarios dokumentiert ist.

Die Änderung muss in einem eigenen begründeten Pull Request erfolgen. Eine Anpassung ausschließlich zur Behebung eines fehlgeschlagenen Drift-Tests ist unzulässig.

## Lean-Abgrenzung

Version 1 enthält bewusst nicht:

- Plugin-System,
- universelle Workflow-DSL,
- grafischen Editor,
- Fremdformat-Adapter,
- Vorlagenbibliothek,
- Multi-Tenant-Funktionen,
- Merge-Engine,
- allgemeine Importhistorie,
- neue Persistenzmodelle nur für Blueprints.
