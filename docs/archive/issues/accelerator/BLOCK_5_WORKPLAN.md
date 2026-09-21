# Accelerator Block 5: Verbindlicher Arbeitsplan

**Issue:** #121  
**Übergeordneter Plan:** #116, unverändert  
**Ausgangsstand:** `main` auf `48927f1009dced414e9b4e8a0e6a9f574e450fdb` einschließlich Realbetrieb-Fix #163/#164  
**Ziel:** Sichere, feldweise und konfliktgeschützte Übernahme freigegebener grüner Textfelder als erster Nutzer-MVP.

## 1. Verifizierter Ausgangspunkt

Der Arbeitsplan basiert auf dem aktuellen Repository-Stand und nicht allein auf den Planannahmen aus #121.

- `CaptureFieldSuggestion` speichert Zielobjekttyp, Zielpfad, optional eine Zielobjekt-ID, Vorschlagswert, Quelle und Unsicherheit. Der aktuelle Block-4-Pfad befüllt jedoch keine belastbare Zielbindung, keinen Feld-Ausgangssnapshot und keinen Übernahmestatus.
- Die regulären Bearbeitungsrechte sind bereits zentral definiert: `can_edit_value_stream(user, value_stream)` und `can_edit_use_case(user, use_case)`. Die normalen Update-Views verwenden genau diese Funktionen nach `login_required`; Block 5 führt keine parallele Rollenlogik ein.
- `ValueStreamForm` und `UseCaseForm` sind die maßgeblichen Validierungspfade. Sie enthalten neben Modellfeldern auch dynamische Referenzfilter, Fachlabels und zusätzliche Validierungen. Adoption-Adapter müssen diese Forms beziehungsweise daraus extrahierte gemeinsame Domain Services verwenden.
- Block 1 klassifiziert `ValueStream.scope_in` und `scope_out` als gelb. Sie sind daher trotz vorhandener Extraktionspfade nicht Teil von Block 5.
- Die Block-4-Retention lässt abgeschlossene Capture Sessions standardmäßig nach 90 Tagen ablaufen und löscht sie nach sieben Tagen Karenz einschließlich Analysen und Vorschlägen kaskadierend. Neue offene Kandidaten dürfen diesem Lebenszyklus folgen; ein dauerhafter Übernahmenachweis darf jedoch nicht unbeabsichtigt mitgelöscht werden.
- `CaptureAnalysis` enthält bereits Provider-, Modell-, Token- und Kostenmetadaten. Der Übernahmenachweis muss auf diesen Lauf zurückführbar bleiben, damit Block 9 LLM-Aufwand und tatsächlich verwendete Vorschläge verbinden kann.
- Es existiert noch kein allgemeines Feature-Flag für die Feldübernahme. Für die sequenzielle Umsetzung wird ein einzelnes, eng begrenztes Accelerator-Flag eingeführt; keine generische Feature-Flag-Plattform.

## 2. Verbindliche Architekturentscheidungen

### 2.1 Genau ein Zielobjekt pro Capture Session

Eine Capture Session darf im MVP an höchstens ein bestehendes Fachobjekt gebunden sein: entweder genau einen `ValueStream` oder genau einen `UseCase`, niemals beide. Ungebundene Sessions bleiben für Erfassung und Vorschau zulässig, bieten aber keine Übernahmeaktion.

Die Bindung wird serverseitig gegen Capture-Typ und Bearbeitungsberechtigung validiert. Explizite nullable Fremdschlüssel mit Datenbank-Constraint werden einer frei interpretierbaren Typ-/UUID-Kombination vorgezogen. Bei Löschung des Fachobjekts darf die Session nicht die Löschung blockieren; Kandidat und Audit halten deshalb zusätzlich unveränderliche Zieltyp- und Ziel-ID-Snapshots.

Diese Ein-Ziel-Grenze ist eine bewusste MVP-Entscheidung. Block 6 darf sie nur mit einer neuen Gap-Analyse erweitern.

### 2.2 Zulässige grüne Felder

Die erste Registry umfasst ausschließlich einfache skalare Textfelder, die Block 1 ausdrücklich als grün klassifiziert und die Block 4 bereits als Zielpfade unterstützt.

**Value Stream:**

- `name`
- `description`
- `trigger`
- `outcome`
- `strategic_objective`
- `stakeholders`
- `constraints`

**Use Case:**

- `title`
- `summary`
- `problem_statement`
- `affected_process`
- `target_users`
- `source_systems`
- `data_sources`
- `interface_description`
- `intended_users`
- `intended_purpose`
- `expected_benefit`
- `benefit_category`
- `human_oversight`
- `support_responsibility`

Gelbe Felder, Referenzen, Enums, Zahlen, Metriken, Scope-Abgrenzungen, Phasen, Prozessanalysen, Lösungsoptionen und alle roten oder systemverwalteten Felder bleiben nicht übernehmbar.

### 2.3 Kanonische Textdarstellung und Hash

Vor Snapshot und Hash wird jeder Textwert deterministisch kanonisiert:

1. Wert muss Text sein; `None` wird als leerer Text behandelt.
2. Unicode wird auf NFC normalisiert.
3. `CRLF` und `CR` werden in `LF` überführt.
4. Führende und abschließende Leerzeichen des gesamten Feldes werden entfernt.
5. Leerzeichen und Tabs am Zeilenende werden entfernt.
6. Interne Leerzeichen, Zeilenumbrüche und Leerzeilen bleiben erhalten.
7. Der SHA-256-Hash wird über die UTF-8-Repräsentation des kanonischen Textes gebildet.

Damit erzeugen reine Plattform- oder Zeilenendeunterschiede keinen Konflikt, während inhaltlich relevante Formatierung nicht still zusammengezogen wird. Snapshot, Hash und Kanonisierungsregel werden separat getestet.

### 2.4 Kandidaten-Gültigkeit und Staleness

Ein Kandidat ist nur ausführbar, wenn gleichzeitig gilt:

- Capture Session ist `completed` und weder `expired` noch `discarded`.
- Zeitpunkt liegt vor `session.expires_at`.
- Analyse ist erfolgreich.
- Katalog-, Antwortschema-, Prompt- und Extraktionsschema-Version werden von der aktuellen Block-5-Registry unterstützt.
- Zielbindung stimmt mit Zieltyp und Ziel-ID des Kandidaten überein.
- Zielobjekt existiert und ist nicht archiviert beziehungsweise fachlich deaktiviert.
- Kandidat wurde nicht verarbeitet, ersetzt oder als veraltet markiert.

Es wird kein zweites frei konfigurierbares TTL-System eingeführt. Die natürliche Gültigkeitsdauer folgt der bestehenden Capture-Retention; Versions- und Zielprüfungen verhindern zusätzlich eine blinde Übernahme formal noch nicht abgelaufener Altstände.

### 2.5 Kandidatenstatus, Supersede und Idempotenz

Mindestens folgende Zustände werden explizit modelliert:

- `open`
- `processing`
- `adopted`
- `adopted_edited`
- `rejected`
- `conflict`
- `superseded`
- `stale`

Erzeugt eine neuere erfolgreiche Analyse für dasselbe Zielobjekt und Zielfeld einen neuen Kandidaten, werden ältere nicht terminale Kandidaten für diese Kombination atomar als `superseded` markiert. Erfolgreich übernommene, bearbeitet übernommene und verworfene Kandidaten bleiben unverändert als Historie erhalten.

Eine Übernahme reserviert den Kandidaten durch einen atomaren Compare-and-swap von `open` nach `processing`. Nur genau ein Request kann diesen Übergang erfolgreich durchführen. Zweite Klicks oder parallele Requests verändern weder Zielobjekt noch Audit erneut.

### 2.6 Lock-Reihenfolge und Konfliktmaßstab

Alle mutierenden Aktionen verwenden dieselbe Lock-Reihenfolge:

1. Kandidat reservieren beziehungsweise sperren.
2. Zielobjekt sperren.
3. Berechtigung, Gültigkeit und Feldregistry erneut prüfen.
4. Aktuellen Zielfeldwert kanonisieren und mit dem Kandidaten-Snapshot vergleichen.
5. Regulär validieren und speichern oder einen kontrollierten Ergebniszustand setzen.

Der kanonische Wert des konkreten Zielfelds ist der maßgebliche Konfliktindikator. `updated_at` wird zusätzlich geprüft und protokolliert, führt bei unverändertem Zielfeld aber nicht allein zum Konflikt. Dadurch können zwei Nutzer unterschiedliche Felder desselben Zielobjekts nacheinander übernehmen, ohne einen falschen Konflikt zu erzeugen. Die einheitliche Lock-Reihenfolge verhindert zyklische Sperren.

Ein gelöschtes Zielobjekt liefert `target_missing`; ein archiviertes oder fachlich inaktives Ziel liefert `target_inactive`. Beide Fälle sind von `field_conflict` getrennt.

### 2.7 Explizite Registry und Labels

Es wird keine Reflection-basierte Patch-API gebaut. Jeder erlaubte Zielpfad erhält einen statischen Registry-Eintrag mit Zieltyp, Modellfeld, Form-Adapter, Kanonisierer, Berechtigungsfunktion und Unsicherheitsmodus.

Das Anzeigeetikett wird nicht separat dupliziert. Der Adapter bezieht es vorrangig aus dem tatsächlich gebundenen ModelForm-Feld, weil Forms bewusst fachlich abweichende Labels definieren können, und verwendet nur ersatzweise das `verbose_name` des Django-Modellfelds.

Unbekannte oder inzwischen anders klassifizierte Zielpfade werden fail-closed abgelehnt.

### 2.8 Unsicherheitsregel

Die Regel wird als benannte, zentrale Policy-Mapping-Konstante implementiert und an den drei Enumwerten getestet:

- `low`: direkte Übernahme oder Bearbeitung möglich.
- `medium`: nur bearbeitet übernehmen oder verwerfen.
- `high`: nur Vorschau und verwerfen; keine Übernahmeaktion.

Da Block 4 kategoriale Enumwerte und keine numerischen Confidence-Scores speichert, werden keine künstlichen Grenzwerte und keine Laufzeit-Environment-Settings eingeführt. Die zentrale Mapping-Konstante verhindert Magic Logic und hält die UX-Regel versioniert und testbar.

### 2.9 Audit und LLM-Kostenbezug

Jeder Übernahme-, Bearbeitungs-, Verwerf-, Konflikt-, Stale- und unzulässige Versuch erzeugt einen nachvollziehbaren Ergebnisdatensatz. Er enthält mindestens:

- Kandidaten-, Vorschlags-, Analyse- und Session-ID als unveränderliche Referenz-Snapshots,
- nullable Datenbankreferenzen, soweit die Quellobjekte noch existieren,
- Zieltyp, Ziel-ID und Zielfeld,
- kanonischen Ausgangswert und Hash,
- ursprünglichen Vorschlagswert,
- gegebenenfalls bearbeiteten Wert,
- tatsächlich gespeicherten Wert,
- Benutzer und Zeitpunkte,
- Aktion, Ergebnis und neutralen Fehlercode,
- Quellfrage und Hash des Quellausschnitts,
- Provider, Modell, Katalog-, Prompt- und Schemaversionen,
- Token- und Kostenmetadaten des zugehörigen Analyse-Laufs.

Vollständige Capture-Rohantworten, Prompts, Providerantworten und Quellausschnitte werden nicht dauerhaft in das Audit dupliziert. Block 9 aggregiert LLM-Kosten über eindeutige Analyse-Referenz-IDs und summiert nicht dieselben Laufkosten pro übernommenem Feld mehrfach.

Offene Kandidaten werden mit der Capture Session gelöscht. Das Audit über tatsächlich ausgeführte oder abgelehnte Fachobjektänderungen bleibt datensparsam erhalten und ist von der Rohdaten-Retention entkoppelt. Löschung, Kaskaden und nullable Referenzen werden ausdrücklich getestet.

### 2.10 Feature-Flag und sequenzielle Freischaltung

`ACCELERATOR_FIELD_ADOPTION_ENABLED` schützt Routen und UI, bis Backend, Audit, Retention und Tests vollständig vorliegen. Das Flag ist während der Backend-PRs standardmäßig deaktiviert. Es wird erst mit der vollständigen Review-UI aktiviert. Direkte Requests gegen deaktivierte Routen bleiben serverseitig wirkungslos.

## 3. Verbindliche Arbeitspakete

Jedes Arbeitspaket erhält genau einen eigenen Commit und einen eigenen Pull Request. Ein Paket wird in Issue #121 erst nach Merge und grünem Nachweis abgehakt. Der vorliegende Arbeitsplan ist ein vorgelagerter Planungs-PR und ersetzt keines der zehn Arbeitspakete.

### AP 1 – Gap-Analyse, Feldfreigabe und bestehende Schreibpfade

- `BLOCK_5_GAP_ANALYSIS.md` gegen den dann aktuellen `main` erstellen.
- Alle grünen Zielpfade gegen Block 1 und Block 4 abgleichen.
- Pro Zieltyp reguläre Form, Berechtigungsfunktion, Validierung und Seiteneffekt dokumentieren.
- Bestätigen, welche View-seitigen Effekte in einen gemeinsamen kleinen Domain Service extrahiert werden müssen.
- Abweichungen vom Workplan nur begründet dokumentieren; #116 bleibt unverändert.

**Abnahme:** Vollständige Feldmatrix, keine unbestätigte Schreibannahme, keine technische Implementierung.

### AP 2 – Zielbindung, Feature-Flag und MVP-Grenzen

- Genau-ein-Ziel-Bindung für Value Stream oder Use Case modellieren.
- Datenbank-Constraints für Capture-Typ und Zielkombination ergänzen.
- Zielauswahl ausschließlich aus serverseitig editierbaren Objekten anbieten.
- Zielwechsel nach Kandidatenerzeugung verhindern oder kontrolliert alle offenen Kandidaten invalidieren.
- Feature-Flag mit standardmäßig deaktivierten Adoption-Routen einführen.

**Abnahme:** Fremde, typfalsche und doppelte Zielbindungen sind in Modell, Service und Tests ausgeschlossen.

### AP 3 – Kanonisierung, Snapshot und Kandidaten-Gültigkeit

- Kanonisierer und SHA-256-Regel implementieren.
- `FieldAdoptionCandidate` mit Feldsnapshot, `updated_at`, Versionsdaten und Ziel-Snapshots einführen.
- Gültigkeitsprüfung gegen Session-Retention, Analysezustand, unterstützte Versionen und Zielaktivität implementieren.
- `target_missing`, `target_inactive` und `stale` getrennt abbilden.

**Abnahme:** Formatierungsäquivalenz, echte Inhaltsänderung und veraltete Kandidaten sind deterministisch getestet.

### AP 4 – Kandidatenstatus, Supersede und Idempotenz

- Zustandsautomat einschließlich `processing`, `superseded` und `stale` implementieren.
- Neuere Kandidaten ersetzen ältere nicht terminale Kandidaten desselben Ziels und Felds atomar.
- Compare-and-swap-Reservierung für Übernahme und Verwerfen implementieren.
- Wiederholte oder parallele Requests idempotent behandeln.

**Abnahme:** Genau ein Request kann einen offenen Kandidaten verarbeiten; terminale Historie bleibt unverändert.

### AP 5 – Explizite Feldregistry und Form-Adapter

- Statische Registry für die freigegebenen Value-Stream- und Use-Case-Felder implementieren.
- Labels aus gebundenem Formfeld, ersatzweise aus `verbose_name`, ableiten.
- Kleine Adapter verwenden reguläre Forms oder gemeinsam extrahierte Domain Services.
- Nach der Validierung sicherstellen, dass nur das freigegebene Fachfeld und dokumentierte technische Seiteneffekte geändert werden.
- Unbekannte, gelbe, rote und systemverwaltete Felder fail-closed ablehnen.

**Abnahme:** Keine generische Patch-API; bestehende Formvalidierungen und History bleiben wirksam.

### AP 6 – Atomare Übernahme, Berechtigung und Konfliktschutz

- Einheitlichen Adoption-Service mit fester Lock-Reihenfolge implementieren.
- `can_edit_value_stream` beziehungsweise `can_edit_use_case` unverändert wiederverwenden.
- Feldsnapshot statt globalem `updated_at` als Konfliktmaßstab verwenden.
- Direkte und bearbeitete Einzelübernahme atomar speichern.
- Konflikt, fehlendes Ziel, inaktives Ziel, fehlende Berechtigung und Validierungsfehler getrennt zurückgeben.
- Keine Force-, Merge- oder Sammelschreibfunktion bereitstellen.

**Abnahme:** Zwischenzeitliche Feldänderungen werden nie überschrieben; unterschiedliche Felder desselben Objekts bleiben sequenziell übernehmbar.

### AP 7 – Audit, LLM-Kostenbezug und Retention

- Unveränderliches, datensparsames Adoption-Audit einführen.
- Analyse-Referenz sowie Provider-, Token- und Kostenmetadaten nachvollziehbar verknüpfen.
- Eindeutige Analyse-ID für spätere kostenkorrekte Aggregation erhalten.
- Kandidaten in die bestehende Capture-Retention integrieren.
- Audit von der Kaskadenlöschung der Rohdaten entkoppeln, ohne Rohantworten oder Quellausschnitte dauerhaft zu duplizieren.
- Purge-Command, Kaskaden und Datenschutztests erweitern.

**Abnahme:** Nach Capture-Löschung bleibt der minimale Änderungsnachweis erhalten; offene Kandidaten bleiben nicht unkontrolliert bestehen.

### AP 8 – Review-UI, Unsicherheitsregeln und Konfliktaktionen

- Feldweise Review mit Ausgangswert, Vorschlag, Quelle, Unsicherheit und Status integrieren.
- Policy-Mapping für `low`, `medium` und `high` zentral anwenden.
- Aktionen „Übernehmen“, „vor Übernahme bearbeiten“ und „Verwerfen“ nur im erlaubten Zustand anzeigen.
- Konflikte mit damaligem, aktuellem und vorgeschlagenem Wert darstellen.
- Konfliktaktionen auf „neu analysieren“, regulär manuell bearbeiten und „verwerfen“ begrenzen.
- Keine globale oder gruppenweise Übernahme anbieten.
- Feature-Flag erst nach vollständiger Backendintegration aktivieren.

**Abnahme:** Desktop und Mobile bleiben ohne Überlauf bedienbar; UI und direkte Requests beachten dieselben serverseitigen Regeln.

### AP 9 – Nebenläufigkeits-, Sicherheits- und Regressionstests

- Manipulationsschutz für Ziel-ID, Zieltyp, Zielfeld, Benutzer und Kandidatenstatus testen.
- CSRF, POST-only, Ownership und fachliche Bearbeitungsberechtigung testen.
- Doppelklick und zwei parallele Übernahmen desselben Kandidaten testen.
- Zwei Nutzer mit unterschiedlichen Feldern desselben Zielobjekts testen: keine Deadlocks und keine falschen Feldkonflikte.
- Ziel gelöscht, archiviert oder zwischenzeitlich geändert testen.
- Formvalidierung, Use-Case-History, erlaubte Seiteneffekte und Nichtänderung aller Gates prüfen.
- Vollständige unveränderte Repo-CI sowie Block-3- und Block-4-Regressionen ausführen.

**Abnahme:** Sicherheits-, Nebenläufigkeits- und Scope-Matrix vollständig grün.

### AP 10 – Real-DEMO, Messung und Blockabschluss

- Reproduzierbaren `[Real-DEMO]`-Durchlauf für Value Stream und Use Case ergänzen.
- Anzahl direkt übernommener, bearbeitet übernommener, verworfener, konfliktbehafteter und ersetzter Kandidaten messen.
- Review- und Korrekturzeit getrennt von Providerwartezeit erfassen.
- LLM-Kosten über eindeutige Analyse-Läufe den tatsächlich verwendeten Feldern gegenüberstellen.
- Eigene UI-Verifikation analog Block 3 und Block 4 ausführen und Artefakte visuell prüfen.
- `BLOCK_5_COMPLETION.md` mit PR-, CI-, Migrations-, Retention-, Sicherheits- und Nicht-Ziel-Nachweis erstellen.
- Issue #121 erst schließen, wenn alle zehn Pakete gemergt, die Checkliste vollständig und die Abnahmekriterien erfüllt sind.

**Abnahme:** Erster Nutzer-MVP real nachgewiesen; keine zusammengezogenen Restimplementierungen in diesem Abschluss-PR.

## 4. PR-Reihenfolge

1. Vorgelagerter Planungs-PR: nur `BLOCK_5_WORKPLAN.md`.
2. AP 1 bis AP 10 strikt sequenziell, jeweils eigener Branch, Commit und PR.
3. Jeder neue Branch startet vom nach dem vorherigen Merge aktualisierten `main`.
4. Issue-Checkliste wird erst nach dem jeweiligen Merge und grüner CI aktualisiert.
5. Kein Sammel-PR, kein paralleles Vorziehen späterer Pakete und keine Änderung von Issue #116.

## 5. Abnahmematrix zu Issue #121

| Kriterium aus #121 | Geplanter Nachweis |
|---|---|
| Gap-Analyse dokumentiert | AP 1 |
| Nur explizit freigegebene grüne Felder | AP 1 und AP 5 |
| Berechtigung, Ausgangswert und aktueller Zustand geprüft | AP 3 und AP 6 |
| Keine stille Überschreibung | AP 4 und AP 6 |
| Verständliche Konfliktdarstellung | AP 8 |
| Reguläre Forms oder Domain Services | AP 5 und AP 6 |
| Übernahme, Bearbeitung und Verwerfen auditierbar | AP 7 |
| Erfolg, Berechtigung, Konkurrenz, Validierung und unzulässige Felder getestet | AP 9 |
| Lösung explizit und klein | alle Pakete; insbesondere AP 2 und AP 5 |
| Erster real nutzbarer MVP | AP 8 bis AP 10 |

## 6. Bestätigte Nicht-Ziele

- keine Änderung von Issue #116,
- keine automatische Neuanlage unvollständiger Fachobjekte,
- keine Bindung einer Session an mehrere Zielobjekte,
- keine Scope-, Metrik-, Enum-, Referenz-, Rollen-, Entscheidungs- oder Lifecycle-Übernahme,
- keine Phasen-, Prozessanalyse- oder Lösungsoptionsanlage,
- keine Sammelübernahme,
- keine Force-Overwrite- oder Drei-Wege-Merge-Engine,
- keine WebSockets oder Echtzeit-Kollaboration,
- keine generische Feature-Flag-, Audit-, Retention- oder Schreibplattform,
- keine dauerhafte Duplizierung von Capture-Rohtexten, Prompts oder Providerantworten.