# Accelerator Block 9 – AP 1 Gap-Analyse und verbindlicher Blockvertrag

**Issue:** #125  
**Workplan:** `docs/accelerator/BLOCK_9_WORKPLAN.md`  
**Geprüfter Stand:** `main` auf `5bf7d26051b29a89d34095e7e93a12cc5b4b1f50`  
**Scope dieses AP:** ausschließlich Analyse und verbindliche Konkretisierung; keine Produktlogik.

## 1. Ergebnis in Kurzform

Der Block-9-Workplan bleibt grundsätzlich gültig. Der aktuelle Repository-Stand bestätigt jedoch drei für die Umsetzung verbindliche Präzisierungen:

1. Der bestehende Use-Case-Intake enthält bereits einen fachlich riskanten Rollen-Default: Der eingeloggte Nutzer wird beim Erzeugen des Use Cases fest als `business_owner` gesetzt. Dieser Mechanismus darf nicht als allgemeine Default-Regel fortgeschrieben werden.
2. Der geführte Accelerator-Pfad und der manuelle Intake besitzen bewusst unterschiedliche technische Startzustände. Vergleichbarkeit wird deshalb über dasselbe fachliche Faktenset und denselben definierten fachlichen Endzustand hergestellt, nicht über identische Datenbankzustände.
3. Für Delivery existiert bereits eine belastbare Rollen-Provenance für den Technical Owner. Block 9 darf diese vorhandene Semantik nicht durch eine zweite Rollenquellenlogik ersetzen.

Es ist keine neue Workforce-, Identity-, Notification- oder Analytics-Infrastruktur erforderlich.

## 2. Verifizierte Rollenbeziehungen und bestehende Defaults

### 2.1 Value-Stream-Owner

`ValueStream.owner` ist eine explizite Rollenbeziehung. Der bestehende `ValueStreamForm` begrenzt zulässige Owner auf aktive, nicht anonymisierte Business Owner, KI-Koordinatoren, Technische Administratoren beziehungsweise Superuser.

Der bestehende Formular-Hilfetext stellt ausdrücklich klar, dass der Value-Stream-Owner von Business Owner und Technical Owner eines späteren Use Cases getrennt ist.

**Verbindliche Folgerung:**

- `ValueStream.owner` ist eine belastbare Quelle für die Rolle Value-Stream-Owner selbst.
- `ValueStream.owner -> UseCase.business_owner` ist keine fachlich identische Rollenbeziehung und darf nicht still vorbelegt werden.
- Falls diese Beziehung in AP 2 für den Golden Path sinnvoll ist, ist sie höchstens als sichtbar begründeter Vorschlag zu klassifizieren.

### 2.2 Business Owner des Use Cases

`UseCase.business_owner` ist ein verpflichtendes Feld. Der reguläre sechsstufige Intake erzeugt den Use Case am Ende mit `business_owner=request.user`.

Damit existiert bereits ein Default, aber keine nachgewiesene fachliche Ableitungsregel. Die Gruppenlogik erlaubt KI-Koordinatoren und Technischen Administratoren ebenfalls die generische Business-Owner-Berechtigung. Diese technische Eligibility beweist nicht, dass die Person fachlich accountable Business Owner des konkreten Use Cases ist.

**Verbindliche Folgerung:**

- Der aktuelle `request.user`-Default wird in Block 9 nicht als autoritative Rollenquelle behandelt.
- AP 2 muss entscheiden, wann ein vorhandener expliziter Business Owner übernommen werden darf und wann das Feld offen bleibt.
- Eine Gruppenmitgliedschaft allein ist keine fachliche Rollenquelle.

### 2.3 KI-Koordinator

`UseCase.coordinator` ist ein explizites optionales Feld. Das Accounts-Modul definiert die Gruppe `KI-Koordinator`; technische Administratoren gelten in den Permission-Helfern ebenfalls als Coordinator.

Es existiert im geprüften Pfad keine belastbare Regel, nach der aus Gruppenmitgliedschaft automatisch genau eine fachlich zuständige Coordinator-Person für einen konkreten Use Case folgt.

**Verbindliche Folgerung:**

- Eine vorhandene explizite `UseCase.coordinator`-Zuordnung ist belastbar.
- Gruppenmitgliedschaft allein erzeugt keinen Personenvorschlag.
- Fehlt eine eindeutige konkrete Referenz, bleibt der Coordinator offen.

### 2.4 Technical Owner

`UseCase.technical_owner` ist eine explizite optionale Rollenbeziehung. Bei Erzeugung eines Delivery Packages wird dieser Wert bereits direkt in `DeliveryPackage.technical_owner` kopiert.

Zusätzlich enthält das vorhandene Delivery-`source_manifest` Rollenquellen für Business Owner und Technical Owner. Für den Technical Owner existieren bereits:

- Source-Snapshot,
- aktuelle Source-Zuordnung,
- Erkennung einer geänderten Source,
- Working-Zuordnung im Package,
- explizite Adoption-Information,
- immutable `DeliveryRoleSourceDecision` für die Auflösung einer Rollenquellenabweichung.

**Verbindliche Folgerung:**

- `UseCase.technical_owner -> DeliveryPackage.technical_owner` ist der stärkste bereits vorhandene Same-Role-Default und wird wiederverwendet statt neu modelliert.
- Block 9 ergänzt hierfür keine parallele Rollen-Provenance.
- Staleness beziehungsweise Source-Änderungen bleiben im bestehenden Delivery-Mechanismus maßgeblich.

### 2.5 Auflagenverantwortlicher

`ApprovalDecision.condition_owner` ist eine explizite Personenzuordnung bei einer Freigabe mit Auflagen. Im Formular stehen aktive, nicht anonymisierte Nutzer zur Auswahl.

Es wurde keine fachlich eindeutige allgemeine Quelle gefunden, die bei einer neuen Auflage automatisch genau diese Person bestimmt.

**Verbindliche Folgerung:**

- Ein vorhandener `condition_owner` desselben konkreten Approval-Kontexts ist eine belastbare bestehende Zuordnung.
- Für eine neu entstehende Auflage wird keine Person aus Business Owner, Technical Owner, Coordinator oder Value-Stream-Owner abgeleitet.
- Fehlt eine explizite gleichartige Referenz, bleibt das Feld offen.

### 2.6 Zweitprüfung / nächste erforderliche Prüfrolle

Für die unabhängige Zweitfreigabe existiert bereits `eligible_second_approvers(use_case, first_decider)`. Das `ApprovalDecisionForm` verwendet genau dieses Queryset für `second_approval_assignee`.

Im Delivery-Pfad definieren die Section-Requirements, ob eine Business- und/oder Technical-Bestätigung erforderlich ist. Die Permission-Funktionen bestimmen, welche Rollen ein konkreter Nutzer für eine Section ausüben darf.

**Verbindliche Folgerung:**

- Vorhandene Eligibility-Services werden wiederverwendet; Block 9 baut keine zweite Vier-Augen- oder Reviewer-Logik.
- Eine Menge zulässiger Prüfer ist keine eindeutige Personenzuordnung.
- Die nächste erforderliche **Rolle** darf aus dem bestehenden Workflow sichtbar gemacht werden.
- Eine konkrete Person wird nur vorgeschlagen, wenn zusätzlich eine eindeutige bereits vorhandene Zuordnung existiert und die aktuelle Eligibility dies bestätigt.

## 3. Permission- und Eligibility-Grenze

Die vorhandenen Permission-Services bleiben autoritativ.

Relevant sind insbesondere:

- Accounts-Gruppen und `is_coordinator` / `is_business_owner`,
- Use-Case-Berechtigungen für Erstellen, Bearbeiten und Pilotstart,
- `eligible_second_approvers` für unabhängige Zweitfreigaben,
- Delivery-Permissions für Business-/Technical-Confirmation, Reviewer-Rollen und Rollenquellenauflösung,
- Architecture-Eligibility für Value-Stream-Owner.

**Block-9-Vertrag:**

Der Rollen-Default-Resolver aus AP 3 darf Eligibility nur lesen. Die tatsächliche Speicherung beziehungsweise fachliche Aktion wird serverseitig im bestehenden Zielpfad erneut geprüft. Ein im Browser angezeigter Vorschlag ist nie ein Berechtigungsnachweis.

Deaktivierung, Anonymisierung, Gruppen-/Rollenänderung oder geänderte Source-Zuordnung zwischen Anzeige und Nutzung führen bei der nächsten serverseitigen Auflösung beziehungsweise Aktion zu einer neuen Bewertung. Ein Rollen-Vorschlag wird nicht als dauerhafter autoritativer Cache gespeichert.

## 4. Audit- und Notification-Grenze

Mehrere maßgebliche Domänenobjekte besitzen bereits History-/Audit-Mechanismen. Delivery-Rollenquellenentscheidungen sind ausdrücklich immutable auditiert. Deshalb darf das bloße Ermitteln oder Rendern eines Rollen-Vorschlags keinen Save auf dem fachlichen Zielobjekt auslösen.

Das vorhandene `notifications`-Modul enthält `NotificationLog` als persistierten Versand-/Ereignisnachweis sowie Nachweislinks. Im Modul selbst existiert kein separater Rollen-Default- oder Assignment-Workflow, der für Block 9 wiederverwendet werden müsste.

**Block-9-Vertrag:**

- Resolver-Aufruf und UI-Rendering sind read-only.
- Keine `NotificationLog`-Anlage allein durch Vorbelegung oder Vorschlag.
- Keine E-Mail-/Review-/Assignment-Benachrichtigung allein durch einen Vorschlag.
- Keine History-/Audit-Änderung auf Use Case, Approval, Governance oder Delivery allein durch das Anzeigen eines Defaults.
- AP 6 weist diese Invarianz explizit regressiv nach.

## 5. Bereits vorhandene Messdaten

### 5.1 Capture Session

Block 3 speichert bereits bewusst schlank:

- kumulierte aktive Eingabezeit,
- Anzahl erfolgreicher Speicherungen,
- Abschlusszeitpunkt,
- Erstell-/Update-Zeitpunkte als Grundlage für getrennte Kalenderdauer.

Die aktive Eingabezeit zählt nur fokussierte native Capture-Felder bei sichtbarem Dokument; es werden keine Klickpfade, Tastendrücke oder Gerätekennungen als Produkttelemetrie gespeichert.

### 5.2 LLM-Extraktion

`CaptureAnalysis` enthält bereits:

- Start-/Endzeit,
- `duration_ms`,
- Fehlercode,
- Input-/Output-Zeichen,
- Prompt-, Completion- und Total-Tokens,
- Kosten soweit verfügbar,
- offene Fragen,
- Widersprüche.

### 5.3 Vorschlagsübernahme

`FieldAdoptionCandidate` und `FieldAdoptionAudit` unterscheiden unter anderem:

- direkt übernommen,
- bearbeitet übernommen,
- verworfen,
- Konflikt,
- stale,
- failed,
- vorherigen/proponierten/bearbeiteten/finalen Wert,
- relevante Token-/Kostenwerte.

### 5.4 Lösungsentwürfe

`SolutionGenerationRun` enthält Laufzeit-, Fehler-, Token- und Kostenmetadaten für Block 7.

### 5.5 Delivery Mapping

Block 8 stellt pro unterstütztem Delivery-Feld Mapping-/Provenance-Informationen bereit und unterscheidet unter anderem gemappte Felder, Gaps, Konflikte und Staleness. Die optionale LLM-Restformulierung ist von deterministischen Mappings getrennt.

**Verbindliche Folgerung:**

Für Block 9 wird kein allgemeines Telemetrie-Datenmodell benötigt. AP 8 ergänzt nur Messinformationen, die für den kontrollierten Vergleich nachweislich fehlen.

## 6. Fehlende Messinformationen

Für den geplanten Vergleich fehlen im aktuellen Stand insbesondere konsistente Messwerte für:

- Navigationszeit des manuellen und geführten Pfads,
- manuelle Prüfzeit,
- manuelle Korrekturzeit,
- aktive Bearbeitungszeit des vollständig manuellen Pfads in derselben Granularität wie Capture,
- ein run-bezogenes gemeinsames Messprotokoll, das Systemdaten und manuell erhobene Vergleichsdaten für denselben Benchmark-Lauf zusammenführt.

Nicht erforderlich ist detaillierte Clickstream-Telemetrie.

**Minimale Lösung:**

Ein kleines, benchmark-spezifisches Messprotokoll beziehungsweise eine schmale Messhilfe genügt, solange die Kategorien Start/Stop, aktive Bearbeitung, Navigation, Review, Korrektur und System-/LLM-Wartezeit reproduzierbar getrennt werden können. Die endgültige technische Form wird erst in AP 8 nach Freeze der Benchmark-Definition festgelegt.

## 7. Technische Startzustände der Vergleichspfade

### 7.1 Manueller Pfad

Der reguläre Use-Case-Einstieg ist der bestehende sechsstufige Intake unter `use_cases:new` / `use_case_intake`.

Technischer Startzustand:

- kein neuer Use Case für den Benchmark-Fall gespeichert,
- leere beziehungsweise für den Lauf zurückgesetzte Intake-Session,
- erforderliche Referenzdaten wie Business Unit und dedizierter Testnutzer vorhanden.

Der Use Case wird erst im finalen Intake-Schritt gespeichert und dort derzeit mit dem eingeloggten Nutzer als `business_owner` erzeugt.

### 7.2 Blueprint-Pfad

Der Block-2-Blueprint ist ein deterministischer technischer Kontrollpfad über `python manage.py apply_scenario_blueprint`; Standard ist Dry Run, Schreiben erfolgt nur mit `--apply`.

Technischer Startzustand:

- erforderliche Referenznutzer/-gruppen/-organisationseinheiten existieren,
- der Blueprint-Graph des Benchmark-Szenarios ist entweder vollständig neu (`CREATE`) oder wird nach Reset in diesen Zustand gebracht,
- kein Teil-Apply beziehungsweise Merge.

Der Blueprint ist kein interaktiver Nutzerpfad und daher kein direkter Produktivitätsvergleich.

### 7.3 Geführter Accelerator-Pfad

Der reguläre UI-Einstieg ist `accelerator:use_case_start`. Daraus entsteht zunächst eine `CaptureSession`; Antworten werden schrittweise gespeichert und anschließend explizit abgeschlossen und analysiert.

Für Feldübernahme gilt eine wichtige bestehende Grenze: Eine Capture Session darf genau ein bereits bestehendes, vom Nutzer bearbeitbares Zielobjekt binden. Eine automatische Neuanlage des Zielobjekts ist in diesem Pfad nicht vorgesehen.

Technischer Startzustand für den späteren Benchmark muss deshalb enthalten:

- eine neue Capture Session,
- einen dedizierten Benchmark-Nutzer,
- das für den Accelerator regulär erforderliche leere beziehungsweise minimale bearbeitbare Draft-Zielobjekt, sofern der zu messende Endzustand Feldübernahme verlangt.

Dieses Draft-Zielobjekt ist technische Pfadvoraussetzung und wird nicht als fachlicher Vorsprung gegenüber dem manuellen Pfad gewertet. AP 7 muss exakt definieren, welche initialen Pflichtwerte dafür unvermeidbar sind und wie sie bei der Zeit-/Qualitätsauswertung behandelt werden.

## 8. Vorläufiger gemeinsamer fachlicher Endzustand

Der Primärbenchmark endet nicht bei Freigabe, Prozessvalidierung oder Delivery-Handover.

Vorläufiger gemeinsamer Zielzustand ist ein gespeicherter, strukturierter Entwurfsstand des zugrunde liegenden fachlichen Falls, in dem die für den Benchmark definierten Use-Case-/Capture-relevanten Inhalte fachlich vergleichbar vorliegen und keine ausgeschlossene rote Gate-/Entscheidungsaktion automatisch gesetzt wurde.

Für den geführten Accelerator bedeutet dies nicht, dass offene Vorschläge als fertiger Inhalt zählen. Nur regulär gespeicherte beziehungsweise explizit übernommene Inhalte zählen zum Endzustand.

Der Blueprint dient zur technischen Referenz des erwarteten Graphen. AP 7 friert für Benchmark A und B die genaue Feld-/Objektliste und die Stop-Regel ein.

## 9. Sekundärbenchmark Delivery

Delivery beginnt aus einem anderen fachlichen Zustand: Ein reguläres Delivery Package setzt eine finale positive Freigabe voraus. Bei seiner Erzeugung wird der Use-Case-Technical-Owner bereits als Package-Technical-Owner übernommen; Block 8 kann die priorisierten Felder deterministisch aus wirksamen Quellen mappen.

Daher gilt verbindlich:

- Delivery wird separat vom 30-Minuten-Primärbenchmark gemessen,
- manueller und Mapper-Lauf starten aus demselben eingefrorenen bestätigten Upstream-Zustand,
- weder Freigabezeit noch Wartezeit auf fachliche Rollen wird dem Mapper zugerechnet,
- deterministische, LLM-formulierte, offene und manuell korrigierte Felder werden getrennt ausgewiesen.

## 10. Benchmark-Isolation

Gewertete Läufe verwenden ausschließlich dedizierte Benchmark-Fixtures/-Datensätze und Testnutzer.

Vor jedem Lauf wird der jeweilige Pfad auf seinen definierten regulären Startzustand zurückgesetzt. Dabei werden keine real genutzten Real-DEMO-Datensätze als veränderliche Benchmark-Arbeitskopie verwendet.

Die versionierte `[Real-DEMO]`-Referenz darf als fachliche Referenz beziehungsweise Drift-Nachweis dienen; die eigentlichen Messläufe müssen reproduzierbar isoliert sein.

Benchmark-Aktionen dürfen keine realen Empfänger benachrichtigen und keine produktiven Audit-Trails mit Messartefakten vermischen.

## 11. Operator-Bias und Aussagegrenze

Falls eine einzelne systemkundige Person alle gewerteten Pfade bedient, ist das eine kontrollierte Einzeloperator-Messung.

Warm-up und wechselnde Pfadreihenfolge reduzieren Lern- und Reihenfolgeeffekte, beseitigen aber nicht:

- Vertrautheits-Bias,
- Erinnern des Fallinhalts über Wiederholungen,
- unterschiedliche Routine mit manuellem und Accelerator-Pfad.

Der Abschlussbericht muss diese Einschränkung explizit ausweisen. Ein gemessenes Ergebnis unter 30 Minuten belegt dann ausschließlich den dokumentierten Benchmark unter diesen Bedingungen und keinen allgemeinen Usability- oder Populationseffekt.

## 12. Verbindlicher AP-1-Entscheid

Der Workplan wird mit folgenden Konkretisierungen fortgeführt:

- keine automatische Cross-Role-Ableitung,
- bestehenden `request.user -> business_owner`-Default nicht als fachliche Wahrheit behandeln,
- vorhandene Same-Role-Provenance für Delivery Technical Owner wiederverwenden,
- Gruppenmitgliedschaft ist Eligibility, nicht Rollenquelle,
- Reviewer-Eligibility ist keine Personenzuweisung,
- Resolver bleibt read-only und revalidiert bei jedem relevanten Request,
- reine Vorschläge lösen weder Audit-Änderung noch Notification aus,
- vorhandene Accelerator-/LLM-Messdaten werden wiederverwendet,
- technische Startzustände dürfen pfadtypisch unterschiedlich sein,
- identisch bleibt das fachliche Faktenset und der eingefrorene fachliche Zielzustand,
- Delivery bleibt eigener Sekundärbenchmark,
- Benchmark-Läufe werden isoliert,
- Einzeloperator-Bias wird verpflichtend berichtet.

Es besteht nach der Gap-Analyse kein Grund, #116 zu verändern oder Block 9 in weitere Plattformkomponenten aufzuteilen.
