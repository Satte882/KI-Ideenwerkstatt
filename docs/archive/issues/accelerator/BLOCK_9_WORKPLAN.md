# Accelerator Block 9: Verbindlicher Arbeitsplan

**Issue:** #125  
**Übergeordneter Plan:** #116, unverändert  
**Ausgangsstand:** `main` auf `e3ee5563850ab23a98385cac3e124ca9fec8fbad` nach Abschluss von Block 8  
**Ziel:** Verbleibende Bedienreibung durch konservative, belegte Rollen-Defaults reduzieren und anschließend den Nutzen des Accelerator-Pfads kontrolliert messen, ohne Rollenhandlungen, Gates oder Messergebnisse vorwegzunehmen.

## 1. Verbindliche Blockgrenze

Block 9 baut keine Rollen-, Identity- oder Analytics-Plattform. Bestehende Rollenbeziehungen, Permission-Services, Gate-Prüfungen, Auditmechanismen, Notifications und fachliche Freigaben bleiben autoritativ.

Rollen-Defaults sind reine Bedienhilfe. Sie dürfen nur auf einer vorhandenen, fachlich eindeutigen und aktuell zulässigen Referenz beruhen. Eine Vorbelegung oder ein Vorschlag führt niemals selbst eine Rollenhandlung aus, bestätigt keine Prüfung und verändert keinen Lifecycle- oder Delivery-Gate-Status.

Die Abschlussmessung prüft das in #116 definierte Produktziel. Sie wird nicht auf ein gewünschtes Ergebnis hin zugeschnitten. Die Messdefinition, der zugrunde liegende fachliche Fall, die Endzustände und die Auswertungsregeln werden vor dem ersten gewerteten Lauf eingefroren.

Nicht gebaut werden:

- Verzeichnisdienst-, HR- oder Workforce-Connectoren,
- automatische Stellvertretungslogik,
- allgemeine Rollenempfehlungs- oder Assignment-Engine,
- neues Rollen- oder Identity-Modell ohne nachgewiesenen Bedarf,
- automatische Freigaben, Bestätigungen oder Prüfhandlungen,
- zweite Permission-Logik neben den bestehenden Services,
- Event-Streaming oder allgemeine Produkttelemetrie,
- Data Warehouse oder BI-Dashboard,
- dauerhaftes Benchmark-/Analytics-Produkt,
- Anpassung der Messgrenze oder Qualitätskriterien nach Sichtung der Ergebnisse.

Issue #116 bleibt unverändert.

## 2. Leitentscheidungen

### 2.1 Rollen-Defaults sind belegte Provenance, keine Vermutung

Die Priorität lautet:

1. bereits gesetzter Zielwert bleibt maßgeblich,
2. eindeutige explizite Rollenquelle derselben fachlichen Beziehung,
3. ausdrücklich zulässiger Workflow-Default,
4. ansonsten kein Default.

Eine fachlich benachbarte Rolle wird nicht automatisch in eine andere Rolle umgedeutet. Insbesondere ist ein Value-Stream-Owner nicht allein aufgrund der Nähe zum Prozess automatisch Business Owner eines Use Cases.

Bei widersprüchlichen Quellen wird nicht nach Reihenfolge entschieden. Der Wert bleibt offen beziehungsweise wird als Konflikt sichtbar gemacht.

### 2.2 Server-side Eligibility bleibt autoritativ

Die UI darf einen Vorschlag anzeigen, aber die tatsächliche Übernahme oder Speicherung wird mit den bestehenden serverseitigen Permission- und Eligibility-Services erneut geprüft. Ein bereits angezeigter, aber noch nicht übernommener Vorschlag wird bei erneutem Laden beziehungsweise erneuter Aktion neu aufgelöst und validiert; er bleibt nicht als autoritativer Cache bestehen.

Damit gelten Deaktivierung, Anonymisierung, Rollenwechsel oder geänderte fachliche Zuordnungen unmittelbar für den nächsten Request.

### 2.3 Keine Notification aus einem bloßen Vorschlag

Das Anzeigen oder Vorbelegen einer Rolle ist keine Zuweisung. Deshalb darf dadurch keine Assignment-, Review- oder sonstige Rollenbenachrichtigung ausgelöst werden. Notifications werden nur durch die bestehenden fachlichen Aktionen erzeugt, die dafür heute bereits vorgesehen sind.

### 2.4 Primärbenchmark und Delivery-Benchmark werden getrennt

Der Primärbenchmark beantwortet die Produktfrage aus #116: Wie schnell lässt sich derselbe fachlich bekannte Fall bis zum vorher definierten strukturierten Draft-Endzustand vorbereiten?

Verglichen werden mindestens:

- manueller Pfad,
- Blueprint als technischer Kontrollpfad,
- geführter Accelerator-Pfad.

Das Delivery-Mapping aus Block 8 wird separat als Sekundärbenchmark gemessen, weil es bestätigte beziehungsweise fachlich wirksame Upstream-Quellen voraussetzt und damit eine andere Prozessgrenze besitzt. Seine Zeit fließt nicht in eine künstlich erweiterte oder verkürzte 30-Minuten-Aussage ein.

### 2.5 Identische Ausgangsdaten bedeuten identisches Faktenset

Die Pfade besitzen technisch unterschiedliche Startzustände. Deshalb bedeutet Vergleichbarkeit nicht identischer Datenbankzustand.

Verbindlich identisch ist das zugrunde liegende fachliche Faktenset beziehungsweise der Fallbeschreibungstext, der dem menschlichen Operator zur Verfügung steht. Jeder Pfad startet aus seinem regulären, vorgesehenen technischen Anfangszustand und soll denselben vorher definierten fachlichen Endzustand erreichen.

### 2.6 Benchmark-Daten sind isoliert

Gewertete Messläufe verwenden reproduzierbare Test-Fixtures beziehungsweise klar isolierte Benchmark-Datensätze und dedizierte Testnutzer. Sie verändern keine produktiven beziehungsweise real genutzten Datensätze, lösen keine realen Notifications aus und vermischen Benchmark-Audit-Trails nicht mit echten fachlichen Vorgängen.

### 2.7 Operator-Bias wird ausgewiesen

Wenn dieselbe mit dem System vertraute Person die Pfade bedient, wird das Ergebnis ausdrücklich als Einzeloperator-Messung eingeordnet. Reihenfolgewechsel und Warm-up reduzieren Lerneffekte, beseitigen aber keinen Vertrautheits-Bias. Eine Aussage wie „unter 30 Minuten“ gilt dann nur für den kontrollierten Benchmark unter den dokumentierten Bedingungen und nicht als populationsübergreifender Usability-Nachweis.

## 3. Messgrenze für das 30-Minuten-Ziel

Die 30-Minuten-Bewertung verwendet die kontrollierte End-to-End-Zeit vom Start der fachlichen Eingabe bis zum eingefrorenen Draft-Endzustand.

Enthalten sind:

- Dateneingabe,
- Navigation,
- Prüfung von Vorschlägen,
- Korrekturen,
- System- und LLM-Wartezeit.

Separat ausgewiesen werden:

- aktive Bearbeitungszeit,
- Navigationszeit,
- Prüfzeit,
- Korrekturzeit,
- System-/LLM-Wartezeit,
- gesamte End-to-End-Zeit.

Nicht Teil der 30-Minuten-Grenze sind die in #116 ausdrücklich ausgeschlossenen fachlichen Entscheidungen und Gates, insbesondere Prozessvalidierung, Auswahl der bevorzugten Lösung, Governance-Fachprüfung, Freigaben, Delivery-Bestätigungen, Übergabe, Pilotstart und Go-live.

Die Aussage „30-Minuten-Ziel erreicht“ ist nur zulässig, wenn die gemessene End-to-End-Zeit nach der vorab definierten Auswertungsregel unter 30 Minuten liegt. Systemwartezeit darf nicht aus der Produktzeit herausgerechnet werden.

## 4. Benchmark-Fälle

Es werden mindestens zwei versionierte Fälle eingefroren.

### Benchmark A – Zeitbenchmark

Ein vollständiger, fachlich bekannter Golden-Path-Fall ohne künstliche Stolperfallen. Er dient der vergleichbaren Zeitmessung.

### Benchmark B – Qualitäts-/Robustheitsbenchmark

Ein gezielt anspruchsvollerer Fall mit mindestens:

- einer fehlenden Pflichtinformation,
- einem Quellenkonflikt,
- einer Scope-In-/Scope-Out-Falle,
- einer Zahl mit Einheit,
- mindestens einer Information, die nicht erfunden werden darf.

Dieser Fall dient insbesondere der Prüfung von Pflichtlücken, Konfliktschutz, Zahlen-/Einheitenqualität und Halluzinationen.

Das zugrunde liegende Faktenset wird versioniert und vor den gewerteten Läufen nicht mehr verändert.

## 5. Durchführung und Auswertung

Vor gewerteten Läufen ist ein nicht gewerteter Warm-up zulässig. Danach werden pro interaktivem Vergleichspfad mindestens drei gewertete Läufe durchgeführt. Die Reihenfolge manueller Pfad/Accelerator wird gewechselt, um Reihenfolge- und Lerneffekte zumindest zu reduzieren.

Bei drei Läufen werden mindestens Median, Minimum und Maximum ausgewiesen. Es wird keine statistische Signifikanz behauptet.

Der Blueprint ist ein technischer Kontrollpfad für Mapping und erwarteten Endzustand, kein menschlicher Produktivitätsbenchmark. Daraus werden keine irreführenden Beschleunigungsfaktoren abgeleitet.

Qualitätsmetriken umfassen mindestens:

- korrekte Feldzuordnungen,
- Zahlen- und Einheitenfehler,
- Scope-In-/Scope-Out-Verwechslungen,
- erfundene Angaben,
- nicht erkannte Pflichtlücken,
- Konflikte mit geänderten Quellen,
- notwendige Nutzerkorrekturen,
- übernommene, bearbeitet übernommene und verworfene Vorschläge,
- Fehler und Abbrüche.

LLM-Nutzung wird soweit im System vorhanden getrennt ausgewiesen:

- Anzahl Aufrufe,
- Prompt Tokens,
- Completion Tokens,
- Total Tokens,
- Kosten,
- Laufzeit,
- Fehler/Timeouts.

Für den Delivery-Sekundärbenchmark werden zusätzlich deterministisch gemappte Felder, LLM-formulierte Restfelder, Gaps, Konflikte und manuell nachbearbeitete Felder ausgewiesen.

## 6. CI- und Arbeitsregel

Jedes Arbeitspaket wird einzeln und sequenziell umgesetzt und erhält einen eigenen Commit und Pull Request. Das nächste AP beginnt erst nach Merge und vollständig grüner, unveränderter Repository-CI des vorherigen APs.

Bei einem fehlgeschlagenen CI-Lauf gilt verbindlich:

- den vollständigen Lauf einschließlich aller gestarteten Jobs abwarten,
- alle Fehler aus allen Jobs sammeln,
- die gesammelten Ursachen gemeinsam beheben,
- genau danach einen neuen Lauf durch einen neuen Fix-Commit auslösen.

Es ist ausdrücklich verboten, nach dem ersten sichtbaren Fehler sofort einen Fix zu pushen und damit weitere Diagnosen des laufenden CI-Laufs abzuschneiden. Ausnahme: Ein Fehler blockiert nachweislich alle Folge-Jobs so, dass deren Fehler sonst nicht sichtbar werden können.

## 7. Arbeitspakete

### AP 1 – Gap-Analyse und verbindlicher Blockvertrag

Gegen den aktuellen `main`-Stand dokumentieren:

- vorhandene Rollenbeziehungen und bestehende Defaults,
- fachlich eindeutige versus riskante Vorbelegungen,
- vorhandene Permission-/Eligibility-Services,
- Notifications und Audit-Nebenwirkungen relevanter Rollenaktionen,
- bereits verfügbare Messdaten und LLM-Metadaten,
- fehlende Messinformationen,
- reguläre technische Startzustände der Vergleichspfade,
- minimal ausreichende Messmethode,
- primäre und sekundäre Messgrenze,
- vorläufige Benchmark-Endzustände.

Der Plan ist gegen den Repository-Stand zu korrigieren, wenn Annahmen nicht bestätigt werden. Keine Produktlogik in diesem AP ändern.

### AP 2 – Rollenquellen- und Prioritätsmatrix

Für jede unterstützte Zielrolle explizit definieren:

- erlaubte Quellen,
- fachliche Gleichheit oder Abgrenzung der Rollenbeziehung,
- Priorität,
- Konfliktverhalten,
- Eligibility-Bedingungen,
- UI-Klassifikation als Vorbelegung, Vorschlag oder offen.

Mindestens Value-Stream-Owner, Business Owner, Technical Owner, KI-Koordinator, Auflagenverantwortlicher und nächste erforderliche Prüfrolle abdecken.

### AP 3 – Serverseitiger Rollen-Default-Resolver und Revalidierung

Einen kleinen zentralen Resolver umsetzen, der ausschließlich Kandidaten mit Quelle und Begründung ermittelt. Er führt keine fachliche Aktion aus und schreibt keinen Rollenwert selbstständig.

Der Resolver validiert Vorschläge bei jedem relevanten Request neu. Deaktivierte, anonymisierte, fachlich geänderte oder nicht mehr berechtigte Personen dürfen nicht aus einem früheren UI-Zustand übernommen werden.

### AP 4 – Eligibility, Permission-Reuse und Fail-closed

Bestehende Permission- und Eligibility-Services wiederverwenden und serverseitige Speicherung gegen manipulierte beziehungsweise veraltete Vorschläge absichern.

Fehlende, widersprüchliche oder nicht mehr zulässige Quellen bleiben offen. Vorhandene Zielwerte werden nicht still überschrieben.

### AP 5 – Rollen-Defaults in der bestehenden UI mit sichtbarer Herkunft

Die unterstützten Defaults in die bestehenden Formulare/Ansichten integrieren. Direkt am Rollenfeld sichtbar machen:

- ob es sich um eine Vorbelegung oder einen Vorschlag handelt,
- Person,
- fachliche Quelle,
- gegebenenfalls warum keine eindeutige Vorbelegung möglich ist.

Keine zusätzliche Rollenübersichtsseite und keine neue Assignment-Oberfläche bauen.

### AP 6 – Gate-, Rollenaktions-, Audit- und Notification-Regression

Explizit nachweisen, dass Rollen-Defaults weder direkt noch indirekt auslösen:

- Freigabe oder Zweitfreigabe,
- Governance-Abschluss,
- Delivery-Section-Bestätigung,
- Übergabe,
- Pilotstart oder Go-live,
- Auflagenbestätigung,
- Assignment-/Review-Notification an lediglich vorgeschlagene Personen.

Bestehende Audit-Trails dürfen erst durch die reguläre fachliche Aktion entstehen, nicht durch das bloße Rendern eines Vorschlags.

## Checkpoint vor der Messstrecke

Nach AP 6 wird die Implementierungsstrecke bewusst beendet. Erst wenn AP 1–6 vollständig gemergt und CI-grün sind, wird die Benchmark-Definition für AP 7 final gegengelesen und eingefroren. Danach werden Messregeln nicht aufgrund erster Ergebnisse verändert.

### AP 7 – Benchmark-Fixtures, Faktenset und Messprotokoll einfrieren

Benchmark A und B als isolierte, reproduzierbare Fixtures beziehungsweise versionierte Testdaten festlegen.

Für jeden Pfad dokumentieren:

- identisches zugrunde liegendes Faktenset,
- regulären technischen Startzustand,
- identischen fachlichen Zielzustand,
- Start-/Stop-Regel,
- erlaubte Hilfsmittel,
- Operator,
- Umgebung und Rollen,
- Reset-Verfahren,
- auszuwertende Qualitätskriterien.

Die Definition wird vor dem ersten gewerteten Lauf eingefroren.

### AP 8 – Minimale Messhilfe und Wiederverwendung vorhandener Messdaten

Vorhandene Messdaten aus Capture Sessions, Analysen, Adoption Audits, Solution Generation und Delivery Mapping wiederverwenden.

Nur die für den Vergleich tatsächlich fehlenden Informationen schlank ergänzen, insbesondere Navigation, manuelle Review-/Korrekturzeiten und manuelle Vergleichswerte. Kein allgemeines Telemetrie- oder Analytics-Datenmodell bauen.

Benchmark-Daten bleiben von produktiven Nutzern, realen Notifications und realen fachlichen Audit-Trails isoliert.

### AP 9 – Kontrollierte Zeit-, Qualitäts- und Delivery-Messläufe

Durchführen:

- nicht gewerteter Warm-up,
- mindestens drei gewertete Läufe je interaktivem Primärpfad,
- manueller Pfad und Accelerator in wechselnder Reihenfolge,
- Blueprint als technischer Kontrollpfad,
- separater Delivery-Mapping-Sekundärbenchmark auf identischem bestätigten Upstream-Zustand.

Alle Laufdaten unverändert dokumentieren. Fehlgeschlagene oder abgebrochene Läufe nicht still verwerfen, sondern mit Ursache kennzeichnen.

### AP 10 – Qualitätsauswertung, Limitationen, Real-DEMO-Nachweis und Blockabschluss

Zeit, Qualität, Korrekturaufwand, Vorschlagsnutzung, LLM-Nutzung und Delivery-Mapping getrennt auswerten.

Der Abschlussbericht enthält mindestens:

- Ergebnisse je Pfad und Benchmark-Fall,
- Median/Minimum/Maximum der gewerteten interaktiven Läufe,
- End-to-End-Zeit und getrennte Zeitkomponenten,
- Qualitätsfehler und Korrekturaufwand,
- LLM-Aufrufe/Token/Kosten soweit vorhanden,
- deterministische versus LLM-formulierte Delivery-Felder,
- alle dokumentierten Abweichungen vom Workplan,
- Real-DEMO-/Drift-/Gate-Nachweis,
- explizite Limitationen der Messung.

Bei Einzeloperator-Messung ist Vertrautheits-/Operator-Bias ausdrücklich als Limitation zu nennen. Aussagen zu „unter 30 Minuten“ oder Beschleunigungsfaktoren werden ausschließlich aus den eingefrorenen und dokumentierten Messergebnissen abgeleitet und auf deren Messbedingungen begrenzt.

## 8. Block-Abnahmekriterien

Block 9 ist erst abgeschlossen, wenn:

- Gap-Analyse gegen den aktuellen `main` dokumentiert ist,
- nur eindeutige und aktuell berechtigte Rollen vorgeschlagen/vorbelegt werden,
- Vorschläge bei Nutzung serverseitig erneut validiert werden,
- keine Rollenhandlung, Gate-Aktion oder Notification allein durch einen Default ausgelöst wird,
- Benchmark-Faktenset, Startzustände, Zielzustände und Messregeln vor Durchführung eingefroren sind,
- Messläufe isoliert und reproduzierbar durchgeführt wurden,
- manuelle und beschleunigte Pfade nachvollziehbar dokumentiert sind,
- Zeit, Qualität, LLM-Nutzung und Korrekturaufwand getrennt ausgewiesen sind,
- der Delivery-Mapping-Nutzen separat gemessen wurde,
- Operator-/Vertrautheits-Bias und weitere relevante Limitationen transparent benannt sind,
- Aussagen zu Beschleunigung ausschließlich auf gemessenen Ergebnissen beruhen,
- keine neue Analytics-, Workforce- oder Identity-Infrastruktur entstanden ist,
- vollständige unveränderte Repository-CI grün ist.
