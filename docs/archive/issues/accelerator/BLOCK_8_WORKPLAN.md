# Accelerator Block 8: Verbindlicher Arbeitsplan

**Issue:** #124  
**Übergeordneter Plan:** #116, unverändert  
**Ausgangsstand:** `main` auf `085c32b19bf173aded1eecfa73c092f1df50e6e9` nach Block-7-Nachtrag #209  
**Ziel:** Bestehende Delivery-Package-Vorbefüllung in einen expliziten, konfliktgeschützten und nachvollziehbaren Evidence-to-Delivery-Mapper überführen, ohne einen parallelen Delivery-Workflow oder neue fachliche Entscheidungen zu bauen.

## 1. Verbindliche Blockgrenze

Block 8 ersetzt keinen bestehenden Delivery-Prozess. Die vorhandene Erzeugung, Section Reviews, Readiness, Source-Manifeste, Staleness-Prüfung, Rollenbestätigungen und Unveränderlichkeit übergebener Package-Versionen bleiben autoritativ.

Der Mapper arbeitet ausschließlich auf regulären, fachlich wirksamen Domänenobjekten. Accelerator-Zwischenartefakte aus Block 4, 5 und 7 sind kein zweiter fachlicher Wahrheitsstand. Nach expliziter Übernahme sind die regulären Objekte maßgeblich; Accelerator-Audits und Generation-Runs bleiben Herkunfts- beziehungsweise Laufnachweis.

Version 1 priorisiert eine kleine Golden-Path-Feldmenge. Fehlende Fakten bleiben offen. Generische Arbeitsanweisungen wie „konkretisieren“ gelten nicht als fertiger Inhalt.

Nicht gebaut werden:

- generische Mapping- oder ETL-Plattform,
- Mapping-DSL oder grafischer Mapping-Editor,
- allgemeine Template-Engine,
- zweiter Delivery-Entwurfstyp,
- paralleler Accelerator-Delivery-Workflow,
- generische Provenance-Datenbank,
- Vektor-Datenbank,
- Dokumenten- oder Connector-Import,
- automatische Sektionsbestätigung,
- automatische Readiness-Freigabe,
- fachliche oder technische Bestätigung,
- automatische Freigabe, Zweitfreigabe oder Übergabe,
- Änderung bereits übergebener Delivery-Versionen,
- freie LLM-Generierung von Anforderungen, Risiken, Systemen, Schnittstellen, Governance-Aussagen, Rollen oder Architekturentscheidungen.

Issue #116 bleibt unverändert.

## 2. Verifizierte Gap-Analyse gegen `main`

### 2.1 Bestehende Delivery-Vorbefüllung

`create_delivery_package()` erzeugt bereits ein reguläres `DeliveryPackage`, setzt die `readiness_schema_version=2`, befüllt Felder über `build_initial_delivery_data()` und erzeugt Section Reviews mit einem gemeinsamen Source Manifest.

Bereits deterministisch aus vorhandenen Quellen vorbefüllt werden unter anderem:

- `problem_context` aus `UseCase.problem_statement`,
- `target_outcome` aus `UseCase.expected_benefit`,
- `in_scope` und `out_of_scope` aus dem Value Stream, sofern eine Architekturherkunft existiert,
- `users_and_scenarios` aus `intended_users` beziehungsweise `target_users`,
- `solution_outline` aus `intended_purpose` beziehungsweise `summary`,
- `system_context` aus `source_systems`,
- `data_context` aus `data_sources`,
- `integrations` aus `interface_description`,
- `human_oversight`,
- `operations_and_support`,
- strukturierte Metrikinformationen für `measurement_plan`,
- Freigabeauflagen für `handover_notes`.

Der aktuelle Code mischt diese belastbaren Übernahmen jedoch mit generischen Defaulttexten für Requirements, Testfälle, Backlog, Betrieb, Architekturartefakte und weitere Felder. Genau diese Mischung wird in Block 8 aufgelöst.

### 2.2 Bestehende Provenance- und Staleness-Mechanismen

`build_source_manifest()` speichert bereits Source-Objekte, IDs, `updated_at`, Assessment-Version, konkrete Feldquellen und Rollenquellen. `delivery_source_differences()` und die Readiness-Prüfung vergleichen Snapshots mit aktuellen Quellen. Architektur-Provenance existiert zusätzlich für Value Stream, Process Analysis und Solution Option.

Verbindliche Folgerung:

- vorhandenes `source_manifest` erweitern statt neues Provenance-System bauen,
- pro V1-Delivery-Feld explizite Source-Snapshots und Mapping-Metadaten speichern,
- zusammengesetzte Felder erhalten mehrere Source-Einträge und einen normalisierten Evidence-Hash,
- Staleness bleibt aus Source-Differenzen ableitbar.

### 2.3 Bestehende Readiness und Platzhalter

Die Readiness blockiert bereits leere Pflichtfelder und mehrere bekannte generische Platzhalter. Dennoch existieren Defaulttexte, die formal Inhalt sind, fachlich aber keine bestätigte Delivery-Aussage darstellen.

Verbindliche Folgerung:

- neue Packages erhalten für fehlende Fakten keine generischen Fülltexte,
- bekannte historische Systemtemplates werden als Legacy-Placeholder behandelt und bleiben nicht readiness-fähig,
- bestehende Packages werden nicht destruktiv bereinigt.

### 2.4 Bestehende Review- und Immutability-Regeln

Änderungen über das reguläre Delivery-Formular setzen nur die betroffenen Section Reviews zurück. Ein bereits `handed_over` Package ist unveränderlich.

Verbindliche Folgerung:

- Mapper-Änderungen nutzen dieselbe Review-Reset-Semantik,
- keine Bestätigung bleibt nach einer fachlichen Mapper-Änderung fälschlich gültig,
- keine automatische Bestätigung wird gesetzt,
- übergebene Versionen werden vom Mapper nie verändert.

### 2.5 Fachliche Quellhierarchie

Block 8 liest aus fachlich wirksamen Domänenobjekten, nicht aus temporären Accelerator-Vorschlägen.

Verbindliche Source-Hierarchie:

1. finale beziehungsweise aktuell wirksame Use-Case-Felder für Use-Case-Inhalte,
2. immutable beziehungsweise eingefrorene Entscheidungs-Snapshots für lösungsspezifische Zusatzinformationen,
3. Process Analysis und Value Stream für dort fachlich beheimatete Prozess- und Scope-Fakten,
4. finale Approval Decision und zugehöriges Assessment ausschließlich für bereits existierende Freigabe- beziehungsweise Bewertungsfakten.

Block 8 erzeugt keine Freigabe und hängt nicht davon ab, dass der Accelerator selbst eine Freigabe automatisiert. `handover_notes` darf nur bereits vorhandene finale Approval-Daten lesen. Der Mapper verändert weder Approval-, Second-Approval- noch Handover-Gates.

### 2.6 V1-Feldmenge

Version 1 unterstützt vorrangig folgende Delivery-Felder:

| Zielbereich | Delivery-Feld | V1 | Autoritative Quelle beziehungsweise Regel |
|---|---|---:|---|
| Problem | `problem_context` | ja | `UseCase.problem_statement` |
| Ziel | `target_outcome` | ja | `UseCase.expected_benefit` |
| Scope | `in_scope` | ja | `ValueStream.scope_in`, sonst dokumentierte Fallback-Quelle |
| Scope | `out_of_scope` | ja | `ValueStream.scope_out`; sonst Gap |
| Nutzer | `users_and_scenarios` | ja | `UseCase.intended_users` oder `target_users` |
| Lösung | `solution_outline` | ja | finaler Use Case, ergänzend bestätigter Lösungs-Snapshot |
| Systeme | `system_context` | ja | `UseCase.source_systems` |
| Daten | `data_context` | ja | `UseCase.data_sources` |
| Integration | `integrations` | ja | `UseCase.interface_description` |
| Aufsicht | `human_oversight` | ja | `UseCase.human_oversight`; sonst Gap |
| Betrieb | `operations_and_support` | ja | `UseCase.support_responsibility`; sonst Gap |
| Messung | `measurement_plan` | ja | strukturierte Use-Case-Metrikfelder |
| Akzeptanz | `acceptance_criteria` | begrenzt | explizites Erfolgskriterium und strukturierte Metrik; keine erfundenen Kriterien |
| Risiken | `risks` | begrenzt | bestätigter Lösungs-Snapshot; sonst Gap |
| Übergabeinfo | `handover_notes` | ja | bereits vorhandene finale Approval-Auflagen; keine neue Freigabelogik |
| Architektur | `system_landscape` | begrenzt | bestätigte Systeme plus bestätigte Anwendungsauswirkung |
| Architektur | `data_flows` | begrenzt | bestätigte Datenquellen plus bestätigte Integrationen |

Bewusst nicht automatisch fachlich ausgefüllt werden in Version 1, sofern keine explizite belastbare Quelle existiert:

- `mvp_scope`,
- `functional_requirements`,
- `non_functional_requirements`,
- `logging_and_audit`,
- `test_scenarios`,
- `dependencies`,
- `assumptions`,
- `architecture_decisions`,
- `initial_backlog`,
- Detailangaben zu `system_responsibilities`, `data_quality_and_access`, `integration_contracts` und `integration_operations`.

Diese Felder bleiben echte Lücken statt plausibel klingender Systemtexte.

## 3. Mapping-Vertrag

### 3.1 Statische Registry statt Mapping-Engine

Für jedes unterstützte V1-Feld wird eine statische, code-seitige Mapping-Spezifikation definiert mit:

- Zielsektion,
- erlaubten Source-Typen,
- erlaubten Source-Feldern,
- Source-Priorität,
- Transformationsart,
- erforderlicher Source-Version beziehungsweise Snapshot-Bedingung,
- Verhalten bei mehreren Quellen,
- Pflichtquellen,
- Konfliktregel,
- Verhalten bei fehlender Evidenz,
- optionaler LLM-Restaufgabe.

Keine Reflection-basierte allgemeine Schreibfunktion und keine frei konfigurierbare Mapping-Sprache.

### 3.2 Drei explizite Schreibzustände

Die Konfliktmatrix unterscheidet zwingend:

1. **neu/leer:** Package ist neu oder das Feld war bisher Gap/offen, nie gemappt und nie manuell befüllt; sobald erstmals valide Evidenz vorliegt, darf direkt deterministisch übernommen werden,
2. **unverändert gemappt:** der aktuelle Delivery-Wert entspricht noch dem zuletzt gemappten fachlichen Zustand; neue valide Evidenz darf deterministisch aktualisieren,
3. **manuell abweichend:** der Delivery-Wert wurde seit dem letzten Mapping fachlich verändert; bei abweichender neuer Evidenz entsteht ein sichtbarer Konflikt und es erfolgt keine stille Überschreibung.

Ein zuvor offenes Feld wird nicht allein deshalb zum Konflikt, weil später erstmals eine Quelle verfügbar wird.

### 3.3 Evidence-Hash statt gerendertem Stringvergleich

Für direkte Mappings kann der normalisierte Quellwert Bestandteil des Hashes sein. Für zusammengesetzte Felder wird Gleichheit nicht am gerenderten Freitext entschieden.

Der Evidence-Hash wird aus einer kanonischen strukturierten Darstellung der fachlichen Inputs berechnet, beispielsweise:

- Source-Typ,
- Source-ID,
- relevante Fachversion,
- Feldname,
- normalisierter Fachwert,
- definierter Mapping-Regelversion.

Reihenfolge- oder Formatierungsänderungen im gerenderten Text dürfen keinen fachlichen Konflikt erzeugen, solange der kanonische Evidence-Inhalt gleich bleibt.

### 3.4 Mapping-Zustände im bestehenden Manifest

Pro unterstütztem Feld wird im bestehenden Source Manifest ein schmaler Mapping-Nachweis geführt:

- `mapped`,
- `gap`,
- `conflict`,
- `stale`.

Zusätzlich werden Mapping-Regelversion, Evidence-Hash und relevante Sources gespeichert. Diese Zustände sind kein neuer Workflowstatus und ersetzen weder Readiness noch Section Review.

## 4. Deterministische Transformation

Die Verarbeitung erfolgt verbindlich in dieser Reihenfolge:

1. direkte deterministische Übernahme eindeutiger Source-Felder,
2. deterministische Zusammensetzung eindeutig strukturierter Sources,
3. Gap- und Konflikterkennung,
4. optionale LLM-Sprachverdichtung nur für ausdrücklich freigegebene Rest-Freitextfelder.

Fehlende Fakten werden niemals durch Defaults oder LLM-Inhalte ergänzt.

Deterministische Kompositionen müssen formatstabil, testbar und unabhängig vom Provider ausführbar sein.

## 5. Refresh- und Konfliktverhalten

### 5.1 Neue Package-Version

Bei Erzeugung einer neuen, noch nicht manuell bearbeiteten Package-Version werden valide V1-Mappings direkt angewendet. Fehlende Sources erzeugen Gap-Zustände.

### 5.2 Erstmals verfügbare Evidenz

War ein Feld bisher leer/GAP, nie automatisch gemappt und nie manuell befüllt, wird neue valide Evidenz bei Refresh wie bei einem neuen Package direkt übernommen.

### 5.3 Bereits gemappte Felder

Ist der Evidence-Zustand seit dem letzten Mapping fachlich unverändert, führt ein Refresh nicht zu unnötigen Schreibvorgängen oder Review-Resets.

Ändert sich die Source-Evidenz und der aktuelle Delivery-Wert entspricht weiterhin dem zuletzt gemappten Zustand, darf der Mapper aktualisieren und die betroffene Review-Sektion zurücksetzen.

### 5.4 Manuell veränderte Felder

Weicht ein aktueller Delivery-Wert vom zuletzt gemappten Zustand ab und ändert sich zugleich die relevante Source-Evidenz, wird kein Wert überschrieben. Der Konflikt zeigt mindestens:

- zuletzt gemappten Zustand,
- aktuellen Delivery-Wert,
- neuen Source-Zustand,
- relevante Source-Versionen.

Kein Force-Overwrite und kein automatischer Drei-Wege-Merge.

### 5.5 Übergebene Packages

`handed_over` bleibt vollständig unveränderlich. Ein Refresh darf dort weder Feldwerte, Mapping-Zustände noch Reviews verändern.

## 6. Bestands-Packages

Bestehende Delivery Packages vor Block 8 werden nicht pauschal mutiert und nicht durch eine Datenmigration neu gerendert.

Verbindliche Strategie:

- bestehende `source_manifest`-Daten bleiben erhalten,
- fehlende Block-8-Mapping-Metadaten bedeuten zunächst `legacy/unmapped`, nicht automatisch `mapped`,
- ein expliziter Refresh eines nicht übergebenen Packages baut den neuen Mapping-Nachweis aus den vorhandenen Sources und dem aktuellen Delivery-Zustand auf,
- bekannte historische Systemtemplates werden als Legacy-Placeholder erkannt,
- echte manuelle Inhalte werden nicht als Template umgedeutet,
- übergebene Legacy-Packages bleiben unangetastet.

Damit gibt es keine stille Backfill-Migration, die bestehende Reviews oder manuelle Delivery-Arbeit verfälscht.

## 7. Review, Readiness und Staleness

Bestehende Mechanismen bleiben maßgeblich:

- Feldänderung durch Mapper setzt nur die betroffene Delivery-Sektion auf `needs_review` zurück,
- bestehende Business-/Technical-Bestätigungen der geänderten Sektion werden zurückgesetzt,
- unveränderte Felder lösen keinen Review-Reset aus,
- Gaps und generische Legacy-Placeholder bleiben readiness-blockierend, soweit das Feld Pflichtfeld ist,
- Source-Änderungen nach Snapshot bleiben sichtbar,
- Mapping-Zustand ergänzt, ersetzt aber nicht die bestehende Staleness- und Readiness-Logik,
- keine Mapping-Aktion setzt `ready`, `confirmed`, `handed_over` oder andere fachliche Gate-Zustände automatisch.

## 8. Deploybarkeit zwischen den Arbeitspaketen

Jedes AP wird einzeln auf `main` gemergt. Deshalb bleibt der Golden Path nach jedem Merge deploybar.

Verbindliche Übergangsstrategie:

- AP 1 ist Dokumentation בלבד; keine Laufzeitänderung,
- AP 2 bis AP 5 bauen neue Mapper-Bausteine und Tests neben dem bestehenden Pfad auf, ohne die produktive Delivery-Erzeugung umzuschalten,
- AP 6 verdrahtet den neuen Mapper kontrolliert in den bestehenden Delivery-Pfad; die Umschaltung erfolgt über eine kleine block-spezifische Konfiguration beziehungsweise Branch-by-Abstraction, nicht über einen zweiten Workflow,
- die bisherige Delivery-Erzeugung bleibt bis zur vollständigen Integrationsreife als Fallback ausführbar,
- AP 7 bis AP 9 erweitern ausschließlich den bereits kontrollierten Block-8-Pfad,
- AP 10 entfernt einen nur temporär notwendigen Umschaltpfad oder setzt den final vorgesehenen Default, sobald vollständige Repository-CI, Real-DEMO und Gate-Regression grün sind.

Kein Zwischen-AP darf `main` in einen Zustand bringen, in dem reguläre Delivery-Erzeugung nicht funktioniert.

## 9. LLM-Resttext

LLM-Unterstützung ist optional und nicht Voraussetzung für das deterministische Ergebnis.

V1 prüft LLM-Sprachverdichtung nur für eine sehr kleine explizite Feldmenge, bevorzugt:

- `system_landscape`,
- `acceptance_criteria`.

Ein LLM-Aufruf ist nur zulässig, wenn:

- alle verwendeten Fakten bereits deterministisch im Evidence Snapshot vorliegen,
- kein Gap oder Konflikt in den dafür notwendigen Sources existiert,
- der Nutzer die Formulierung ausdrücklich anstößt oder ein bereits bestätigter Verarbeitungsschritt dies eindeutig vorsieht,
- der Provider ausschließlich bestätigte Fakten sprachlich zusammenführt.

Das LLM darf insbesondere keine neuen Systeme, Schnittstellen, Anforderungen, Risiken, Architekturentscheidungen, Governance-Aussagen, Rollen, Freigaben oder Bestätigungen erzeugen.

### 9.1 LLM-Idempotenz und Cache-Regel

Der LLM-Eingang erhält einen kanonischen Evidence-Hash plus Prompt-/Schema-Version.

Verbindliche Regel:

- gleicher Evidence-Hash plus gleiche Prompt-/Schema-Version und bereits erfolgreicher Resttext → kein neuer Provideraufruf; vorhandenes validiertes Ergebnis wird wiederverwendet,
- geänderte Evidenz oder bewusst geänderte Prompt-/Schema-Version → neuer Lauf möglich,
- fehlgeschlagener Provideraufruf verändert keine deterministischen Delivery-Werte,
- kein automatischer Retry.

Damit erzeugt ein bloßer Refresh bei unverändertem fachlichem Zustand keine zusätzlichen Kosten.

### 9.2 Quoten, Provider und Logging

Block 8 verwendet dieselben Betriebsgrenzen und denselben Providerpfad wie Block 4 beziehungsweise Block 7:

- bestehender OpenRouter-Transport,
- bestehende Timeout-, Input-, Output-, User-, Context- und Global-Limits,
- bestehende Token-/Kostenfelder und Einheiten,
- bestehende Fehlerklassifikation soweit fachlich passend,
- keine neue Billing- oder Logging-Ablage,
- keine Rohprompts oder vollständigen Providerantworten in Standardlogs.

Falls für Block 8 ein kleiner domänenspezifischer Laufnachweis erforderlich ist, referenziert er dieselben Kosten-/Tokenmetadaten und Quotenmechanismen; er wird nicht zu einer generischen AI-Run-Plattform erweitert.

## 10. UI-Leitplanke

Keine neue Delivery-Anwendung und kein neuer Wizard.

Die bestehende Delivery-UI wird nur um die für Block 8 erforderliche Transparenz ergänzt:

- Anzahl gemappter Felder,
- offene Gaps,
- Konflikte,
- stale Sources,
- pro relevantem Feld nachvollziehbare Source-/Versionsangabe,
- verständlicher Vergleich bei Konflikten.

Der primäre bestehende Delivery-Workflow und die Section Reviews bleiben unverändert erkennbar.

## 11. Teststrategie

Mindestens folgende Invarianten werden regressiv abgesichert:

1. gleiche fachliche Source-Evidenz und gleiche Regelversion ergeben denselben fachlichen Mapping-Zustand,
2. Determinismus wird auf fachlichen Feldwerten und kanonischen Evidence-Hashes geprüft; volatile Zeitstempel und Laufmetadaten werden eingefroren oder aus dem byte-identischen Vergleich ausgeklammert,
3. jedes gemappte Feld besitzt nachvollziehbare Sources und Versionen,
4. fehlende Source ergibt Gap statt Defaulttext,
5. ein bislang nie gemapptes und leeres Feld übernimmt erstmals verfügbare valide Evidenz direkt,
6. manuell veränderter Delivery-Inhalt wird niemals still überschrieben,
7. semantisch identische strukturierte Evidenz erzeugt trotz Formatierungsunterschieden keinen falschen Konflikt,
8. Source-Änderung nach Snapshot bleibt sichtbar,
9. echte Mapper-Änderung setzt nur die betroffene Review-Sektion zurück,
10. unverändertes Mapping löst keinen Review-Reset aus,
11. `handed_over` bleibt unveränderlich,
12. keine Business-/Technical-Bestätigung, Readiness, Approval-, Handover- oder Lifecycle-Aktion wird automatisch gesetzt,
13. deterministischer Mapper funktioniert ohne API-Key und bei Providerfehler unverändert,
14. gleicher LLM-Evidence-Hash erzeugt keinen zweiten Provideraufruf,
15. bestehende Legacy-Packages bleiben ohne expliziten Refresh unverändert.

## 12. Verbindliche Arbeitspakete

### AP 1 – V1-Feldkatalog und Mapping-Vertrag

- statische V1-Zielfeldliste fixieren,
- je Feld erlaubte Sources, Source-Priorität, Transformationsregel, erforderliche Version, Mehrquellenverhalten, Konfliktregel, Pflichtlücke und optionale LLM-Restaufgabe dokumentieren,
- Scope-Grenzen insbesondere für Approval-/Handover-Daten explizit festhalten,
- bekannte Legacy-Placeholder katalogisieren,
- Tests für Registry-Vollständigkeit und verbotene Zielfelder vorbereiten.

**Abnahme:** Für jedes V1-Feld existiert eine eindeutige Mapping-Spezifikation; keine nicht katalogisierten Delivery-Felder können vom Block-8-Mapper beschrieben werden.

### AP 2 – Evidence-Snapshot, Source-Hierarchie und Evidence-Hash

- kanonischen Block-8-Evidence-Snapshot aus regulären Domänenobjekten aufbauen,
- Source-Hierarchie und erforderliche Fachversionen implementieren,
- strukturierte Normalisierung und Evidence-Hash definieren,
- immutable Lösungsentscheidungs-Snapshots dort verwenden, wo lösungsspezifische Zusatzinformationen benötigt werden,
- volatile Zeitstempel vom fachlichen Determinismus trennen.

**Abnahme:** Gleiche fachliche Evidence erzeugt denselben Hash; geänderte fachliche Source-Daten verändern ihn deterministisch.

### AP 3 – Direkte deterministische Mappings

- direkte 1:1-Mappings für priorisierte Felder implementieren,
- leere Pflichtquellen als Gap behandeln,
- keine generischen Ersatztexte erzeugen,
- Mapping-Metadaten pro Feld vorbereiten.

**Abnahme:** Direkte V1-Felder werden ohne LLM reproduzierbar befüllt; fehlende Sources bleiben sichtbar offen.

### AP 4 – Deterministische Mehrquellen-Komposition

- strukturierte Metrik- und weitere eindeutig zusammensetzbare Felder implementieren,
- lösungs- beziehungsweise architekturspezifische Zusatzinformationen nur aus bestätigten Sources zusammensetzen,
- gerenderten Text von kanonischem Evidence-Zustand trennen,
- keine fachlichen Informationen aus Layout oder Textreihenfolge ableiten.

**Abnahme:** Mehrquellenfelder sind reproduzierbar, source-aware und ohne Provider vollständig ausführbar.

### AP 5 – Gap-, Placeholder- und Konfliktlogik

- drei Schreibzustände `neu/leer`, `unverändert gemappt`, `manuell abweichend` implementieren,
- `mapped/gap/conflict/stale` im bestehenden Manifest führen,
- Legacy-Placeholder erkennen,
- konfliktsicheren Refresh ohne Force-Overwrite implementieren,
- idempotente No-op-Refreshes sicherstellen.

**Abnahme:** Erstmalige Evidenz für ein bisher leeres Feld wird übernommen; manuelle Abweichungen werden niemals still überschrieben.

### AP 6 – Integration in bestehende Delivery-Erzeugung und Refresh

- Mapper in `create_delivery_package()` beziehungsweise vorhandene Delivery-Services integrieren,
- expliziten Refresh für nicht übergebene Packages bereitstellen,
- produktiven Übergang über kleine block-spezifische Konfiguration/Branch-by-Abstraction absichern,
- bestehenden Delivery-Pfad bis zur vollständigen Reife als Fallback erhalten,
- keinen parallelen Workflow oder zweiten Package-Typ einführen.

**Abnahme:** Golden Path bleibt deploybar; neue Packages können den Block-8-Mapper verwenden und bestehende nicht übergebene Packages können kontrolliert refreshed werden.

### AP 7 – Provenance, Staleness, Bestands-Packages und Review-Reset

- vorhandenes `source_manifest` um Block-8-Mappingnachweis ergänzen,
- Staleness mit den neuen Feld-Sources verbinden,
- Bestands-Package-Strategie implementieren,
- echte Mapper-Änderungen an bestehende Section-Review-Reset-Logik anbinden,
- unveränderte Felder ohne Review-Reset behandeln,
- `handed_over` explizit regressiv sperren.

**Abnahme:** Provenance, Staleness, Legacy-Verhalten und bestehende Reviews bleiben konsistent; keine stille Migration bestehender Packages.

### AP 8 – Sichtbare Herkunft, Lücken und Konflikte in bestehender Delivery-UI

- bestehende Delivery-Seite um kompakten Mapping-Status ergänzen,
- Quellen und Versionen für gemappte Aussagen sichtbar machen,
- Gaps, Konflikte und stale Sources verständlich darstellen,
- Konfliktansicht mit zuletzt gemapptem Zustand, aktuellem Delivery-Wert und neuem Source-Zustand,
- keine neue Wizard- oder Paralleloberfläche.

**Abnahme:** Nutzer kann Herkunft und offene Arbeit erkennen, ohne den bestehenden Section-Review-Workflow zu verlassen.

### AP 9 – Optionale LLM-Resttexte, Idempotenz und Provider-Ausfall

- nur nach bestätigtem Bedarf maximal kleine freigegebene Resttextmenge aktivieren,
- Evidence-Hash plus Prompt-/Schema-Version als Cache-Schlüssel verwenden,
- unveränderte Evidence ohne neuen Providercall wiederverwenden,
- Quoten, OpenRouter-Transport, Token-/Kostenmetadaten und Fehlerbehandlung aus Block 4/7 wiederverwenden,
- Rate Limit, Timeout, fehlenden API-Key und ungültige Antwort ohne Verlust deterministischer Ergebnisse behandeln,
- keine automatischen Retry-Schleifen.

**Abnahme:** Provider ist für den deterministischen Block-8-Nutzen optional; gleicher Evidence-Zustand verursacht keinen unnötigen zweiten LLM-Aufruf.

### AP 10 – Real-DEMO, Drift-Schutz und Blockabschluss

- `[Real-DEMO]` über reale Upstream-Domänenobjekte bis zum Delivery Package ausführen,
- direkte Mappings, Mehrquellen-Komposition, Gap, erstmalig verfügbare Evidenz, Konflikt und Staleness nachweisen,
- Gate-Invarianz und Unveränderlichkeit übergebener Packages nachweisen,
- Provider-Ausfall beziehungsweise optionalen LLM-Cache nachweisen,
- fachlichen Referenzzustand mit SHA-256-Drift-Schutz fixieren,
- volatile Zeitstempel aus der fachlichen Referenz entfernen oder deterministisch einfrieren,
- vollständige unveränderte Repository-CI grün abwarten,
- Abschlussdokumentation und Abnahmekriterien aus #124 vollständig nachweisen.

**Abnahme:** Reproduzierbarer fachlicher Endzustand, vollständige Gate-Regression, Drift-Schutz und geschlossener Block ohne Änderung an #116.

## 13. PR- und Merge-Regel

- Dieser Workplan wird über einen eigenen PR vor AP 1 fixiert.
- Danach erhält jedes AP einen eigenen Branch, eigenen Commit und eigenen PR.
- Arbeitspakete werden streng sequenziell umgesetzt.
- Das nächste AP beginnt erst nach vollständig grüner unveränderter Repository-CI und Merge des vorherigen APs.
- Nach jedem Merge wird der zugehörige Punkt in Issue #124 abgehakt.
- Issue #124 wird erst nach AP 10, vollständigem Abschlussnachweis und grünem finalen `main` geschlossen.
- Issue #116 wird nicht verändert.

## 14. Definition of Done

Block 8 ist abgeschlossen, wenn:

- alle zehn Arbeitspakete gemergt sind,
- die identische AP-Checkliste in #124 vollständig abgehakt ist,
- alle Abnahmekriterien aus #124 erfüllt sind,
- der deterministische Mapper ohne LLM vollständig funktioniert,
- Gaps, Konflikte, Provenance und Staleness sichtbar bleiben,
- keine automatische Bestätigung, Freigabe oder Übergabe erfolgt,
- Provider-Ausfall deterministische Ergebnisse nicht verändert,
- bestehende Delivery-Reviews und Immutability-Regeln unverändert wirksam sind,
- `[Real-DEMO]` und Drift-Schutz reproduzierbar grün sind,
- die vollständige Repository-CI auf dem finalen `main` grün ist.