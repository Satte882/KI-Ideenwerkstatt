# Accelerator Block 6: Verbindlicher Arbeitsplan

**Issue:** #122  
**Übergeordneter Plan:** #116, unverändert  
**Ausgangsstand:** `main` auf `18e17003d0d8a3c4c302e4bf37e92b2c0d0ef5c2` nach vollständigem Abschluss von Block 5  
**Ziel:** Strukturierte gelbe Felder sowie Value-Stream-Phasen und Prozessanalysen kontrolliert, nachvollziehbar und atomar in bestehende Entwurfsobjekte übernehmen.

## 1. Verbindliche Blockgrenze

Block 6 erweitert den feldweisen Block-5-Pfad nicht zu einem universellen Importer. Er führt einen eigenen, eng begrenzten Structured-Adoption-Pfad für genau drei fachliche Kandidatenarten ein:

1. Metrikgruppe eines bestehenden Use Cases,
2. neue `ValueStreamStage` eines bestehenden Value Streams,
3. neue `ProcessAnalysis` als Entwurf an einer bestehenden oder im selben Batch neu angelegten Phase.

Der bestehende Value Stream beziehungsweise Use Case bleibt das bereits angelegte und an die Capture Session gebundene Root-Entwurfsobjekt. Block 6 erzeugt weder automatisch einen neuen Value Stream noch automatisch einen neuen Use Case. Fehlt das Root-Objekt, wird es über den regulären Erstellungsdialog angelegt und anschließend an die Capture Session gebunden.

Nicht gebaut werden:

- generischer Schema-Mapper,
- ContentType-basierter Objektgenerator,
- frei konfigurierbare Objektgraph-Engine,
- automatische Personen- oder Rollenauflösung,
- Einheitenumrechnung,
- Sammelübernahme ohne Einzelprüfung,
- Fokus-, Validierungs-, Bewertungs-, Freigabe-, Governance-, Delivery- oder Lifecycle-Aktion.

## 2. Verifizierte Gap-Analyse gegen `main`

### 2.1 Wiederzuverwendende Bausteine

| Bereich | Befund auf `main` | Verbindliche Folgerung für Block 6 |
|---|---|---|
| Capture-Katalog | `catalogs.py` enthält die sieben Use-Case-Metrikpfade, wiederholbare Phasenpfade und Prozessanalysepfade. Wiederholbare Ziele besitzen bereits lokale `target_group_key`-Schlüssel. | Kein neuer Erfassungswizard und kein zweites Gruppenschlüsselkonzept. |
| Extraktionsvertrag | `CaptureFieldSuggestion` und `extraction_contract.py` kennen `integer`, `decimal`, `enum`, `boolean`, `date`, `uuid` und `reference`; Dezimalwerte bleiben zunächst Strings. | Der Providerwert bleibt Vorschlag. Kanonische Interpretation erfolgt deterministisch nach der Extraktion. |
| Block-5-Adoption | Zielbindung, Berechtigungsprüfung, Candidate-Reservierung, feldbezogener Snapshot, Konflikterkennung, Idempotenz und Audit existieren für einfache Textfelder. | Sicherheitsprinzipien wiederverwenden, aber strukturierte Objektkandidaten nicht in die Textfeld-Registry pressen. |
| Konfliktmaßstab | Block 5 vergleicht den kanonischen Wert des konkreten Zielfelds. Eine Änderung von `updated_at` allein blockiert nicht. | Auch Block 6 prüft nur fachlich relevante Felder, Slots und Abhängigkeiten; kein Gesamtobjekt-Fingerprint als alleiniger Konfliktgrund. |
| Use-Case-Validierung | `UseCaseForm` lokalisiert Decimal-Felder und prüft Prozentbereich sowie Baseline/Ziel/Richtung gemeinsam. Referenz-Querysets und Berechtigungsabhängigkeiten werden im Form aufgebaut. | Metrikwerte werden über einen vollständigen Formlauf validiert; Regeln werden nicht dupliziert. |
| Phasenmodell | `ValueStreamStage` verlangt `value_stream`, positive `sequence` und `name`; `(value_stream, sequence)` ist eindeutig. `ValueStreamStageForm` ist der reguläre Schreibpfad. | Phasen werden explizit sortiert, gegen bestehende Sequenzen geprüft und ausschließlich über das Form gespeichert. |
| Prozessanalyse | `ProcessAnalysis` gehört zwingend zu einer Phase, startet als `draft`, besitzt Pflichtfelder und `source_snapshot`. `ProcessAnalysisForm` verhindert eine direkte neue Setzung auf `validated`. | Neue Analysen werden mit erzwungenem `draft` und Accelerator-Herkunft angelegt. |
| Atomare Graphanlage | Der Block-2-Blueprint-Importer zeigt Form-Wiederverwendung, geordnete Anlage und `transaction.atomic`. Er erzeugt jedoch einen vollständigen Szenariographen. | Nur technische Muster übernehmen; `apply_blueprint` darf im Block-6-Nutzerpfad nicht aufgerufen werden. |
| Herkunft | Prozessanalysen besitzen bereits einen konkreten `source_snapshot`. Block 5 besitzt ein dauerhaftes, von Rohdaten-Retention getrenntes Adoption-Audit. | Structured Adoption erhält einen eigenen Herkunfts- und Auditnachweis mit Capture-, Analyse-, Item- und Bestätigungsbezug. |

### 2.2 Tatsächlich freigegebener V1-Scope

Die Block-1-Foundation klassifiziert Rollenreferenzen, Booleans und Datumsfelder grundsätzlich. Der aktuelle Capture-Katalog bietet für Block 6 jedoch keine konkrete referenzielle Personenrolle, kein gelbes Boolean-Zielfeld und kein gelbes Datums-Zielfeld des Erstentwurfs an.

Daher gilt für Version 1:

- **aktiv unterstützt:** Metrikfelder, die dafür benötigten Enums, Phasenreihenfolge, Phasenfelder und Prozessanalysefelder;
- **weiterhin feldweise über Block 5:** bereits freigegebene grüne Textfelder;
- **fail-closed abgelehnt:** nicht katalogisierte Rollen-/Referenz-, Boolean- und Datumsziele;
- **nur als Sicherheitstest:** unbekannte oder hypothetische `reference`, `boolean` und `date`-Vorschläge erzeugen keine Übernahmeaktion und keine Fachobjektänderung.

Damit wird keine spekulative Rollenauflösung vorgezogen. Eine spätere Erweiterung benötigt einen konkreten katalogisierten Zielpfad, eine neue Gap-Analyse und eine explizite Whitelist.

### 2.3 Scope-Matrix

| Kandidat | V1-Verhalten |
|---|---|
| Metrikname, Metriktyp, Richtung, Einheit, Baseline, Ziel, Messmethode | strukturiert interpretieren, einzeln bestätigen, als konsistente Gruppe committen |
| `ValueStreamStage.sequence` | Ganzzahl, positive Reihenfolge, Sequenzkonfliktprüfung |
| übrige katalogisierte Phasenfelder | gruppiert je `target_group_key`, reguläre Formvalidierung |
| katalogisierte Prozessanalysefelder | genau eine Analyse je Batch, reguläre Formvalidierung, Status erzwungen `draft` |
| `solution_type`, `hosting_type` oder andere katalogisierte Enums | nur aufnehmen, wenn AP 1 sie anhand Block 1 und des aktuellen Katalogs ausdrücklich in die statische V1-Whitelist bestätigt; sonst fail-closed |
| Scope-Felder oder strukturierte Baseline-Texte außerhalb der drei Kandidatenarten | keine implizite Aufnahme; nur nach expliziter AP-1-Feldfreigabe |
| Personen-, Rollen- und Fremdschlüsselreferenzen | nicht aktiv unterstützt; unbekannte Referenzen werden abgelehnt |
| Booleans und Datumsfelder | nicht aktiv unterstützt; unbekannte Ziele werden abgelehnt |
| rote oder systemverwaltete Felder | immer abgelehnt |

## 3. Architekturentscheidungen

### 3.1 Eigener Structured-Adoption-Pfad

Block 6 erhält separate Batch- und Item-Modelle. Die endgültigen Modellnamen werden in AP 1 bestätigt; fachlich erforderlich sind:

- ein Batch für genau einen bestätigten atomaren Schreibversuch,
- strukturierte Items der Typen `metric_set`, `value_stream_stage` und `process_analysis`,
- stabile lokale Schlüssel und explizite Abhängigkeiten,
- eine dauerhafte Auditspur für Erfolg, Konflikt, Invalidierung und Fehler.

Keine dynamischen Modellnamen, keine ContentTypes und keine frei interpretierbaren Relationen.

### 3.2 Original, Interpretation und Entscheidung

Jedes Item hält getrennt:

- Originalaussage und Quellfrage,
- Provider-Vorschlag,
- kanonisch interpretierten Wert,
- erwarteten Datentyp und Einheit,
- Validierungsstatus und neutrale Fehlercodes,
- Nutzerentscheidung einschließlich bearbeitetem Wert,
- tatsächlich gespeicherten Wert oder erzeugte Objekt-ID.

Die UI zeigt vor jeder Bestätigung genau diese Ebenen. Ein Provider-Vorschlag wird nie unmittelbar persistiert.

### 3.3 Teilverwerfung und Abhängigkeitsgraph

Phasen und Prozessanalyse werden über stabile lokale Schlüssel verbunden. Für Abhängigkeiten gilt:

- Eine Prozessanalyse darf auf eine bestehende Phase desselben Value Streams oder auf genau einen neuen Phasenkandidaten im selben Batch zeigen.
- Eine freie Namenssuche oder heuristische Auflösung ist verboten.
- Wird die referenzierte neue Phase verworfen, ungültig, superseded oder konfliktbehaftet, wird das abhängige Prozessanalyse-Item automatisch als `dependency_invalid` beziehungsweise gleichwertig invalidiert.
- Cascade-Invalidierung erfolgt serverseitig und wird in UI und Audit sichtbar. Eine vorherige Bestätigung der Prozessanalyse bleibt nicht ausführbar.
- Wird die Phase später korrigiert und erneut gültig bestätigt, muss die Prozessanalyse wegen des geänderten Abhängigkeitsstands erneut geprüft und bestätigt werden.

### 3.4 Metrik-Merge-Semantik

Der Nutzer muss nicht zwingend alle sieben Metrikfelder neu bestätigen. Der Commit ist dennoch atomar für den effektiven vollständigen Metrikzustand.

Für jedes Metrikfeld gilt genau eine Quelle:

- `confirmed_proposal`: bestätigter interpretierter Vorschlag,
- `confirmed_edited`: vom Nutzer bearbeitet bestätigter Wert,
- `current_database`: nicht bestätigter oder verworfener Vorschlag; der aktuelle Datenbankwert bleibt maßgeblich.

Unbestätigte Felder werden niemals aus dem Vorschlag übernommen. Unmittelbar vor dem Commit wird der aktuelle Use Case neu geladen; nur bestätigte Felder ersetzen die aktuellen DB-Werte. Der daraus gebildete vollständige Form-Payload wird durch `UseCaseForm` validiert.

Folgen:

- Teilbestätigung ist zulässig.
- Die Datenbankänderung ist alles-oder-nichts.
- Widersprüche zwischen bestätigten und aktuellen Werten blockieren den Commit mit konkreten Formfehlern.
- Die Auditspur dokumentiert pro Metrikfeld die tatsächlich verwendete Quelle.

### 3.5 Deterministische Zahlen- und Einheiteninterpretation

Unterstützt werden ausschließlich explizit definierte deutsche Formate und Aliaslisten. Mindestens zu behandeln sind:

- `1.234,56` → `1234.56`,
- `1 234,56` sowie geschützte Leerzeichen → `1234.56`,
- `12,5 %` → Wert `12.5`, Einheit `%`,
- eindeutige Schreibweisen wie `8,25 min`.

Mehrdeutige oder widersprüchliche Angaben werden nicht geraten. Insbesondere gilt:

- `1,234` ist ohne weiteren eindeutigen Kontext unklar, weil Komma sowohl Dezimal- als auch Tausenderfunktion haben könnte;
- genau drei Stellen nach einem einzelnen Trennzeichen werden nicht automatisch als Dezimalwert interpretiert;
- gemischte Formate wie `1,234.56`, Wertebereiche, freie Multiplikatoren wie „Mio.“, mehrere Einheiten und implizite Umrechnungen bleiben unklar;
- Einheiten werden nur über statische Aliaslisten kanonisiert; es erfolgt keine Umrechnung.

### 3.6 Enum- und Ambiguitätsregel

Enums werden ausschließlich über eine statische Feld-Whitelist und die tatsächlichen Django-Choices verarbeitet.

Zulässig sind:

- exakter kanonischer Wert,
- exakt ein dokumentiertes Alias mit eindeutigem Ziel.

Unzulässig beziehungsweise unklar sind:

- natürliche Formulierungen, die zu mehreren Choice-Werten passen,
- unbekannte Synonyme,
- gemischte oder konditionale Aussagen,
- Providerwerte außerhalb der Feld-Whitelist.

Die Normalisierung liefert deshalb nicht nur `valid` oder `invalid`, sondern mindestens `valid`, `ambiguous` und `invalid`. `ambiguous` bietet keine direkte Übernahme.

### 3.7 Feld- und itembezogener Konfliktschutz

Ein Gesamtobjekt-`updated_at` blockiert einen Batch nicht allein.

Konfliktmaßstab:

- Metrik: nur bestätigte Metrikfelder werden gegen ihren Feldsnapshot verglichen. Nicht bestätigte Felder werden frisch aus der Datenbank übernommen.
- Neue Phase: relevante Sequenzslots und gegebenenfalls explizit referenzierte bestehende Phasen werden geprüft. Eine unabhängige Textänderung am Value Stream ist kein Konflikt.
- Prozessanalyse an bestehender Phase: Existenz, Zugehörigkeit zum gebundenen Value Stream und die für die Referenz relevante Identität werden geprüft. Unabhängige Änderungen an anderen Phasen blockieren nicht.
- Prozessanalyse an neuer Phase: Gültigkeit und bestätigter Zustand des lokalen Phasenitems sind maßgeblich.

`updated_at`-Änderungen werden protokolliert, erzeugen aber nur bei fachlich relevantem Snapshot-Delta einen Konflikt.

### 3.8 Lock-Reihenfolge

Alle mutierenden Structured-Adoption-Aktionen verwenden dieselbe Reihenfolge:

1. Batch-Zeile reservieren und sperren,
2. gebundenes Root-Zielobjekt sperren,
3. relevante bestehende Phasenzeilen in stabiler UUID-/ID-Reihenfolge sperren,
4. strukturierte Items in stabilem lokalen Schlüssel sortiert sperren beziehungsweise erneut laden,
5. Berechtigung, Gültigkeit, Abhängigkeiten und Snapshots erneut prüfen,
6. Forms vorbereiten und validieren,
7. Fachobjekte in definierter Reihenfolge speichern,
8. Postconditions, Audit und Batchabschluss innerhalb derselben Transaktion schreiben.

Diese Reihenfolge gilt auch für Retry- und Konfliktpfade. Es darf keinen alternativen Pfad geben, der zuerst Phasen und danach das Root-Objekt sperrt.

### 3.9 Idempotenz und Retry

Jeder Commitversuch besitzt einen stabilen Idempotency-Key aus Session, Analyse, Ziel, bestätigter Auswahl und Interpretationsversion.

- Nur ein Request kann einen offenen Batch nach `processing` reservieren.
- Nach erfolgreichem Commit wird das Batchergebnis in derselben Transaktion terminal gespeichert. Ein wiederholter Request liefert dieses Ergebnis zurück.
- Bei Rollback bleiben keine Phasen oder Prozessanalysen bestehen.
- Ein kontrollierter Retry desselben fehlgeschlagenen Batches darf keine Duplikate erzeugen und erhöht einen nachvollziehbaren Versuchszähler.
- Falls die Fachobjekte erfolgreich gespeichert wurden, kann der Batchstatus nicht außerhalb derselben Transaktion fehlen.
- Eindeutigkeitsconstraints und erzeugte Objekt-IDs werden zusätzlich als Schutz verwendet, ersetzen aber nicht die Service-Idempotenz.

### 3.10 Atomare Schreibgruppen

- Use-Case-Batch: bestätigte Metrikfelder als eine vollständige, validierte Metrikgruppe.
- Value-Stream-Batch: alle bestätigten neuen Phasen plus die davon abhängige bestätigte Prozessanalyse.

Eine Prozessanalyse kann nicht ohne ihre bestätigte neue Phase gespeichert werden. Scheitert ein Item, wird der vollständige fachliche Batch zurückgerollt. Eine bewusste Nutzerverwerfung vor Commit reduziert den ausgewählten Graphen; sie erzeugt keinen Teilfehler.

### 3.11 Fehleraudit

Ein fehlgeschlagener Batch wird nach dem fachlichen Rollback in einer getrennten kurzen Audit-Transaktion protokolliert. Das Audit nennt mindestens:

- Batch- und Idempotency-Key,
- Versuchszähler,
- fehlgeschlagenen Schritt,
- konkreten Item-Typ und lokalen Item-Key,
- gegebenenfalls Zielfeld,
- neutralen Fehlercode,
- konkrete Form- oder Abhängigkeitsfehler,
- Actor, Analyse, Session und Ziel-Snapshots.

Ein pauschales Ergebnis „Batch fehlgeschlagen“ ohne Item- oder Schrittbezug ist nicht ausreichend.

### 3.12 Herkunft

Für neu erzeugte Prozessanalysen wird `source_snapshot` mit einem expliziten Accelerator-Schema befüllt. Es referenziert mindestens:

- Capture Session und Revision,
- Capture Analysis und Extraktionsversion,
- Quellfragen und Originalausschnitte beziehungsweise deren datensparsame Hashes,
- Structured-Adoption-Batch und Items,
- bestätigenden Nutzer und Zeitpunkt,
- lokale oder bestehende Phasenreferenz.

Rohantworten und vollständige Providerantworten werden nicht unkontrolliert in dauerhafte Audits dupliziert.

### 3.13 Gate-Postconditions

Nach jedem erfolgreichen Block-6-Commit wird technisch geprüft:

- `ProcessAnalysis.status == draft`,
- keine neue `ProcessValidation`,
- keine Value-Stream- oder Phasenfokusentscheidung,
- keine bevorzugte Lösungsoption und keine Lösungsentscheidung,
- keine Use-Case-Entscheidung oder Freigabe,
- keine Governance-Entscheidung,
- keine Delivery-Bestätigung,
- keine Lifecycle-Änderung.

Verletzt eine Postcondition diese Grenze, wird der vollständige Batch zurückgerollt.

## 4. Verbindliche Arbeitspakete

Der vorliegende Workplan ist ein vorgelagerter Planungs-PR und ersetzt keines der folgenden zehn Arbeitspakete. Jedes Arbeitspaket erhält genau einen eigenen Commit und einen eigenen Pull Request. Die Checkliste in Issue #122 verwendet exakt dieselben Titel. Abhaken und Merge erfolgen erst nach grüner unveränderter CI und dokumentierter Abnahme.

### AP 1 – Strukturierter Vertrag, Feldfreigabe und Abhängigkeitsgraph

- Exakte V1-Feldmatrix gegen Block 1, Capture-Katalog, Extraktionsvertrag, Models und Forms festschreiben.
- Statische Kandidatentypen und lokale Referenzen definieren.
- Aktive Enumfelder ausdrücklich benennen.
- Nicht katalogisierte Rollen-, Boolean- und Datumsziele fail-closed festlegen.
- Cascade-Invalidierung für abhängige Items definieren.
- Vertrags- und Denylist-Tests ergänzen.

**Abnahme:** Kein Zielpfad kann allein aufgrund seines Provider-Feldtyps in den Schreibpfad gelangen.

### AP 2 – Deterministische Typ-, Zahlen- und Ambiguitätsnormalisierung

- Deutschen Decimal-Parser, Tausendertrennzeichen und Unicode-Leerzeichen implementieren.
- Einheitenalias und Prozentbehandlung implementieren.
- `1,234` und vergleichbare Dreiergruppen als unklar behandeln.
- Enum-Whitelist, dokumentierte Aliase und `ambiguous`-Status implementieren.
- Unsupported-Tests für Boolean, Datum und Referenz ergänzen.

**Abnahme:** Jede Interpretation ist reproduzierbar; unklare Werte besitzen keine direkte Übernahmeaktion.

### AP 3 – Batch-, Item- und Audit-Persistenz

- Eng begrenzte Batch-, Item- und Auditmodelle mit Migration einführen.
- Statusmodell, stabile lokale Keys, Abhängigkeiten, Entscheidungs- und Interpretationssnapshots abbilden.
- Idempotency-Key und Versuchszähler absichern.
- Retention und Löschverhalten gegen Capture-Rohdaten dokumentieren und testen.

**Abnahme:** Herkunft und terminale Ergebnisse bleiben nachvollziehbar, ohne Rohdaten unnötig zu duplizieren.

### AP 4 – Metrik-Merge und feldbezogener Konfliktschutz

- Metrik-Items aus den sieben Zielpfaden gruppieren.
- Pro Feld `confirmed_proposal`, `confirmed_edited` oder `current_database` festlegen.
- Nur bestätigte Felder gegen ihren Feldsnapshot prüfen.
- Effektiven vollständigen Payload über `UseCaseForm` validieren und atomar speichern.
- Prozent-, Richtung-, Baseline- und Zielkonsistenz testen.

**Abnahme:** Teilbestätigung ist möglich, aber es existiert niemals ein teilweise geschriebener Metrikzustand.

### AP 5 – Value-Stream-Phasen und Cascade-Invalidierung

- Phasenitems anhand `target_group_key` bilden.
- Pflichtfelder, positive Reihenfolge, doppelte lokale Sequenzen und DB-Sequenzkollisionen prüfen.
- `ValueStreamStageForm` als alleinigen Schreibpfad verwenden.
- Verwerfen oder Invalidieren einer Phase auf abhängige Prozessanalyse-Items kaskadieren.
- Phasen in deterministischer Reihenfolge erzeugen.

**Abnahme:** Keine abhängige Prozessanalyse bleibt nach Verwerfung oder Fehler ihrer neuen Phase ausführbar.

### AP 6 – Prozessanalyse, lokale Referenzen und Herkunft

- Prozessanalyseitem aus katalogisierten Feldern bilden.
- Referenz ausschließlich auf bestehende zulässige Phase oder lokalen Phasenschlüssel erlauben.
- `ProcessAnalysisForm` verwenden und `status=draft` serverseitig erzwingen.
- Accelerator-`source_snapshot` schreiben.
- Keine Prozessvalidierung, Fokus- oder Lösungsentscheidung erzeugen.

**Abnahme:** Jede neue Analyse gehört nachweisbar zu genau einer zulässigen Phase und bleibt ein unvalidierter Entwurf.

### AP 7 – Atomare Orchestrierung, Lock-Reihenfolge und Idempotenz

- Einheitlichen Orchestrierungsservice mit der festen Lock-Reihenfolge implementieren.
- Berechtigung, Item-Snapshots und Abhängigkeiten innerhalb der Transaktion erneut prüfen.
- Use-Case- und Value-Stream-Schreibgruppen vollständig atomar behandeln.
- Repeat-Request, Response-Verlust und Retry nach fehlgeschlagenem Commit idempotent testen.
- Fehleraudit mit Schritt- und Itembezug nach Rollback schreiben.

**Abnahme:** Parallele Batches erzeugen weder Deadlocks durch wechselnde Lock-Reihenfolge noch doppelte Fachobjekte.

### AP 8 – Review-UI, Teilverwerfung und Bestätigung

- Original, Vorschlag, Interpretation, Typ/Einheit und Validierung pro Item anzeigen.
- Metrikfelder mit ihrer effektiven Quelle darstellen.
- Phasen sortiert und Prozessanalyse mit sichtbarer Abhängigkeit anzeigen.
- Einzelne Bestätigung, Bearbeitung und Verwerfung anbieten.
- Cascade-Invalidierung und notwendige erneute Bestätigung verständlich anzeigen.
- Keinen „Alle übernehmen“-Pfad einführen.

**Abnahme:** Kein Wert oder Objekt wird ohne sichtbare Einzelentscheidung Teil des Commit-Batches.

### AP 9 – Sicherheits-, Rollback- und Gate-Regression

- Berechtigungs-, Fremdziel-, Stale-, Konflikt- und Manipulationstests ergänzen.
- Rollback an jedem relevanten Schreibschritt erzwingen und nachweisen.
- Feste Lock-Reihenfolge und konkurrierende Batches testen.
- Gate-Postconditions und unveränderte rote Zustände vor/nach Commit prüfen.
- Desktop- und Mobile-Review ohne horizontalen Overflow verifizieren.

**Abnahme:** Fehler hinterlassen keinen inkonsistenten Objektgraphen und setzen keine Entscheidung oder Bestätigung.

### AP 10 – Real-DEMO, Drift-Schutz und Blockabschluss

- Reproduzierbaren Real-DEMO-Durchlauf ausschließlich über den neuen Structured-Adoption-Pfad erstellen.
- Direkte oder indirekte Nutzung von `apply_blueprint` im Real-DEMO durch Test beziehungsweise Spy ausdrücklich ausschließen.
- Metrik-Merge, mehrere Phasen, lokale Prozessreferenz, Teilverwerfung, Cascade-Invalidierung und einen Rollback-Fall nachweisen.
- Referenzartefakt mit Checksum-/Drift-Schutz ergänzen.
- Vollständige Regression, CI, UI-Evidenz und Completion-Dokumentation liefern.

**Abnahme:** Der erweiterte Erfassungs-MVP ist reproduzierbar belegt; der alte Blueprint-Importer war an keinem Block-6-Nutzerschritt beteiligt.

## 5. PR- und Ausführungsprotokoll

1. Dieser Workplan wird in einem eigenen ersten Pull Request gemergt.
2. Issue #122 erhält eine Checkliste mit exakt den zehn AP-Titeln aus Abschnitt 4.
3. AP 1 bis AP 10 werden strikt nacheinander umgesetzt.
4. Jedes AP besitzt genau einen eigenen fachlichen Commit und einen eigenen Pull Request.
5. Ein AP wird erst nach grüner, unveränderter CI, Review der Abnahmekriterien und Merge abgehakt.
6. Folge-APs starten jeweils vom dann aktuellen `main`.
7. Abweichungen vom Workplan werden im betroffenen PR begründet; #116 wird nicht geändert.
8. Issue #122 wird erst nach AP 10, vollständigem Abschlussnachweis und erfüllten Abnahmekriterien geschlossen.

## 6. Definition of Done für Block 6

Block 6 ist abgeschlossen, wenn:

- alle zehn APs gemergt und in Issue #122 abgehakt sind,
- der sichtbare Scope auf die bestätigten Golden-Path-Felder und zwei Entwurfsobjekttypen begrenzt bleibt,
- Original, Interpretation, Validierung und Bestätigung nachvollziehbar sind,
- unklare Zahlen und Enums nicht geraten werden,
- nicht katalogisierte Rollen-, Boolean- und Datumsziele fail-closed bleiben,
- Metriken nach dokumentierter Merge-Semantik atomar gespeichert werden,
- Phasenverwerfung abhängige Prozessanalyse-Items kaskadierend invalidiert,
- Konflikte nur fachlich relevante Felder und Abhängigkeiten betreffen,
- die feste Lock-Reihenfolge und Retry-Idempotenz nachgewiesen sind,
- Fehleraudits das konkrete Item und den konkreten Schritt benennen,
- keine rote Entscheidung oder Bestätigung verändert wurde,
- die Real-DEMO ausschließlich den Structured-Adoption-Pfad verwendet,
- vollständige CI, Regression, UI-Evidenz und Drift-Schutz grün sind.
