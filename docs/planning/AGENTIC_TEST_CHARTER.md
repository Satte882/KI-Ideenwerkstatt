# Agentic Exploratory Test Charter

Issue: #428  
Grundlage: `main` @ `9fa0cc156a3c49b4d623afbbea9322714a3c1b8e`

## 1. Ziel

Dieses Dokument definiert ein reproduzierbares Testdesign für zehn agentische, explorative Browser-Runs durch den Discovery-Pfad des KI-UseCase-Radars.

Die Runs sollen prüfen, ob ein fachlich nur grob instruierter Nutzer mit wenigen Eckdaten durch das bestehende Vorgehensmodell zu einer belastbaren Problem- und Lösungsentscheidung gelangt. Der Agent erhält **keinen vorgegebenen Value Stream, keine vorgefertigte Prozessanalyse, keine gewünschte Technologie und keinen erwarteten Use Case**.

Der Test misst gleichzeitig:

- methodische Führung: Problem vor Lösung, sinnvolle Scope-Grenzen, Ursachen vor Präferenz;
- Lösungsneutralität: organisatorische, regelbasierte, Standardsoftware-, klassische Software-, Analytics-/ML-, GenAI-, Assistenz- und Hybridoptionen bleiben echte Alternativen;
- UX und Verständlichkeit innerhalb des geführten Pfads;
- Navigation und Next Action;
- Gate-/Validierungsverhalten;
- funktionale und technische Fehler;
- Trennbarkeit echter Produktprobleme von Agent-/Browser-/Toolproblemen.

Die zehn Runs liefern **qualitative Muster**, keinen statistischen Wirksamkeitsnachweis.

## 2. Abgrenzung

Nicht Bestandteil dieses Testblocks:

- kein deterministischer Regressionstest;
- kein vorgegebenes Klickskript;
- kein Permission-/Rollentest mit wechselnden Rollen;
- kein Security-/Penetrationstest;
- kein Performance-/Lasttest;
- keine Produktänderung oder Fehlerbehebung zwischen den Runs;
- keine wissenschaftliche Validierung mit statistischer Signifikanz;
- keine Bewertung nach einem künstlichen Gesamtscore.

Deterministische Tests bleiben parallel die Absicherung bekannter Regeln. Dieser Testblock ergänzt sie um exploratives Verhalten unter variablen fachlichen Ausgangsbedingungen.

## 3. Repo-Befund: Der Pfad ist geführt, der Inhalt bleibt offen

Die Anwendung ist kein frei navigierbarer Sandkasten. Wesentliche Übergänge des Discovery-Pfads werden bereits serverseitig bzw. durch bestehende Journey-Logik geführt.

Der zu prüfende fachliche Pfad lautet:

```text
fachlicher Ausgangsrahmen
→ Value Stream
→ Value-Stream-Screening / Deep-Dive-Entscheidung
→ Fokusphase
→ Prozessanalyse
→ Lösungsoptionen und Vergleich
→ bevorzugte Lösung
→ bei tatsächlicher KI-Komponente: geführter Use-Case-Intake
```

Wichtig: Eine bevorzugte Non-AI-Lösung darf Discovery regulär ohne künstlich erzeugten KI-Use-Case beenden. Das ist ein **gültiges positives Testergebnis** und ausdrücklich notwendig, um ein mögliches KI-Bias erkennen zu können.

### 3.1 Wesentliche bekannte Gates auf dem geprüften `main`

| Schritt | Bekannter Rahmen / Gate | Testinterpretation |
|---|---|---|
| Zugriff | Architektur- und Use-Case-Anlage verlangen eine berechtigte Rolle | fester Testrollen-Kontext, kein Freiheitsgrad des Runs |
| Value Stream | nachgelagerte Prozessarbeit setzt einen aktiven Value Stream voraus | erwartetes Gate; Qualität der Erklärung/Next Action ist testbar |
| Value-Stream-Fokus | Deep Dive setzt `SELECTED` und vollständig dokumentiertes Screening voraus | erwartetes Gate; fachliche Verständlichkeit ist testbar |
| Fokusphase | bei mehreren Phasen muss eine Fokusphase gewählt und begründet werden; bei einer Phase existiert ein bewusster Kurzpfad | erwartete Führung; Auswahlqualität und UX bleiben testbar |
| Prozessanalyse | Prozess-Deep-Dive darf nur auf der ausgewählten Fokusphase entstehen | erwartetes Gate |
| Lösungspräferenz | mindestens zwei aktive, vollständig vergleichbare Optionen erforderlich | erwartete Lösungsneutralitäts-Sicherung |
| Diagnose vor Präferenz | für eine verbindliche Präferenz müssen mindestens Beobachtung/Problem und bestätigte Ursache dokumentiert sein | erwartete methodische Sicherung |
| Auswahl | Präferenz benötigt Begründung; maximal eine Option ist bevorzugt | erwartete Governance |
| Use Case | nur bevorzugte Lösungen mit tatsächlicher KI-Komponente führen regulär in den KI-Use-Case-Pfad | Non-AI-Abschluss ist zulässiges Endergebnis |

Ein vorhandenes Gate ist **nicht allein deshalb ein Finding**, weil es Arbeit blockiert. Ein Finding entsteht, wenn z. B.:

- der Nutzer nicht versteht, warum es blockiert;
- die erforderliche Information im UI nicht erkennbar ist;
- Next Action oder Navigation widersprüchlich sind;
- das Gate fachlich unpassend ausgelöst wird;
- zulässige Arbeit unnötig verhindert wird;
- UI und serverseitige Regel unterschiedliche Zustände vermitteln.

## 4. Kanonischer Rollen- und Permission-Kontext

### 4.1 Standardrolle

Alle zehn Blackbox-Runs verwenden dasselbe Permission-Profil:

```text
Rolle: Business Owner
Superuser: nein
KI-Koordinator: nein
Technischer Administrator: nein
Leser-only: nein
```

Begründung:

- `can_manage_architecture()` verwendet die bestehende Business-Owner-Eligibility;
- `can_create_use_case()` erlaubt einem Business Owner die Use-Case-Anlage;
- ein Business Owner kann einen Value Stream bearbeiten, wenn er dessen Owner ist;
- ein Business Owner kann einen Use Case bearbeiten, wenn er dessen Business Owner ist;
- Koordinator/Admin hätten weitergehende Rechte und könnten reale Ownership-/UX-Probleme verdecken.

### 4.2 Ownership-Regel für die Runs

Der kanonische Testnutzer ist bei selbst erzeugten Objekten soweit im Produkt vorgesehen:

- Value-Stream-Owner des angelegten Value Streams;
- Business Owner eines daraus erzeugten Use Cases.

Falls der geführte Produktpfad diese konsistente Ownership nicht zulässt oder unerwartet höhere Rechte verlangt, wird das als `Testsetup / Permission` bzw. als Produktfinding dokumentiert – nicht durch Hochstufen des Testusers auf Koordinator/Admin umgangen.

### 4.3 Testidentität

Vor Run 1 ist eine dedizierte, aktive Testidentität anzulegen oder festzulegen, z. B.:

```text
agentic_test_owner
```

Sie gehört ausschließlich zur Gruppe `Business Owner`. Die konkrete Identität wird in jedem Run-Log dokumentiert.

Keine Rollenänderung zwischen den zehn Runs.

Gezieltes Permission-Testing ist Anti-Scope dieses Blocks.

## 5. Clean State und Ausschluss vorbereiteter Referenzfälle

### 5.1 Grundregel

Jeder Run startet aus demselben fachlichen Ausgangszustand.

Bevorzugt wird eine reproduzierbare Testdatenbank bzw. ein wiederherstellbarer Baseline-Snapshot mit:

- migriertem Schema;
- notwendigen Auth-Gruppen;
- einer aktiven Testorganisationseinheit;
- der kanonischen Business-Owner-Testidentität;
- technisch notwendigen Taxonomien/Stammdaten;
- **keinen fachlich vorbereiteten Value Streams, Prozessanalysen, Lösungsoptionen oder Use Cases**, die dem Agenten eine Lösung vorgeben.

### 5.2 Explizit ausgeschlossene Referenzdaten

Nicht als Ausgangsbasis, Vorlage oder Fortsetzung verwenden:

- Supplier Golden Path `supplier-selection-golden-path`;
- `[DEMO] Automatisierte Lieferantenauswahl`;
- vorbereitete Golden-Path-Use-Cases;
- Demo-Value-Streams mit bereits ausgewähltem Fokus;
- Demo-Prozessanalysen oder vorausgefüllte Lösungsoptionen;
- sonstige Szenario-/Blueprint-Daten, die den fachlichen Pfad bereits vorentscheiden.

Neutrale technische Stammdaten oder Auth-Gruppen sind zulässig.

### 5.3 Isolation zwischen Runs

Nach jedem Run wird der definierte Baseline-Zustand wiederhergestellt. Eine bloße Namenskonvention reicht nicht, wenn vorherige fachliche Artefakte im UI sichtbar bleiben und den nächsten Agenten beeinflussen könnten.

Falls ein vollständiger DB-Reset technisch nicht praktikabel ist, muss eine gleichwertige Isolation nachgewiesen werden, bei der frühere Run-Artefakte für den nächsten Blackbox-Agenten nicht sichtbar oder nutzbar sind.

Jeder Run verwendet zusätzlich die Kennung `AET-R01` bis `AET-R10` in Screenshot-/Log-Dateien. Die Kennung darf nicht als fachlicher Hinweis im Charter wirken.

## 6. Master-Test-Charter für den Blackbox-Agenten

Der folgende Charter ist je Run verbindlich. Nur der Abschnitt `Ausgangsrahmen` wird anhand der Stichprobenmatrix ersetzt.

```text
Du testest den KI-UseCase-Radar als fachlicher Business Owner.

Ziel:
Arbeite aus dem gegebenen fachlichen Ausgangsrahmen selbständig durch den sichtbaren Discovery-Pfad. Entwickle die fachlichen Inhalte selbst. Prüfe, ob das Vorgehensmodell dich von einem noch unscharfen Geschäftsproblem zu einer nachvollziehbaren Lösungsentscheidung führt.

Wichtig:
- Nutze ausschließlich die laufende Anwendung im Browser.
- Du kennst keinen Repo-Code, keine Models, Views, Services oder versteckten Testdaten.
- Folge der sichtbaren Produktführung und den vorhandenen Gates.
- Erfinde keinen anderen Workflow, nur weil du einen besseren vermutest.
- Entscheide selbst, welcher Value Stream sinnvoll ist, welche Phase vertieft werden sollte, wie der Prozess abzugrenzen ist, welche Probleme/Ursachen relevant sind und welche Lösungsoptionen betrachtet werden sollten.
- KI ist keine Vorgabe. Organisatorische Änderung, Standardsoftware, regelbasierte Automatisierung, klassische Software, Analytics/ML, GenAI, Assistenz, Hybrid oder keine technische Lösung sind gleichwertig zulässig.
- Unbekannte Fakten, Messwerte oder Evidenz nicht als Tatsachen erfinden. Wo der Charter keine belastbaren Informationen liefert, arbeite mit transparenten Annahmen/Hypothesen, soweit das Produkt dies zulässt.
- Versuche nicht, bekannte Golden-Path-/Demo-Inhalte nachzubauen.
- Verändere keinen Produktcode und greife während dieses Blackbox-Teils nicht auf das Repository zu.
- Dokumentiere Reibung, Unsicherheit, Sackgassen, unerwartete Gates und technische Fehler im Run-Log.

Run-Ende:
A) Wenn die begründete bevorzugte Lösung eine tatsächliche KI-Komponente enthält, führe den vorgesehenen Pfad bis zu einem konkret angelegten Use Case fort.
B) Wenn die begründete bevorzugte Lösung keine KI-Komponente enthält und das Produkt Discovery regulär dort beendet, ist das ein gültiger erfolgreicher Non-AI-Abschluss. Erzeuge keinen künstlichen KI-Use-Case.
C) Wenn ein Produkt- oder Agent-/Tool-Abbruchkriterium erreicht wird, beende den Run entsprechend der dokumentierten Regel und klassifiziere den Abbruch.

Ausgangsrahmen:
<run-spezifischer Charter aus Abschnitt 7>
```

Der Blackbox-Agent erhält **nicht**:

- erwarteten Value-Stream-Namen;
- erwartete Fokusphase;
- erwartete Ursache;
- erwarteten Lösungstyp;
- erwarteten Use Case;
- Links auf Implementierungsdateien;
- technische Erklärungen zu Guards;
- Ergebnisse vorheriger Runs.

## 7. Zehn-Run-Stichprobenmatrix

Die Matrix variiert Fachbereich, Arbeitstyp, Datenreife, Pain-Point-Klarheit, Unternehmensgröße und **primäre Zielart**. Damit soll verhindert werden, dass die Stichprobe selbst ausschließlich auf Prozess-/Koordinationseffizienz vorgerahmt ist. Die letzte Spalte beschreibt nur die **Testspannung**, nicht das erwartete Ergebnis.

| Run | Kontext | Datenreife | Pain-Klarheit | Primäre Zielart | Problemcharakter / Testspannung |
|---|---|---|---|---|---|
| R01 | mittelständischer Maschinenbauer, After Sales / Service | mittel | klar | Effizienz + Servicequalität | viel manuelle Koordination und wiederkehrende Informationssuche |
| R02 | produzierendes KMU, interne Qualitätsarbeit | niedrig-mittel | diffus | Qualität + Ursachenklärung | Nacharbeit steigt, Ursachen sind nicht eindeutig belegt |
| R03 | Handelsunternehmen, Bestell-/Freigabekontext | hoch | klar | Durchlaufzeit + Regeltreue | wiederkehrende Standardfälle und bekannte Regeln; KI darf nicht erzwungen werden |
| R04 | Dienstleistungs-KMU, Kundenservice | hoch | mittel | Servicequalität + Effizienz | hohes Kontaktvolumen, mehrere Kanäle, Freitext und saisonale Schwankung |
| R05 | mittelständisches Unternehmen, HR / Onboarding | niedrig | diffus | Zuverlässigkeit + Nutzererlebnis | viele Übergaben, lokale Varianten, unvollständige Transparenz |
| R06 | technischer Außendienst / Field Service | mittel | klar | Planungsqualität + Resilienz | Termin-/Ressourcenkoordination, Ausnahmen und Abhängigkeiten |
| R07 | B2B-Industrieunternehmen, strategischer Vertrieb | mittel | mittel | Wachstum + Marge | Abschlussquote und Margenqualität verbessern, ohne den Hebel vorzugeben |
| R08 | reguliertes Produktionsunternehmen, Traceability / Qualitätssicherung | hoch | klar | Risiko + Compliance | Nachweis- und Rückverfolgbarkeitsrisiko bei hoher Datenverfügbarkeit; Effizienz ist nicht Primärziel |
| R09 | Großhandel / Logistik, Retouren und Ausnahmebearbeitung | mittel | diffus | Qualität + Durchlaufzeit | mehrere Ursachen, Medienbrüche und Regeln gemischt |
| R10 | Engineering-/Projektorganisation, Wissens- und Entscheidungsarbeit | niedrig-mittel | mittel | Entscheidungsqualität + Wissensrobustheit | kritisches Expertenwissen verteilt; wiederkehrende Entscheidungen sind schwer nachvollziehbar |

### R01 – Maschinenbau / After Sales

```text
Unternehmen: mittelständischer Maschinenbauer, ca. 650 Mitarbeitende.
Bereich: After Sales / Service.
Ausgangslage: Kundenanliegen und interne Rückfragen benötigen häufig mehrere Abstimmungen zwischen Service, Technik und Ersatzteilbereich. Bearbeitungszeiten sind zu hoch und schwanken stark.
Informationslage: Ticket- und ERP-Daten existieren, sind aber nicht durchgehend miteinander verknüpft. Einzelne Teams arbeiten zusätzlich mit E-Mail und Dateien.
Ziel: Serviceleistung messbar verbessern, ohne die Lösung vorzugeben.
```

### R02 – Produktion / Qualität

```text
Unternehmen: produzierendes KMU, ca. 400 Mitarbeitende.
Bereich: Qualität und Produktion.
Ausgangslage: Nacharbeit und interne Qualitätsabweichungen haben zugenommen. Mehrere Beteiligte nennen unterschiedliche Ursachen; belastbare Messwerte liegen nur teilweise vor.
Informationslage: Prüfprotokolle, Schichtinformationen und Reklamationsdaten existieren in unterschiedlicher Qualität.
Ziel: einen sinnvollen Ansatzpunkt für messbare Verbesserung identifizieren.
```

### R03 – Bestell-/Freigabekontext

```text
Unternehmen: Handelsunternehmen, ca. 300 Mitarbeitende.
Bereich: interne Beschaffung und Freigaben.
Ausgangslage: Standardbestellungen warten häufig auf Freigaben. Betragsgrenzen und Zuständigkeiten sind grundsätzlich bekannt, trotzdem entstehen Rückfragen und Liegezeiten.
Informationslage: strukturierte Bestell-, Betrags- und Freigabedaten sind verfügbar.
Ziel: Durchlaufzeit und unnötige manuelle Arbeit reduzieren.
```

### R04 – Kundenservice

```text
Unternehmen: Dienstleistungs-KMU, ca. 800 Mitarbeitende.
Bereich: Kundenservice.
Ausgangslage: Kontaktvolumen ist hoch und saisonal. Kunden nutzen Telefon, E-Mail und Webformulare. Wiederholkontakte treten auf, ihre Ursachen sind nicht vollständig verstanden.
Informationslage: CRM- und Kontaktdaten sind umfangreich vorhanden; Freitext und Gesprächsinhalte sind jedoch uneinheitlich strukturiert.
Ziel: Servicequalität und Effizienz verbessern.
```

### R05 – HR / Onboarding

```text
Unternehmen: mittelständisches Unternehmen, ca. 550 Mitarbeitende.
Bereich: HR und Fachbereiche.
Ausgangslage: Neue Mitarbeitende erleben je nach Bereich sehr unterschiedliche Onboarding-Abläufe. Aufgaben werden verspätet erledigt, Zuständigkeiten wechseln und lokale Checklisten existieren parallel.
Informationslage: wenig zentrale Prozessdaten; hauptsächlich Checklisten, E-Mails und Erfahrungswissen.
Ziel: Onboarding verlässlicher und mit weniger Koordinationsaufwand gestalten.
```

### R06 – Field Service

```text
Unternehmen: technischer Serviceanbieter, ca. 450 Mitarbeitende.
Bereich: Außendienststeuerung.
Ausgangslage: Einsatztermine müssen häufig kurzfristig umgeplant werden. Qualifikation, Ersatzteile, Reiseweg, Kundentermin und Priorität beeinflussen die Planung.
Informationslage: Einsatz-, Mitarbeiter- und Auftragsdaten sind vorhanden, einzelne Randbedingungen werden aber manuell gepflegt.
Ziel: Planungsqualität erhöhen und Terminverschiebungen reduzieren.
```

### R07 – Strategischer B2B-Vertrieb / Wachstum

```text
Unternehmen: B2B-Industrieunternehmen, ca. 1.400 Mitarbeitende.
Bereich: strategischer Vertrieb und Key Account Management.
Ausgangslage: Das Unternehmen möchte Abschlussquote und Margenqualität in strategischen Kundenchancen steigern. Verlorene Angebote, Rabattentscheidungen und Kundenfeedback zeigen kein einheitliches Muster; reine Beschleunigung des Angebotsprozesses ist ausdrücklich nicht das Primärziel.
Informationslage: CRM, Angebotsdaten und Deckungsbeiträge sind vorhanden; qualitative Verlustgründe und Kundenfeedback sind uneinheitlich dokumentiert.
Ziel: einen belastbaren Hebel für profitables Wachstum identifizieren, ohne Technologie oder Prozessautomatisierung vorzugeben.
```

### R08 – Traceability / Risiko und Compliance

```text
Unternehmen: reguliertes Produktionsunternehmen, ca. 220 Mitarbeitende.
Bereich: Qualitätssicherung, Produktion und Compliance.
Ausgangslage: Bei internen Audits wurden Lücken in der Nachvollziehbarkeit von Chargen-, Prüf- und Freigabeinformationen sichtbar. Es gab noch keinen gravierenden Vorfall, aber das Management will das Risiko unvollständiger oder verspätet rekonstruierbarer Nachweise reduzieren. Effizienzgewinne sind willkommen, aber nicht das Primärziel.
Informationslage: Produktions-, Prüf- und Chargendaten sind überwiegend strukturiert vorhanden; Nachweise liegen teilweise über mehrere Systeme und Dokumentablagen verteilt.
Ziel: Rückverfolgbarkeit und Nachweissicherheit verbessern und dafür den sinnvollsten End-to-End-Hebel bestimmen.
```

### R09 – Retouren / Logistik

```text
Unternehmen: Großhandel, ca. 500 Mitarbeitende.
Bereich: Logistik, Kundenservice und Lager.
Ausgangslage: Retouren mit Abweichungen benötigen überdurchschnittlich viele Rückfragen und manuelle Klärung. Gründe reichen von beschädigter Ware über falsche Lieferung bis zu fehlenden Angaben.
Informationslage: ERP- und Lagerdaten vorhanden; Begründungen und Fotos sind teilweise unstrukturiert.
Ziel: Bearbeitungszeit reduzieren und unnötige Schleifen vermeiden.
```

### R10 – Engineering / Wissen und Entscheidungsqualität

```text
Unternehmen: projektorientierter Maschinen- und Anlagenbauer, ca. 1.100 Mitarbeitende.
Bereich: Engineering und Projektabwicklung.
Ausgangslage: Technische Entscheidungen zu Änderungen, Sonderfreigaben und wiederkehrenden Konstruktionsfragen hängen stark von wenigen erfahrenen Personen ab. Ähnliche Fragen werden in verschiedenen Projekten unterschiedlich entschieden; frühere Begründungen sind später schwer auffindbar. Das Kernproblem ist nicht primär Geschwindigkeit, sondern robuste und nachvollziehbare Entscheidungsqualität.
Informationslage: technische Dokumente, Änderungsinformationen und Projektakten existieren, sind aber über mehrere Ablagen und Systeme verteilt; Entscheidungsbegründungen sind uneinheitlich dokumentiert.
Ziel: Wissen und Entscheidungsqualität robuster machen, ohne eine bestimmte technische Lösung vorzugeben.
```

## 8. Session- und Rollen-Trennung

Jeder Run besteht aus drei logisch getrennten Kontexten.

### A. Blackbox-Run

- frische Session / frischer Modellkontext;
- nur Charter und Browserzugriff auf die App;
- kein Repo-Code;
- keine Ergebnisse früherer Runs;
- Run-Log wird während/nach dem Run aus Nutzersicht abgeschlossen.

### B. Unabhängiger Plausibilitätsreview

- andere Session bzw. anderer Reviewer;
- erhält nur ursprünglichen Charter und resultierenden fachlichen Stand/Export/Screenshots;
- erhält **nicht** die Entstehungsargumentation oder den vollständigen Dialog des Erstellungsagenten;
- prüft fachliche Plausibilität, nicht technische Ursache.

### C. Technische Diagnose

Erst nach Abschluss von A und B:

- Repo-Zugriff erlaubt;
- Code-Stellen und technische Ursache dürfen untersucht werden;
- Finding darf präzisiert, aber die ursprüngliche Blackbox-Beobachtung nicht umgeschrieben werden;
- keine Produktänderung in #429.

Wenn das verwendete lokale Agentenwerkzeug Repo-Zugriff nicht technisch deaktivieren kann, ist eine frische Blackbox-Session ohne zuvor eingebrachten Repo-Kontext das Mindestniveau. Diese Einschränkung wird im Run-Log vermerkt.

## 9. Run-Endzustände

Jeder Run erhält genau einen Status:

| Status | Bedeutung |
|---|---|
| `AI_USE_CASE_CREATED` | bevorzugte Lösung enthält tatsächliche KI-Komponente und daraus wurde regulär ein konkreter Use Case angelegt |
| `NON_AI_DISCOVERY_COMPLETE` | bevorzugte Lösung ist Non-AI; Discovery endet nachvollziehbar ohne künstlichen KI-Use-Case |
| `PRODUCT_ABORT` | Produkt verhindert den sinnvollen Fortgang durch Bug, inkonsistenten Blocker oder echten Dead End |
| `AGENT_TOOL_ABORT` | Browser-/Agent-/Toolproblem verhindert den Fortgang ohne erkennbaren Produktblocker |
| `INVALID_RUN` | Testprotokoll wurde verletzt, z. B. Repo-Wissen im Blackbox-Kontext oder falsche Rolle; Run muss gemäß Restart-Regel behandelt werden |

`NON_AI_DISCOVERY_COMPLETE` ist ausdrücklich **kein Fehlschlag**.

## 10. Verbindliches Run-Log-Template

Für jeden Run ist dasselbe Schema zu verwenden.

```md
# AET-RXX – Run Log

## Identität / Setup
- Run-ID:
- Datum / Start / Ende:
- getesteter main-SHA:
- App-/Umgebungskennung:
- Agent / Modell:
- Browser-/Computer-Use-Tooling:
- Testnutzer:
- fachliche Rolle: Business Owner
- Permission-Profil entspricht Standard: ja/nein
- Abweichung + Begründung:
- Blackbox-Session frei von Repo-Kontext: ja/nein
- Clean-State bestätigt: ja/nein

## Charter
<unverändert eingefügter Ausgangsrahmen>

## Fachlicher Verlauf
- gewählter Value Stream:
- Value-Stream-Grenze / Trigger / Outcome:
- gewählte Fokusphase:
- Begründung der Fokusentscheidung:
- Prozess-Deep-Dive:
- beobachtete Probleme/Symptome:
- Ursachenhypothesen:
- bestätigte Ursachen bzw. als offen markierte Ursachen:
- Baseline/Evidenz: bekannt / hypothesenbasiert / offen:
- erzeugte Lösungsoptionen:
- bevorzugte Lösung:
- Auswahlbegründung:
- enthält tatsächliche KI-Komponente: ja/nein:
- finaler Use Case (falls KI):
- Run-Endstatus:

## UX / Interaktion
- unklare Begriffe/Felder:
- fehlende oder missverständliche Hilfetexte:
- Rücksprünge:
- Sackgassen:
- unerwartete Gates/Blocker:
- Next-Action-Probleme:
- Doppeleingaben/Wiederholungen:
- besonders hilfreiche Führung:
- grobe Bearbeitungsdauer:
- grober Interaktionsumfang (optional):
- auffällige No-Progress-Phasen:

## Findings
<pro Finding das Schema aus Abschnitt 11>

## Abbruch, falls zutreffend
- Typ: Produkt / Agent-Tool / Invalid Run
- letzter erfolgreicher fachlicher Zustand:
- konkrete Ursache:
- ausgeführte Retry-/No-Progress-Regel:
- Screenshot-/Log-Referenz:

## Artefakte
- Screenshots:
- Export/Review-Unterlage:
- weitere Referenzen:
```

## 11. Finding-Schema und Klassifikation

### 11.1 Finding-Template

```md
### AET-RXX-FYY – <Kurztitel>
- Journey-Schritt:
- Screen/Route aus Nutzersicht:
- Kategorie:
- Beobachtung:
- erwartetes/hilfreicheres Verhalten:
- Auswirkung:
- Schweregrad: niedrig / mittel / hoch / kritisch
- reproduzierbar: ja / nein / noch offen
- Screenshot/Artefakt:
- Blackbox-Befund:
- technische Diagnose: <erst nach Review ergänzen>
- Produktproblem / Agent-Tool / Testsetup-Permission / erwartetes Verhalten:
```

### 11.2 Kategorien

Verbindliche Kategorien:

```text
Methodik / fachliche Führung
UX / Verständlichkeit
Navigation / Next Action
Validierung / Gate
Datenmodell / Inkonsistenz
Funktionaler Bug
Technischer Fehler
Testsetup / Permission
Agent / Browser / Tool
Kein Problem / erwartetes Verhalten
```

### 11.3 Schweregrad

- **kritisch:** Datenverlust, unzulässiger Zustand, Sicherheits-/Integritätsproblem oder vollständiger reproduzierbarer Abbruch des Kernpfads;
- **hoch:** zentraler Discovery-Schritt kann nicht sinnvoll abgeschlossen werden oder führt wiederholt zu fachlich falscher Entscheidung;
- **mittel:** relevante Reibung/Fehlführung mit Workaround;
- **niedrig:** lokales Verständlichkeits-/Darstellungsproblem ohne wesentlichen Einfluss auf Ergebnis.

Häufigkeit und Schweregrad bleiben getrennte Achsen.

## 12. Progressbasierte Retry-/No-Progress-Regel

Es gibt **keine harte Minutenbegrenzung** als primäres Abbruchkriterium.

Zeit wird beobachtet, aber Fortschritt entscheidet.

### 12.1 Definition Fortschritt

Fortschritt liegt vor, wenn mindestens eines eintritt:

- neuer fachlicher Zustand gespeichert;
- neuer Journey-Schritt erreicht;
- Blocker wurde durch eine fachlich zulässige Aktion reduziert;
- eine neue, relevante Produktinformation erklärt den nächsten zulässigen Schritt;
- ein technischer Fehlversuch wurde durch einen alternativen legitimen Bedienweg erfolgreich überwunden.

### 12.2 Retry-Regel

Bei einem fehlgeschlagenen Browser-/Tool-Schritt:

1. Aktion einmal unverändert erneut versuchen, wenn ein transienter Toolfehler plausibel ist.
2. Falls weiterhin kein Fortschritt: genau einen alternativen, im sichtbaren UI naheliegenden Bedienweg versuchen.
3. Falls danach weiterhin derselbe Zustand ohne neue Information besteht: **No Progress** feststellen und klassifizieren.

Maximal zwei Wiederhol-/Alternativversuche nach dem ursprünglichen Fehlschlag, sofern nicht zwischenzeitlich echter Fortschritt eintritt.

Der Agent darf nicht in Schleifen denselben Button, dieselbe Navigation oder denselben Submit wiederholen.

### 12.3 Abbruchklassifikation

**Produktbedingter Abbruch (`PRODUCT_ABORT`)**, wenn der sichtbare Produktzustand den fachlich notwendigen Fortgang reproduzierbar verhindert, z. B.:

- serverseitiger Fehler;
- unerfüllbarer oder widersprüchlicher Gate-Zustand;
- kein zulässiger nächster Schritt trotz erfüllter sichtbarer Anforderungen;
- fachlicher Dead End innerhalb des vorgesehenen Pfads.

**Agent-/Tool-Abbruch (`AGENT_TOOL_ABORT`)**, wenn z. B.:

- Browserautomation trotz Retry-Regel technisch nicht mehr bedienbar ist;
- Tool-Timeout wiederholt ohne App-Ursache auftritt;
- Session notwendigen Kontext verliert und ihn nicht wiederherstellen kann;
- das Modell wiederholt den Charter verletzt;
- ein Computer-Use-Limit weitere Bedienung verhindert.

**Invalid Run (`INVALID_RUN`)**, wenn die Testintegrität verletzt wurde, z. B. falsche Rolle, Repo-Wissen im Blackbox-Kontext oder sichtbare Altartefakte trotz Clean-State-Anforderung.

### 12.4 Restart-Regel

- Ein `AGENT_TOOL_ABORT` oder `INVALID_RUN` darf mit **demselben Charter genau einmal** aus sauberem Ausgangszustand und frischer Session neu gestartet werden.
- Der erste Versuch bleibt dokumentiert und wird nicht gelöscht.
- Scheitert auch der Restart agent-/toolbedingt, bleibt der Run für die Aussagekraft als eingeschränkt markiert; nicht durch einen elften Ersatz-Charter kaschieren.
- `PRODUCT_ABORT` wird nicht neu gestartet, nur um einen erfolgreichen Run zu erzwingen. Technische Reproduktion erfolgt später im Diagnosekontext.

## 13. Zeit- und Aufwandsdaten

Pro Run protokollieren:

- grobe Gesamtdauer;
- optional grobe Anzahl relevanter Interaktionen/Seitenwechsel;
- auffällige Phasen ohne Fortschritt;
- Abbruchursache, falls vorhanden.

Diese Werte sind **keine harte Erfolgsmetrik**. Ein einzelner langer Run ist kein Produktfehler. Wiederholt hoher Aufwand am selben Journey-Schritt über mehrere Runs ist dagegen ein Cross-Run-Signal.

## 14. Unabhängiger Plausibilitätsreview

Der Reviewer erhält:

- ursprünglichen Charter;
- resultierenden fachlichen Stand;
- relevante sichtbare Exporte/Screenshots.

Nicht erhalten:

- vollständigen Erstellungsdialog;
- interne Argumentation des Erstellungsagenten;
- technische Diagnose.

### Review-Template

```md
# AET-RXX – Independent Plausibility Review

- Value Stream passend zum Ausgangsproblem: ja / teilweise / nein
- E2E-Grenze plausibel: ja / teilweise / nein
- Fokusentscheidung nachvollziehbar: ja / teilweise / nein
- Problem vor Lösung analysiert: ja / teilweise / nein
- Symptom, Hypothese und bestätigte Ursache sauber getrennt: ja / teilweise / nein
- unbekannte Fakten transparent statt erfunden: ja / teilweise / nein
- mindestens zwei echte Lösungsalternativen betrachtet: ja / teilweise / nein
- Alternativen ausreichend unterschiedlich: ja / teilweise / nein
- Lösungspräferenz aus Diagnose herleitbar: ja / teilweise / nein
- KI nur gewählt, wenn gegenüber einfacheren Alternativen plausibel: ja / teilweise / nein / nicht zutreffend
- Non-AI-Abschluss akzeptiert statt künstlichen KI-Use-Case erzwungen: ja / nein / nicht zutreffend
- finaler Use Case aus Upstream-Kontext nachvollziehbar: ja / teilweise / nein / nicht zutreffend
- wesentliche Evidenzlücken sichtbar: ja / teilweise / nein

Kurzurteil:
- robust
- teilweise robust
- schwach

Wichtigste Begründung:
<max. wenige Absätze>
```

Der Reviewer bewertet keine statistische Signifikanz und vergibt keinen künstlichen Gesamtscore.

## 15. Technische Diagnose nach Blackbox + Review

Erst danach kann derselbe Run technisch untersucht werden.

Für relevante Findings ergänzen:

- reproduzierbar gegen denselben SHA;
- betroffene View/Form/Service/Template bzw. Domainregel;
- erwartetes Gate vs. tatsächliches Verhalten;
- vermutete technische Ursache;
- vorhandene Tests, falls relevant;
- Konflikt zwischen UI/Journey/Domain, falls vorhanden.

Keine Lösung implementieren. #429 bleibt reine Validierung.

## 16. Cross-Run-Schema

Nach Abschluss aller zehn Runs werden Einzelbefunde nicht einfach hintereinander aufgelistet, sondern zu Mustern gruppiert.

### 16.1 Pattern-Tabelle

| Pattern-ID | Muster | betroffene Runs | Journey-Schritt | Kategorie | Häufigkeit | Auswirkung | Reproduzierbarkeit | Interpretation | Priorität |
|---|---|---|---|---|---:|---|---|---|---|

Priorität qualitativ aus mindestens diesen Achsen ableiten:

```text
Häufigkeit
× fachliche Auswirkung
× Blockierwirkung
× Reproduzierbarkeit
```

Kein numerischer Gesamtscore erforderlich.

### 16.2 Verbindliche Cross-Run-Fragen

1. Führt das Modell aus unterschiedlichen Ausgangslagen nachvollziehbar von Problemkontext zur Lösungsentscheidung?
2. Wo werden Value Streams wiederholt zu breit oder zu eng geschnitten?
3. Wo scheitert die Auswahl einer sinnvollen Fokusphase?
4. Werden Symptome, Ursachenhypothesen und bestätigte Ursachen sauber getrennt?
5. Werden unbekannte Zahlen/Evidenzen sichtbar als offen behandelt oder erfunden?
6. Entstehen mindestens zwei echte Lösungsoptionen oder nur Varianten derselben Idee?
7. Wird eine Lösung ausgewählt, bevor die Diagnose belastbar ist?
8. Wie oft endet Discovery plausibel mit Non-AI?
9. Gibt es ein systematisches Bias in Richtung KI oder eines anderen Lösungstyps?
10. Falls eine Lösungsklasse auffällig häufig gewählt wird: bleibt die Konvergenz **über unterschiedliche Zielarten** (Effizienz, Qualität, Wachstum, Risiko/Compliance, Wissens-/Entscheidungsqualität) bestehen, oder lässt sie sich plausibel durch die Szenarioverteilung erklären?
11. Falls KI gewählt wird: ist der KI-Anteil gegenüber einfacheren Alternativen plausibel?
12. Welche Gates erhöhen Qualität, welche erzeugen überwiegend Reibung?
13. Wo fehlen klare Next Actions oder verständliche Erklärungen?
14. Welche Informationen müssen unnötig mehrfach erfasst werden?
15. Welche UX-Probleme treten in mehreren fachlich unterschiedlichen Fällen auf?
16. Welche Befunde sind echte Produktprobleme und welche nur Agent-/Toolartefakte?
17. Welche Journey-Schritte erzeugen wiederholt ungewöhnlich hohen Aufwand?

### 16.3 Pflichtprüfung: Szenario-Framing als Confounder

Eine beobachtete Lösungskonvergenz darf **nicht automatisch** als Methodik-Bias des KI-UseCase-Radars gewertet werden.

Vor einer solchen Aussage ist mindestens zu prüfen:

- treten gleiche Lösungstypen nur in ähnlich gerahmten Effizienz-/Koordinationsfällen auf oder auch bei Wachstum, Risiko/Compliance und Wissens-/Entscheidungsproblemen?
- korreliert die Lösungsklasse stärker mit Datenreife, Problemcharakter oder Zielart als mit der Produktführung?
- wurden die Alternativen in den einzelnen Runs tatsächlich offen erzeugt und erst später verengt?
- zeigt sich dasselbe Bias-Signal auch in Szenarien, deren Ausgangsrahmen diesen Lösungstyp nicht offensichtlich nahelegt?

Interpretationsregel:

> Erst wenn eine Lösungsklasse über **unterschiedliche Zielarten und Problemcharaktere hinweg** auffällig bevorzugt wird und die einzelnen Reviews keine sachliche Erklärung aus dem jeweiligen Charter liefern, darf dies als belastbares Signal für ein mögliches Methodik-/Produkt-Bias gewertet werden.

Wenn die Konvergenz plausibel durch die Stichprobe erklärbar ist, muss das Cross-Run-Review dies ausdrücklich als **Stichproben-/Framing-Effekt** kennzeichnen statt der App zuzuschreiben.

### 16.4 Gesamturteil

Abschluss entlang folgender Dimensionen:

- Discovery-Führung: `robust / teilweise robust / schwach`
- Problem-vor-Lösung-Prinzip: `eingehalten / teilweise / häufig verletzt`
- Lösungsneutralität: `robust / Bias erkennbar / durch Stichprobe nicht eindeutig beurteilbar`
- Stichproben-/Framing-Einfluss: `gering / relevant / stark einschränkend`
- Use-Case-Herleitung: `nachvollziehbar / uneinheitlich / schwach`
- Non-AI-Fähigkeit: `funktioniert / teilweise / wird faktisch verdrängt`
- UX-Unterstützung: `ausreichend / reibungsreich / blockierend`
- Gate-Qualität: `überwiegend hilfreich / gemischt / kontraproduktiv`
- Testaussage: `qualitativ belastbar / durch Agent-Toolprobleme eingeschränkt / durch Stichproben-Framing eingeschränkt`

## 17. Ablagestruktur für #429

Empfohlene Struktur:

```text
docs/planning/agentic-test-runs/
  AET-R01.md
  AET-R01-review.md
  ...
  AET-R10.md
  AET-R10-review.md
  screenshots/
    AET-R01-...
    ...
docs/planning/AGENTIC_TEST_RUNS_REVIEW.md
```

Die Run-Logs und Reviews bleiben einzeln nachvollziehbar. `AGENTIC_TEST_RUNS_REVIEW.md` enthält anschließend die verdichtete Cross-Run-Analyse statt zehn vollständige Logs zu duplizieren.

## 18. Definition of Done für #428

- [x] aktueller Discovery-Pfad gegen `main` geprüft;
- [x] wesentliche appseitige Gates als bekannter Rahmen dokumentiert;
- [x] Master-Charter ist fachlich offen und enthält keine Klick-/Lösungsvorgabe;
- [x] Freiheit des Agenten auf fachliche Inhalte innerhalb des geführten Pfads korrekt beschrieben;
- [x] Blackbox, unabhängiger Plausibilitätsreview und technische Diagnose getrennt;
- [x] Golden-Path-/Supplier-Demo und vorbereitete Referenzfälle ausgeschlossen;
- [x] reproduzierbarer Clean-State als Voraussetzung definiert;
- [x] zehn unterschiedliche Runs eindeutig festgelegt;
- [x] Fachbereich, Datenreife und Pain-Point-Klarheit variieren;
- [x] Zielarten variieren über Effizienz, Qualität, Wachstum, Risiko/Compliance und Wissens-/Entscheidungsqualität;
- [x] Fälle ermöglichen sowohl KI- als auch Non-AI-Ergebnisse;
- [x] Run-Log-Template festgelegt;
- [x] Finding-Schema und Kategorien festgelegt;
- [x] Produktprobleme, Permission/Testsetup und Agent-/Toolprobleme sind trennbar;
- [x] Run-Endzustände einschließlich erfolgreichem Non-AI-Abschluss definiert;
- [x] Abbruch-/Restart-Regeln festgelegt;
- [x] unabhängiger Plausibilitätsreview definiert;
- [x] Cross-Run-Schema inklusive Confounder-Prüfung für Szenario-Framing festgelegt;
- [x] kanonische Testrolle `Business Owner` gegen aktuellen Permission-Stand festgelegt;
- [x] gezieltes Permission-Testing abgegrenzt;
- [x] progressbasierte Retry-/No-Progress-Regel definiert;
- [x] Bearbeitungsdauer nur als Diagnose-/Cross-Run-Signal definiert;
- [x] kein Produktcode geändert.

## 19. Übergabe an #429

#429 verwendet dieses Dokument unverändert als Testvertrag.

Vor Run 1 sind dort nur noch die Ausführungsparameter festzuhalten:

1. final getesteter `main`-SHA;
2. konkrete lokale App-/DB-Umgebung;
3. konkrete Testidentität mit dem hier definierten Business-Owner-Profil;
4. technisch verwendeter Mechanismus zum Wiederherstellen des Clean State;
5. konkretes Agent-/Browser-Tooling.

Diese Parameter dürfen den Charter nicht fachlich umschreiben.

Während der zehn Runs gilt strikt:

```text
finden → protokollieren → unabhängig reviewen → technisch diagnostizieren

nicht:

finden → reparieren → nächsten Run auf verändertem Produktstand ausführen
```
