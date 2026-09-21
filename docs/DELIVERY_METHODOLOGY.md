# Methodische Referenz des Delivery-Handover

Diese Seite dokumentiert die methodische Herkunft der Delivery-Package-Struktur in KI-Ideenwerkstatt. Sie dient dem Delivery-Team zur Einordnung der übergebenen Inhalte und dem KI-Koordinator als dauerhafte Referenz bei methodischen Rückfragen.

KI-Ideenwerkstatt verwendet **CRISP-ML(Q)** als Lebenszyklus- und Qualitätssicherungsrahmen sowie den **Google ML Test Score** als Referenz für produktionsrelevante Prüfbereiche. Daraus entsteht innerhalb von KI-Ideenwerkstatt kein zusätzlicher Workflow, keine automatische Score-Berechnung und keine Zertifizierung. Die operative Umsetzung, technische Detailplanung und Erfüllung der Produktionsreifeprüfungen verbleiben beim Delivery-Team.

## Mapping der sieben Delivery-Sektionen

| Delivery-Sektion | Methodischer Bezug |
|---|---|
| **1. Problem und Ziel** | CRISP-ML(Q): Business and Data Understanding; Geschäftsproblem, Baseline und messbare Zielgrößen |
| **2. Scope, Nutzer und MVP** | CRISP-ML(Q): Business and Data Understanding; Anwendungskontext, Nutzer, Prozessgrenzen und kleinstes validierbares Inkrement |
| **3. Gewählte Lösungsrichtung** | CRISP-ML(Q): Modeling; Vergleich mit einer einfacheren Baseline und Begründung der gewählten Lösungsoption |
| **4. System-, Daten- und Integrationskontext** | CRISP-ML(Q): Data Preparation und Vorbereitung des Deployment; ML Test Score: Daten und Infrastruktur |
| **5. Anforderungen und Governance** | Phasenübergreifende Quality Assurance; Security, Datenschutz, Human Oversight, Logging, Betrieb und Support |
| **6. Akzeptanz und Erfolgsmessung** | CRISP-ML(Q): Evaluation; fachliche und technische Akzeptanz, Testfälle und Messkonzept |
| **7. Risiken, Abhängigkeiten und Umsetzungsstart** | CRISP-ML(Q): Deployment sowie Monitoring and Maintenance; Voraussetzungen, Auflagen, Verantwortlichkeiten und initialer Umsetzungsrahmen |

## Scope-Priorisierung nach MoSCoW

Die Delivery-Sektion **„Scope, Nutzer und MVP“** verwendet für die Priorisierung des Lieferumfangs die etablierte **MoSCoW-Methode**. Sie konkretisiert den bereits freigegebenen Scope für eine konkrete Delivery-Version und erzeugt keinen zusätzlichen Workflow, Score, Freigabeschritt oder eine neue Governance-Entscheidung.

- **Must:** unverzichtbarer Mindestumfang; wird im bestehenden Feld `mvp_scope` als **Must / MVP-Scope** geführt.
- **Should:** wichtiger Umfang, der nach dem Must-Scope folgen soll, für den Mindestnutzen aber nicht zwingend ist.
- **Could:** optionaler Umfang mit zusätzlichem Nutzen, sofern Zeit und Kapazität verfügbar sind.
- **Won't this time:** grundsätzlich denkbarer beziehungsweise zulässiger Umfang, der bewusst für diese Delivery-Version zurückgestellt wird.

`in_scope` und `out_of_scope` bleiben davon getrennte Scope-Grenzen. Insbesondere ist **Won't this time nicht dasselbe wie `out_of_scope`**: `out_of_scope` liegt außerhalb der fachlich gesetzten Grenze, während Won't this time innerhalb des grundsätzlich möglichen Lösungsrahmens liegt, aber für das aktuelle Inkrement bewusst nicht umgesetzt wird.

Die in MoSCoW-/DSDM-Kontexten häufig verwendete Leitlinie, den Must-Anteil bewusst zu begrenzen (beispielsweise auf ungefähr 60 % der erwarteten Umsetzungskapazität), dient hier nur als methodischer Denkanstoß gegen einen überladenen MVP-Scope. KI-Ideenwerkstatt berechnet oder erzwingt keinen 60-%-Wert, solange keine belastbaren Aufwandsschätzungen auf Ebene einzelner Scope-, Requirement- oder Backlog-Items vorliegen.

## Einordnung für Delivery

Das Delivery Package bildet nicht den vollständigen CRISP-ML(Q)-Lebenszyklus innerhalb von KI-Ideenwerkstatt ab. Es übergibt den freigegebenen Problem-, Scope-, Lösungs-, Architektur- und Qualitätsrahmen. Deployment, Rollback, laufendes Monitoring und die eigentliche ML-Test-Score-Erhebung werden während der Umsetzung und im Betrieb durch die zuständigen Delivery- und Betriebsteams durchgeführt.

## Verbindliche Präzisierungen für ein übergabefähiges Package

### Architekturartefakte

Zielarchitektur beziehungsweise Systemkontext und Daten-/Informationsfluss müssen im Package konkret beschrieben oder über vorhandene Architekturartefakte referenziert sein. Eine externe Diagramm-URL ist optional, wenn diese beiden Sichten im Package selbst belastbar dokumentiert sind. Komponenten-, Integrations- und Trust-/Security-Boundaries werden ergänzt, wenn Risiko und Lösungsreife dies erfordern.

### Evaluation, Qualitätsmetriken und Stichproben

Prozentuale Qualitätsgrenzen werden immer gemeinsam mit Metrik, betrachteter Testpopulation und Stichprobengröße interpretiert. Bei kleinen Populationen wird die Aussagekraft über ein Konfidenzintervall, eine Fehlerspanne oder eine gleichwertige verständliche Unsicherheitsaussage eingeordnet. Seltene oder kritische Fehlerklassen erhalten gezielte Testfälle oder kuratierte Testsets; ein aggregierter Prozentwert ersetzt diese Prüfung nicht. Recall-Ziele benennen insbesondere die Anzahl positiver Fälle.

### Confidence und Unsicherheit nach Output-Typ

- **Extraktion/Klassifikation:** Numerische Confidence nur, wenn sie technisch vorhanden, fachlich definiert und möglichst kalibriert ist.
- **Generative Texte/Vorschläge:** Quellenbezug beziehungsweise Grounding, fehlende Grundlagen und Unsicherheit sichtbar machen; keinen pseudo-präzisen numerischen Score erzwingen.
- **Regelbasierte Prüfung:** Regelreferenz, Prüfergebnis und bei Bedarf Regelversion oder Herkunft ausweisen.

### Ende-zu-Ende-Latenz, Timeouts und Retries

Das nutzerseitige Ende-zu-Ende-Latenzbudget ist das verbindliche Gesamtbudget. Request-, Provider- und Komponenten-Timeouts sind davon getrennt auszuweisen. Sämtliche synchronen Versuche einschließlich Retries müssen in das Gesamtbudget passen. Andernfalls erfolgt der Retry außerhalb des synchronen Nutzerpfads oder es greift ein deterministischer, testbarer Fallback.

### Audit und Retention

Aufbewahrung und Löschung werden mindestens getrennt für Audit-/Traceability-Metadaten, Prompt-/Input-Rohinhalte, Dokumentinhalte, personenbezogene oder besonders schutzbedürftige Daten sowie technische Logs/Betriebsdaten beschrieben. Jede Kategorie erhält Zweckbindung und Löschfrist. Eine längere Auditfrist für Metadaten begründet keine gleich lange Speicherung vollständiger Rohinhalte.

### Beispiele für belastbare Delivery-Angaben

- **Evaluation:** `Testpopulation: eingehende Rechnungen; n=400, davon 62 positive Fälle; 95-%-Konfidenzintervall dokumentiert; kritische Betragsfehler mit 20 gezielten Testfällen.`
- **Latenz:** `P95-E2E-Budget 8 Sekunden; Provider-Timeout 2 Sekunden; zwei synchrone Retries; maximale Gesamtdauer aller synchronen Versuche 6 Sekunden.`
- **Retention:** Jede Kategorie steht in einer eigenen Policy-Zeile, beispielsweise `Prompt-/Input-Rohinhalte — Zweck: Verarbeitung der Anfrage; nicht persistiert.` Audit-Metadaten, Dokumentinhalte, personenbezogene Daten und technische Logs erhalten entsprechend jeweils einen eigenen Zweck und eine konkrete Frist oder Löschregel.

---

# Vollständiges Vorgehensmodell Version 2.0

Nachfolgend ist das im Projekt verbindlich hinterlegte Vorgehensmodell vollständig, ungekürzt und ohne Umformulierungen wiedergegeben.

---

# Vorgehensmodell für produktionsreife KI-Systeme

**Bezeichnung:** CRISP-ML(Q) mit integriertem ML Test Score
**Version:** 2.0
**Zweck:** KI- und Machine-Learning-Anwendungen strukturiert vom Geschäftsproblem bis zum kontrollierten Produktivbetrieb entwickeln.

---

# 1. Status und Herkunft des Vorgehensmodells

Dieses Dokument ist **kein eigenständiger wissenschaftlicher Standard** und kein ISO-zertifiziertes Vorgehensmodell.

Es ist eine konsolidierte Anwendungsvorlage auf Basis von:

1. **CRISP-ML(Q)** als Entwicklungs- und Lebenszyklusmodell,
2. **Google ML Test Score** als Prüfrubrik für technische Produktionsreife,
3. ergänzenden, ausdrücklich gekennzeichneten Projektregeln für:

   * Quality Gates,
   * Rollen und Eskalationen,
   * Tailoring nach Projektgröße,
   * Übertragung auf generative KI.

CRISP-ML(Q) beschreibt sechs Phasen und integriert Qualitätssicherung sowie risikobezogene Maßnahmen in die Aufgaben jeder Phase. Das Modell wurde aus wissenschaftlicher Literatur und praktischer Industrieerfahrung abgeleitet.

Der ML Test Score enthält 28 Prüfungen aus den Bereichen Daten, Modellentwicklung, Infrastruktur und Monitoring. Die Autoren leiteten die Rubrik aus Erfahrungen mit Produktionssystemen und Interviews mit 36 Google-Teams ab.

## Verbindliche Kommunikationsregel

Das Vorgehen darf bezeichnet werden als:

> **Auf CRISP-ML(Q) und dem Google ML Test Score basierendes, operationalisiertes Vorgehensmodell.**

Es darf nicht bezeichnet werden als:

* empirisch bewiesener Erfolgsstandard,
* offizieller CRISP-ML(Q)-Standard,
* Google-zertifiziertes Vorgehen,
* ISO-konformes Gesamtverfahren,
* validiertes GenAI-Lifecycle-Modell.

---

# 2. Geltungsbereich

Das Vorgehensmodell ist geeignet für:

* klassische Machine-Learning-Anwendungen,
* Prognose- und Klassifikationssysteme,
* Entscheidungsunterstützung,
* Dokumentenverarbeitung,
* LLM-Anwendungen,
* Retrieval-Augmented Generation,
* begrenzte agentische Systeme,
* KI-gestützte Geschäftsprozesslösungen.

Es ist nicht allein ausreichend für:

* sicherheitskritische Systeme,
* medizinische Diagnostik mit unmittelbarer Patientengefährdung,
* autonome Fahrzeugsteuerung,
* kritische Industrie- oder Infrastruktursteuerung,
* Anwendungen mit vorgeschriebener Fachzertifizierung,
* Systeme, bei denen ein Fehler unmittelbar Leib, Leben oder erhebliche Sachwerte gefährden kann.

CRISP-ML(Q) weist ausdrücklich darauf hin, dass seine Prozesse und Qualitätsmaßnahmen nicht für sicherheitskritische Systeme entworfen wurden und dort andere oder zusätzliche Verfahren notwendig sein können.

---

# 3. Grundprinzipien

## 3.1 Lebenszyklus statt lineares Projekt

Die sechs Phasen werden nicht als einmalig durchlaufener Wasserfall verstanden.

Rücksprünge sind ausdrücklich zulässig und häufig notwendig:

```text
Business and Data Understanding
              ↓
       Data Preparation
              ↓
           Modeling
              ↓
          Evaluation
              ↓
          Deployment
              ↓
 Monitoring and Maintenance
              ↺
```

Ergebnisse aus Evaluation, Deployment oder Betrieb können Änderungen an:

* Anforderungen,
* Daten,
* Modellierung,
* Architektur,
* Erfolgskriterien

auslösen.

---

## 3.2 Qualitätssicherung ist phasenübergreifend

**Evaluation ist eine eigene Phase. Qualitätssicherung ist trotzdem keine einzelne Phase.**

In jeder Phase werden betrachtet:

1. Anforderungen und Einschränkungen,
2. relevante Risiken,
3. geeignete Qualitätsmaßnahmen,
4. überprüfbare Nachweise,
5. Entscheidung über Fortsetzung oder Rücksprung.

CRISP-ML(Q) beschreibt Qualitätssicherung auf Aufgabenebene innerhalb aller Phasen, um Fehler möglichst früh zu erkennen.

---

## 3.3 Nachweise statt Selbsteinschätzung

Eine Anforderung gilt nicht als erfüllt, nur weil ein Teammitglied sie bestätigt.

Akzeptierte Nachweise sind beispielsweise:

* Testprotokolle,
* versionierte Konfigurationen,
* Messwerte,
* freigegebene Dokumente,
* automatisierte Testläufe,
* Monitoring-Dashboards,
* Architekturentscheidungen,
* Freigabeprotokolle,
* nachvollziehbare Tickets oder Reviews.

---

## 3.4 Einfachste ausreichende Lösung

Jede komplexe KI-Lösung muss gegen eine einfachere Baseline geprüft werden.

Mögliche Baselines:

* bestehender manueller Prozess,
* feste Geschäftsregel,
* einfache statistische Methode,
* klassisches Suchverfahren,
* einfaches Modell,
* einzelner LLM-Aufruf ohne Agentenlogik,
* einfaches RAG ohne Graph- oder Multi-Agent-Komponenten.

Der ML Test Score enthält ausdrücklich die Prüfung, ob ein einfacheres Modell beziehungsweise eine einfachere Lösung nicht besser ist.

---

## 3.5 Keine Kompensation kritischer Lücken

Gute Modellqualität gleicht keine fehlende Betriebskontrolle aus.

Ebenso gleichen starke Infrastrukturtests keine schlechte Datenqualität aus.

Deshalb verwendet der ML Test Score den niedrigsten Wert der vier Kategorien als Gesamtscore.

---

# 4. Rollen und Verantwortlichkeiten

## 4.1 Business Owner

Verantwortet:

* Geschäftsproblem,
* fachliche Zielsetzung,
* Business-KPI,
* Prozessintegration,
* fachliche Abnahme,
* wirtschaftliche Entscheidung,
* Akzeptanz fachlicher Restrisiken.

Der Business Owner darf technische Risiken nicht allein akzeptieren.

---

## 4.2 Technical Owner

Verantwortet:

* technische Lösung,
* Architektur,
* Integration,
* Sicherheit auf Systemebene,
* Deployment,
* Betrieb,
* technische Schulden,
* technische Abnahme,
* Akzeptanz technischer Restrisiken.

Der Technical Owner darf fachliche oder wirtschaftliche Zielabweichungen nicht allein akzeptieren.

---

## 4.3 Data beziehungsweise AI Owner

Verantwortet:

* Datenqualität,
* Datenherkunft,
* Modell- oder LLM-Konfiguration,
* Evaluation,
* Modellgrenzen,
* ML Test Score,
* Regressionstests,
* Qualitätsmonitoring.

Bei kleinen Projekten kann diese Rolle mit dem Technical Owner zusammenfallen.

---

## 4.4 Risk-, Datenschutz- oder Compliance-Verantwortlicher

Wird verbindlich eingebunden, wenn mindestens einer der folgenden Punkte vorliegt:

* personenbezogene Daten,
* vertrauliche Unternehmensdaten,
* automatisierte Bewertung von Personen,
* regulatorische Anforderungen,
* externe Modellanbieter,
* erhebliche Informationssicherheitsrisiken,
* relevante Grundrechts- oder Diskriminierungsrisiken.

---

## 4.5 Gate Owner

Für jedes Quality Gate wird vor Projektbeginn ein Gate Owner benannt.

Der Gate Owner:

* organisiert die Prüfung,
* kontrolliert die Nachweise,
* dokumentiert die Entscheidung,
* darf fehlende Nachweise nicht durch persönliche Einschätzung ersetzen.

Der Gate Owner muss nicht alle Inhalte selbst beurteilen, ist aber für die Vollständigkeit der Entscheidung verantwortlich.

---

# 5. Konflikt- und Eskalationsverfahren

## 5.1 Grundregel

Ein Quality Gate ist nur bestanden, wenn:

* alle Muss-Kriterien erfüllt sind oder
* offene Abweichungen ausdrücklich akzeptiert wurden.

## 5.2 Konflikt zwischen Business und Technik

Bei Uneinigkeit zwischen Business Owner und Technical Owner gilt:

1. Die strittige Abweichung wird schriftlich dokumentiert.
2. Auswirkungen auf Nutzen, Kosten, Qualität, Sicherheit und Betrieb werden dargestellt.
3. Es werden mindestens zwei Optionen formuliert:

   * Fortsetzung unter Auflagen,
   * Rücksprung oder Stopp.
4. Die Entscheidung wird an den benannten Projekt- oder Produktverantwortlichen eskaliert.
5. Technische oder regulatorische Ausschlusskriterien dürfen nicht durch eine reine Business-Entscheidung überstimmt werden.

## 5.3 Nicht überstimmbare Stop-Kriterien

Ein Gate darf nicht freigegeben werden bei:

* ungeklärtem Verstoß gegen Recht oder verbindliche Regulierung,
* fehlender Rechtsgrundlage für relevante Datenverarbeitung,
* unkontrolliertem Zugriff auf sensible Daten,
* fehlender Möglichkeit zur Deaktivierung eines kritischen Systems,
* unbekannter Verantwortlichkeit für den Betrieb,
* nicht beherrschbarem kritischem Sicherheitsrisiko,
* sicherheitskritischem Einsatz ohne ergänzendes Fachverfahren.

## 5.4 Conditional Go

Ein **Conditional Go** ist zulässig, wenn:

* kein Stop-Kriterium vorliegt,
* jede Abweichung dokumentiert ist,
* eine verantwortliche Person benannt ist,
* eine Frist besteht,
* eine Kompensationsmaßnahme definiert ist,
* der Einsatzumfang begrenzt werden kann.

---

# 6. Tailoring nach Projektumfang

Die sechs CRISP-ML(Q)-Phasen bleiben immer bestehen. Der Umfang der Artefakte und Prüfungen wird jedoch angepasst.

## 6.1 Stufe A: Kompaktes Vorhaben

Geeignet für:

* internen PoC,
* begrenzten Pilot,
* wenige Nutzer,
* keine kritische Entscheidung,
* keine sensiblen Daten,
* vollständig reversiblen Einsatz.

### Mindestumfang

* ein gemeinsames Projektstatusblatt,
* kurze Problem- und Datenbeschreibung,
* definierte Baseline,
* Evaluationsset,
* dokumentierte Gate-Entscheidungen,
* ML Test Score als Bestandsaufnahme,
* Rollback- oder Deaktivierungsmöglichkeit.

Dokumente können in einem einzigen Projekt-Dokument gebündelt werden.

---

## 6.2 Stufe B: Standardvorhaben

Geeignet für:

* produktive Geschäftsanwendung,
* mehrere Nutzergruppen,
* Integration in operative Prozesse,
* wiederkehrende Nutzung,
* relevante Betriebs- oder Datenabhängigkeiten.

### Mindestumfang

* getrennte fachliche und technische Zieldefinition,
* Daten- und Systemdokumentation,
* versionierte Evaluation,
* Risiko- und Maßnahmenregister,
* dokumentierte Architekturentscheidungen,
* Release- und Rollback-Verfahren,
* Monitoring und Verantwortlichkeiten,
* regelmäßige ML-Test-Score-Bewertung.

---

## 6.3 Stufe C: Erweitertes Vorhaben

Geeignet für:

* geschäftskritische Prozesse,
* hohe Nutzer- oder Transaktionszahlen,
* personenbezogene oder besonders vertrauliche Daten,
* teilautomatisierte Entscheidungen mit erheblicher Wirkung,
* komplexe Integrationen,
* hohe regulatorische Anforderungen.

### Zusätzlicher Mindestumfang

* unabhängiges Review,
* formalisierte Risikoanalyse,
* explizite Sicherheits- und Datenschutzfreigabe,
* Last-, Recovery- und Penetrationstests,
* dokumentierte Human-Oversight-Regeln,
* Notfall- und Abschaltverfahren,
* regelmäßige Revalidierung,
* gegebenenfalls ergänzende Normen oder Branchenstandards.

---

# 7. Phase 1: Business and Data Understanding

## Ziel

Prüfen, ob ein relevantes Geschäftsproblem vorliegt und ob es mit verfügbaren Daten und geeigneter KI-Technologie sinnvoll bearbeitet werden kann.

CRISP-ML(Q) verbindet Business- und Datenverständnis bewusst in einer gemeinsamen Phase, weil Datenverfügbarkeit und Datenqualität die Machbarkeit und sogar die fachliche Zielsetzung beeinflussen können.

## Pflichtfragen

* Welches konkrete Problem wird gelöst?
* Welcher Prozess oder Prozessabschnitt ist betroffen?
* Wer nutzt das Ergebnis?
* Welche Entscheidung oder Tätigkeit wird unterstützt?
* Was ist die heutige Baseline?
* Welche Daten beziehungsweise Informationen werden benötigt?
* Sind diese Daten verfügbar und ausreichend?
* Welche Fehler wären besonders kritisch?
* Warum ist KI geeigneter als eine konventionelle Lösung?
* Welche Abbruchkriterien gelten?

## Erfolgskriterien

CRISP-ML(Q) unterscheidet drei aufeinander abzustimmende Ebenen:

### Business-Erfolg

Beispiele:

* reduzierte Durchlaufzeit,
* geringere Bearbeitungskosten,
* höhere Abschlussrate,
* weniger manuelle Nacharbeit,
* verbesserte Entscheidungsqualität.

### KI- beziehungsweise Systemerfolg

Beispiele:

* Genauigkeit,
* Vollständigkeit,
* Fehlerrate,
* Antwortzeit,
* Groundedness,
* Extraktionsqualität,
* Tool-Erfolgsrate.

### Wirtschaftlicher Erfolg

Beispiele:

* Kosteneinsparung,
* vermiedener Aufwand,
* zusätzlicher Umsatz,
* Return on Investment,
* Kosten pro Vorgang.

## Pflichtnachweise

* Problem- und Prozessbeschreibung
* abgegrenzter Use Case
* Nutzer und Stakeholder
* Ist-Baseline
* Datenquellenübersicht
* Machbarkeitsbewertung
* erste Risikoübersicht
* drei Ebenen der Erfolgskriterien
* Abbruchkriterien
* Tailoring-Stufe A, B oder C

## Quality Gate 1: Use-Case-Freigabe

### Muss-Kriterien

* Problem und Scope sind eindeutig.
* Ist-Baseline ist dokumentiert.
* Erfolgskriterien sind messbar.
* Datenverfügbarkeit ist grundsätzlich bestätigt.
* Verantwortlichkeiten sind benannt.
* wesentliche rechtliche und organisatorische Ausschlussgründe wurden geprüft.
* eine einfachere Nicht-KI-Lösung wurde betrachtet.

### Entscheidungen

* Go
* Conditional Go
* No-Go
* Rücksprung zur fachlichen Neuschärfung

---

# 8. Phase 2: Data Preparation

## Ziel

Einen reproduzierbaren, kontrollierbaren und für Entwicklung sowie Betrieb geeigneten Datenbestand herstellen.

## Pflichtaufgaben

* relevante Daten auswählen,
* Datenquellen und Verantwortliche dokumentieren,
* Datenqualität prüfen,
* Daten bereinigen,
* fehlende und widersprüchliche Werte behandeln,
* Daten transformieren,
* Merkmale beziehungsweise Eingabestrukturen erzeugen,
* Trainings-, Evaluations- und Produktionsdaten trennen,
* Datenschutz und Berechtigungen umsetzen,
* Datenstände versionieren,
* Verarbeitung automatisierbar gestalten.

## Pflichtnachweise

* Datenquellenkatalog
* Daten- oder Eingabeschema
* Datenqualitätsregeln
* Data Lineage
* Berechtigungsmodell
* Datenschutzbewertung
* dokumentierte Datenaufbereitung
* versionierter Entwicklungs- und Evaluationsbestand
* automatisierte oder manuell dokumentierte Datenprüfungen

## Relevante ML-Test-Score-Prüfungen

In dieser Phase werden insbesondere die Datenprüfungen vorbereitet:

* Erwartungen an Daten sind in einem Schema festgehalten.
* verwendete Eingaben liefern einen nachgewiesenen Nutzen.
* Kosten und Abhängigkeiten einzelner Eingaben sind vertretbar.
* fachliche und organisatorische Datenvorgaben werden eingehalten.
* Datenschutzkontrollen bestehen.
* neue Eingaben können kontrolliert ergänzt werden.
* Verarbeitungscode für Eingaben wird getestet.

## Quality Gate 2: Datenfreigabe

### Muss-Kriterien

* Daten können reproduzierbar bereitgestellt werden.
* Datenherkunft ist nachvollziehbar.
* wesentliche Qualitätsanforderungen sind definiert.
* unzulässige Eingaben werden erkannt.
* Berechtigungen sind umgesetzt.
* sensible Daten sind geschützt.
* Änderungen können versioniert und nachvollzogen werden.
* der Evaluationsbestand ist vom Entwicklungsbestand getrennt.

---

# 9. Phase 3: Modeling

## Ziel

Die einfachste Lösung entwickeln, die die definierten Erfolgskriterien nachweisbar erfüllt.

## Pflichtaufgaben

* einfache Baseline implementieren,
* geeignete Verfahren beziehungsweise Anbieter vergleichen,
* Modell- und Systemkonfiguration versionieren,
* Experimente nachvollziehbar dokumentieren,
* repräsentatives Evaluationsset verwenden,
* relevante Daten- und Nutzersegmente separat prüfen,
* Qualität, Kosten und Antwortzeit messen,
* Fehler analysieren,
* bekannte Grenzen dokumentieren.

## Pflichtnachweise

* Baseline-Lösung
* versionierte Modellspezifikation
* versionierte Konfiguration
* Evaluationsdatensatz
* Qualitätsmetriken
* Kosten- und Latenzmessung
* Lösungsvergleich
* Fehleranalyse
* dokumentierte Modell- und Systemgrenzen

## Relevante ML-Test-Score-Prüfungen

* Modellspezifikationen werden geprüft und versioniert.
* Offline-Metriken stehen in nachvollziehbarem Zusammenhang mit realen Auswirkungen.
* relevante Parameter und Konfigurationen wurden systematisch geprüft.
* Auswirkungen veralteter Modelle sind bekannt.
* eine einfachere Lösung ist nicht besser.
* Qualität ist auf wichtigen Daten- beziehungsweise Nutzersegmenten ausreichend.
* Auswirkungen auf unterschiedliche Personengruppen wurden betrachtet.

## Quality Gate 3: Modellierungsfreigabe

### Muss-Kriterien

* Mindestqualität ist erreicht.
* Baseline-Vergleich liegt vor.
* relevante Sonderfälle wurden geprüft.
* Kosten und Antwortzeiten sind grundsätzlich akzeptabel.
* Ergebnisse können reproduzierbar bewertet werden.
* Fehlerarten und Grenzen sind dokumentiert.
* Modell und Konfiguration sind versioniert.

---

# 10. Phase 4: Evaluation

## Ziel

Nachweisen, dass das vollständige KI-System im vorgesehenen Anwendungskontext fachlich, technisch und wirtschaftlich geeignet ist.

Evaluation betrifft nicht nur die Modellmetrik, sondern das Gesamtsystem und dessen Einbettung in den Geschäftsprozess.

## Pflichtprüfungen

* fachliche Akzeptanz,
* Business-Erfolgskriterien,
* KI- beziehungsweise Systemmetriken,
* wirtschaftliche Zielsetzung,
* Vergleich mit Ist-Baseline,
* End-to-End-Prozess,
* Fehler- und Ausnahmefälle,
* Robustheit,
* Datenschutz,
* Informationssicherheit,
* Zugriffssteuerung,
* relevante Nutzer- und Datensegmente,
* menschliche Kontrollmöglichkeit,
* Kosten unter realistischen Bedingungen,
* Deaktivierungs- und Fallback-Verhalten.

## Pflichtnachweise

* Evaluationsbericht
* versionierter Testfallkatalog
* gemessene Ergebnisse
* Abweichungs- und Fehlerliste
* aktualisiertes Risiko- und Maßnahmenregister
* fachliche Bewertung
* technische Bewertung
* dokumentierte Restrisiken
* Pilot- beziehungsweise Go-live-Empfehlung

## Quality Gate 4: Pilot- oder Release-Kandidatenfreigabe

### Muss-Kriterien

* alle projektspezifischen Mindestwerte sind erfüllt,
* kritische Risiken sind geschlossen,
* Restrisiken sind dokumentiert,
* der geplante Einsatzumfang entspricht der getesteten Lösung,
* ein menschliches Eingreifen ist möglich, sofern erforderlich,
* Fehler führen nicht zu unkontrolliertem Verhalten,
* die Betriebsanforderungen sind definiert.

---

# 11. Phase 5: Deployment

## Ziel

Das geprüfte System reproduzierbar, kontrolliert und rücksetzbar in die vorgesehene Umgebung überführen.

## Pflichtaufgaben

* Build- und Release-Prozess einrichten,
* Entwicklungs-, Test- und Produktionsumgebungen trennen,
* Konfigurationen und Secrets verwalten,
* Freigabeprüfungen automatisieren oder dokumentieren,
* End-to-End-Integration testen,
* begrenzten Rollout ermöglichen,
* Rollback oder Deaktivierung testen,
* Logging und Tracing bereitstellen,
* Monitoring und Alarmierung aktivieren,
* Betriebs- und Supportverantwortung festlegen,
* Nutzer informieren und gegebenenfalls schulen.

## Pflichtnachweise

* Release-Paket
* Deployment-Protokoll
* Integrationstest
* getestetes Rollback beziehungsweise Abschaltverfahren
* Betriebsdokumentation
* Runbook
* Monitoring-Dashboard
* Alarmierungsregeln
* Support- und Incident-Verantwortung
* freigegebene Produktivversion

## Relevante ML-Test-Score-Prüfungen

* Systemerzeugung ist reproduzierbar.
* Modell- beziehungsweise Systemkonfiguration wird getestet.
* vollständige Pipeline wird integrationstested.
* Qualität wird vor Veröffentlichung geprüft.
* Fehler können diagnostiziert werden.
* neue Versionen können begrenzt ausgerollt werden.
* vorherige Versionen können wiederhergestellt werden.

## Quality Gate 5: Go-live

### Muss-Kriterien

* freigegebene Version ist eindeutig identifizierbar,
* End-to-End-Test wurde bestanden,
* Release- und Rollback-Verfahren funktionieren,
* Logging und Monitoring sind aktiv,
* Alarmierungs- und Supportwege bestehen,
* Verantwortliche sind benannt,
* ML Test Score wurde aktuell erhoben,
* projektspezifische Mindestanforderungen an den Score wurden erfüllt,
* offene Abweichungen sind genehmigt und befristet.

---

# 12. Phase 6: Monitoring and Maintenance

## Ziel

Sicherstellen, dass die Anwendung auch nach der Veröffentlichung zuverlässig, wirtschaftlich und regelkonform bleibt.

## Fortlaufend zu überwachen

* Systemverfügbarkeit,
* Antwortzeiten,
* Fehlerquoten,
* Eingabe- und Datenqualität,
* fachliche Ergebnisqualität,
* Kosten und Ressourcenverbrauch,
* Nutzung und Akzeptanz,
* Unterschiede zwischen Test und Produktion,
* Alter von Modellen und Daten,
* externe Modell-, Provider- und API-Änderungen,
* Sicherheits- und Datenschutzereignisse,
* Nutzerkorrekturen,
* Eskalationen und Beschwerden.

## Pflichtprozesse

* Incident Management,
* Change Management,
* Regressionstests,
* regelmäßige Qualitätsbewertung,
* Aktualisierung der Evaluationsdaten,
* Revalidierung nach relevanten Änderungen,
* Rollback oder Deaktivierung,
* Austausch von Modell oder Anbieter,
* geordneter Rückbau am Lebenszyklusende.

## Relevante ML-Test-Score-Prüfungen

* Änderungen relevanter Abhängigkeiten werden erkannt.
* Datenanforderungen werden im Betrieb eingehalten.
* Entwicklungs- und Produktionsverarbeitung weichen nicht unkontrolliert voneinander ab.
* Modelle und Daten sind nicht unzulässig veraltet.
* Ausgaben bleiben technisch stabil.
* Rechenleistung, Antwortzeiten und Ressourcenverbrauch verschlechtern sich nicht unkontrolliert.
* fachliche Ergebnisqualität wird überwacht.

## Quality Gate 6: Fortgesetzte Betriebsfreigabe

### Muss-Kriterien

* Betriebs- und Qualitätsmetriken liegen innerhalb der vereinbarten Grenzen,
* kritische Vorfälle wurden behandelt,
* Änderungen sind kontrolliert durchgeführt,
* notwendige Regressionstests sind bestanden,
* Verantwortlichkeiten bestehen weiterhin,
* ML Test Score wurde nach wesentlichen Änderungen aktualisiert.

### Mögliche Entscheidungen

* Weiterbetrieb
* Weiterbetrieb mit Auflagen
* begrenzter Betrieb
* Rollback
* temporäre Deaktivierung
* vollständige Stilllegung

---

# 13. ML Test Score

## 13.1 Zweck

Der ML Test Score ist eine Rubrik zur Bewertung von:

* technischer Produktionsreife,
* Testabdeckung,
* Monitoring,
* technischer Schuld.

Er ersetzt nicht:

* fachliche Abnahme,
* Business-Case-Bewertung,
* Datenschutzprüfung,
* Security Review,
* regulatorische Prüfung,
* allgemeine Softwaretests.

Das Originalpaper betont ausdrücklich, dass die Rubrik ML-spezifische Probleme behandelt und allgemeine Software-Engineering-Praktiken weiterhin zusätzlich erforderlich sind.

---

## 13.2 Die vier Kategorien

### A. Daten

1. Erwartungen an Eingaben sind in einem Schema dokumentiert.
2. Alle verwendeten Eingaben liefern einen nachgewiesenen Nutzen.
3. Keine Eingabe verursacht unverhältnismäßige Kosten oder Abhängigkeiten.
4. Eingaben erfüllen fachliche und organisatorische Vorgaben.
5. Die Datenpipeline besitzt angemessene Datenschutzkontrollen.
6. Neue Eingaben können kontrolliert ergänzt werden.
7. Verarbeitungscode für Eingaben wird getestet.

### B. Modell

1. Modellspezifikationen werden geprüft und versioniert.
2. Offline-Metriken stehen in Bezug zu realen Auswirkungen.
3. relevante Parameter wurden systematisch untersucht.
4. Auswirkungen veralteter Modelle sind bekannt.
5. eine einfachere Lösung ist nicht besser.
6. Qualität ist auf wichtigen Datensegmenten ausreichend.
7. Auswirkungen auf unterschiedliche Nutzer- oder Personengruppen wurden geprüft.

### C. Infrastruktur

1. System- beziehungsweise Modellerzeugung ist reproduzierbar.
2. Modellspezifikationen und Konfigurationen werden getestet.
3. die vollständige Pipeline wird integrationstested.
4. Qualität wird vor Veröffentlichung geprüft.
5. Fehler können diagnostiziert werden.
6. neue Versionen können begrenzt ausgerollt werden.
7. frühere Versionen können wiederhergestellt werden.

### D. Monitoring

1. Änderungen abhängiger Systeme oder Datenquellen werden erkannt.
2. Eingabe- und Datenregeln werden im Betrieb geprüft.
3. Entwicklungs- und Produktionsverarbeitung bleiben konsistent.
4. Modelle und Datenbestände werden auf Veralterung überwacht.
5. Modellausgaben bleiben technisch stabil.
6. Latenz, Durchsatz und Ressourcenverbrauch verschlechtern sich nicht unkontrolliert.
7. fachliche Ergebnisqualität wird überwacht.

Die Liste ist eine deutschsprachige, sinngemäße Arbeitsfassung der 28 Prüfungen und keine autorisierte Übersetzung des Google-Papers. Das Original enthält 28 Prüfungen in vier Bereichen.

---

# 14. Berechnung des ML Test Score

Jede Prüfung wird bewertet mit:

|    Wert | Bedeutung                                                                 |
| ------: | ------------------------------------------------------------------------- |
|   **0** | Prüfung wird nicht durchgeführt                                           |
| **0,5** | Prüfung wird manuell durchgeführt; Ergebnis ist dokumentiert und verteilt |
| **1,0** | Prüfung wird automatisiert und wiederkehrend durchgeführt                 |

Danach:

1. Punkte je Kategorie addieren.
2. Niedrigsten Kategoriewert bestimmen.
3. Dieser niedrigste Wert ist der finale ML Test Score.

[
\text{ML Test Score}
====================

\min(
\text{Daten},
\text{Modell},
\text{Infrastruktur},
\text{Monitoring}
)
]

Dieses Berechnungsverfahren stammt direkt aus dem Originalpaper.

---

# 15. Interpretation des ML Test Score

Die folgende Interpretation entspricht der im Originalpaper veröffentlichten Orientierung:

|              Score | Interpretation                                                                      |
| -----------------: | ----------------------------------------------------------------------------------- |
|              **0** | eher Forschungsprojekt als produktiviertes System                                   |
| **größer 0 bis 1** | nicht vollständig ungetestet, aber möglicherweise erhebliche Zuverlässigkeitslücken |
| **größer 1 bis 2** | erste grundlegende Produktivierung, weiterer Investitionsbedarf wahrscheinlich      |
| **größer 2 bis 3** | angemessen getestet, weitere Automatisierung möglich                                |
| **größer 3 bis 5** | hoher Grad an automatisierten Tests und Monitoring                                  |
|       **größer 5** | außergewöhnlich hoher Grad an automatisierten Tests und Monitoring                  |

Die Autoren weisen darauf hin, dass Systeme je nach Entwicklungsstand sinnvollerweise unterschiedliche Werte anstreben können. Die Interpretation wurde anhand interner ML-Systeme kalibriert, stellt aber keine universelle Zertifizierungsschwelle dar.

## Verbindliche Regel für dieses Vorgehensmodell

Es gibt **keine allgemeingültigen festen Grenzwerte** für:

* PoC,
* Pilot,
* Produktivbetrieb,
* geschäftskritische Systeme.

Stattdessen wird in Phase 1 projektspezifisch festgelegt:

* welcher Mindestscore vor Pilotstart erwartet wird,
* welcher Mindestscore für den Go-live erforderlich ist,
* welche Einzelprüfungen unabhängig vom Gesamtscore zwingend erfüllt sein müssen.

Diese Grenzwerte sind **projektspezifische Governance-Entscheidungen** und nicht Bestandteil des Google-Standards.

---

# 16. Projektspezifische Score-Festlegung

## Pflichtverfahren

Vor Beginn der Umsetzung werden festgelegt:

| Einsatzstufe        | Projektspezifischer Mindestscore | Zwingende Einzelprüfungen |
| ------------------- | -------------------------------: | ------------------------- |
| PoC                 |                                  |                           |
| Pilot               |                                  |                           |
| Produktivbetrieb    |                                  |                           |
| erweiterter Betrieb |                                  |                           |

## Festlegungskriterien

Der Zielwert wird bestimmt anhand von:

* Auswirkung eines Fehlers,
* Anzahl und Art der Nutzer,
* Reversibilität,
* Datenkritikalität,
* Automatisierungsgrad,
* Abhängigkeit operativer Prozesse,
* regulatorischen Anforderungen,
* Kosten eines Ausfalls,
* Möglichkeit menschlicher Kontrolle.

## Schutz vor Score-Gaming

Ein ausreichender Gesamtscore erlaubt keinen Go-live, wenn eine zwingende Einzelprüfung fehlt.

Beispiele für mögliche zwingende Prüfungen:

* Rollback funktioniert,
* Produktionsdaten werden validiert,
* Datenschutzkontrollen sind umgesetzt,
* fachliche Qualität wird überwacht,
* relevante Konfigurationen sind versioniert,
* kritische Ausgaben können nachvollzogen werden.

---

# 17. Übertragung auf generative KI

## Status dieser Übertragung

Die folgenden Zuordnungen sind eine **operative Heuristik dieses Dokuments**.

Sie sind:

* plausibel,
* praktisch nutzbar,
* aus den ursprünglichen ML-Konzepten abgeleitet,

aber:

* nicht Bestandteil von CRISP-ML(Q),
* nicht Bestandteil des Google ML Test Score,
* nicht als LLM- oder Agentenstandard validiert.

## Arbeitszuordnung

| Klassischer ML-Begriff | Mögliche GenAI-Operationalisierung                                                     |
| ---------------------- | -------------------------------------------------------------------------------------- |
| Feature                | Eingabe, Dokument, Metadatum, Retrieval-Ergebnis oder Tool-Ausgabe                     |
| Modellspezifikation    | Modellversion, Systemanweisung, Parameter, Routing-, Retrieval- und Tool-Konfiguration |
| Trainingsdaten         | Fine-Tuning-Daten, Referenzbeispiele oder kuratierte Evaluationsdaten                  |
| Offline-Metrik         | Ergebnis auf einem versionierten Test- oder Evaluationsset                             |
| Online-Metrik          | Aufgabenerfolg, Nutzerkorrekturen, Eskalationen, Prozesszeit oder Business-KPI         |
| Training-Serving Skew  | Unterschied zwischen Test- und Produktivkonfiguration                                  |
| Modellalter            | Alter von Modell, Prompt, Index, Dokumentenbestand, API oder Tool                      |
| Prediction Quality     | fachliche Korrektheit, Vollständigkeit und Regelkonformität der Ausgabe                |

---

# 18. Zusätzliche GenAI-Prüfungen

Diese Prüfungen ergänzen den ML Test Score, verändern aber nicht dessen offiziellen Score.

## 18.1 Modell- und Antwortverhalten

* unbelegte Aussagen werden erkannt oder begrenzt,
* Antworten sind bei wissensbasierten Aufgaben auf Quellen zurückführbar,
* relevante Informationen werden nicht ausgelassen,
* das System hält definierte Ausgabeformate ein,
* Unsicherheit wird angemessen behandelt,
* Ablehnungen und Fallbacks funktionieren.

## 18.2 RAG

* relevante Dokumente werden gefunden,
* nicht relevante Dokumente beeinflussen die Antwort nicht unzulässig,
* Berechtigungen gelten auch für Retrieval-Ergebnisse,
* Dokumentänderungen werden zeitnah übernommen,
* gelöschte Dokumente verschwinden aus dem Index,
* Antwort und Quellen stehen in nachvollziehbarem Zusammenhang.

## 18.3 Sicherheit

* Prompt Injection wird geprüft,
* unzulässige Systemanweisungen werden nicht offengelegt,
* vertrauliche Daten werden nicht an unberechtigte Nutzer ausgegeben,
* Tool-Aufrufe sind auf erlaubte Aktionen beschränkt,
* externe Inhalte können keine unkontrollierten Aktionen auslösen.

## 18.4 Agentische Systeme

* erlaubte Ziele und Aktionen sind begrenzt,
* jeder Tool-Aufruf ist nachvollziehbar,
* risikoreiche Aktionen benötigen eine Freigabe,
* Schleifen und unkontrollierter Ressourcenverbrauch werden verhindert,
* Abbruch- und Eskalationsregeln bestehen,
* Agentenentscheidungen werden protokolliert,
* deterministische Schritte werden nicht unnötig dem Modell überlassen.

## 18.5 Human Oversight

* Freigabepunkte sind eindeutig,
* Nutzer erkennen, wann KI beteiligt ist,
* kritische Entscheidungen können korrigiert werden,
* Eskalationswege sind bekannt,
* menschliche Prüfer erhalten ausreichend Kontext.

---

# 19. Sicherheitskritische und besonders regulierte Systeme

## Ausschlussregel

Wird ein System als sicherheitskritisch oder fachlich zertifizierungspflichtig eingestuft, darf dieses Vorgehensmodell nur als ergänzender ML-Arbeitsrahmen verwendet werden.

Vor weiterer Umsetzung ist festzulegen:

* welche Fachnorm gilt,
* welche unabhängige Assurance notwendig ist,
* welche Nachweise regulatorisch vorgeschrieben sind,
* wer die Sicherheitsverantwortung trägt,
* welches Freigabeorgan zuständig ist.

ISO/IEC 5338 definiert allgemeine Prozesse für den Lebenszyklus von KI-Systemen und kann für Definition, Steuerung, Entwicklung, Betrieb und Verbesserung eines KI-Systems herangezogen werden. Es ersetzt jedoch nicht automatisch domänenspezifische Sicherheits- oder Zertifizierungsanforderungen.

## Entscheidung

```text
Sicherheitskritisch oder zertifizierungspflichtig?
        │
        ├── Nein → Vorgehensmodell regulär anwenden
        │
        └── Ja  → Fachstandard und unabhängige Assurance
                  verbindlich ergänzen
```

---

# 20. Quality-Gate-Protokoll

Für jedes Gate wird folgendes Schema verwendet:

## Stammdaten

| Feld            | Inhalt |
| --------------- | ------ |
| Projekt         |        |
| Systemversion   |        |
| Phase           |        |
| Gate            |        |
| Bewertungsdatum |        |
| Gate Owner      |        |
| Business Owner  |        |
| Technical Owner |        |
| Data/AI Owner   |        |

## Entscheidung

| Feld                    | Inhalt                                   |
| ----------------------- | ---------------------------------------- |
| Entscheidung            | Go / Conditional Go / No-Go / Rücksprung |
| Begründung              |                                          |
| offene Abweichungen     |                                          |
| Restrisiken             |                                          |
| Kompensationsmaßnahmen  |                                          |
| Verantwortliche         |                                          |
| Fristen                 |                                          |
| Eskalation erforderlich | Ja / Nein                                |
| nächster Review-Termin  |                                          |

## Nachweise

| Kriterium | Status                            | Nachweis | Verantwortlicher |
| --------- | --------------------------------- | -------- | ---------------- |
|           | erfüllt / offen / nicht anwendbar |          |                  |

---

# 21. Projektstatusblatt

## Stammdaten

| Feld                             | Eintrag   |
| -------------------------------- | --------- |
| Projekt beziehungsweise Use Case |           |
| Tailoring-Stufe                  | A / B / C |
| Business Owner                   |           |
| Technical Owner                  |           |
| Data/AI Owner                    |           |
| aktuelle Phase                   |           |
| aktuelle Systemversion           |           |
| Bewertungsdatum                  |           |

## Zielgrößen

| Ebene              | Metrik | Baseline | Mindestwert | Zielwert | Ist-Wert |
| ------------------ | ------ | -------: | ----------: | -------: | -------: |
| Business           |        |          |             |          |          |
| KI/System          |        |          |             |          |          |
| Wirtschaftlichkeit |        |          |             |          |          |

## ML Test Score

| Kategorie                          | Score | offene Kernprüfungen |
| ---------------------------------- | ----: | -------------------- |
| Daten                              |       |                      |
| Modell                             |       |                      |
| Infrastruktur                      |       |                      |
| Monitoring                         |       |                      |
| **Gesamtscore – niedrigster Wert** |       |                      |

## Projektspezifische Zielwerte

| Einsatzstufe     | Mindestscore | zwingende Einzelprüfungen |
| ---------------- | -----------: | ------------------------- |
| Pilot            |              |                           |
| Produktivbetrieb |              |                           |

---

# 22. Anwendungsvorschrift

1. Use Case und Tailoring-Stufe bestimmen.
2. Business-, System- und Wirtschaftskriterien festlegen.
3. Projektspezifische Score-Ziele und zwingende Einzelprüfungen definieren.
4. Die sechs CRISP-ML(Q)-Phasen durchlaufen.
5. In jeder Phase Risiken, Qualitätsmaßnahmen und Nachweise dokumentieren.
6. Am Ende jeder Phase ein Quality Gate durchführen.
7. Den ML Test Score spätestens ab Data Preparation fortlaufend pflegen.
8. Komplexere Lösungen immer gegen eine einfache Baseline testen.
9. Kein Pilot oder Go-live ohne dokumentierte Gate-Entscheidung.
10. Kein Go-live allein aufgrund eines ausreichenden Gesamtscores.
11. Nach wesentlichen Änderungen Evaluation und Score aktualisieren.
12. Im Betrieb Qualität, Daten, Infrastruktur und Abhängigkeiten überwachen.
13. Bei kritischen Abweichungen Betrieb begrenzen, zurückrollen oder deaktivieren.
14. Sicherheitskritische Systeme an ein ergänzendes Fachverfahren übergeben.

---

# 23. Kurzform für Projektkommunikation

```text
1. Business and Data Understanding
   Lösen wir das richtige Problem mit geeigneten Daten?

2. Data Preparation
   Können Daten und Kontext zuverlässig bereitgestellt werden?

3. Modeling
   Ist die einfachste ausreichend gute Lösung gefunden?

4. Evaluation
   Erfüllt das Gesamtsystem die fachlichen, technischen
   und wirtschaftlichen Anforderungen?

5. Deployment
   Kann das System kontrolliert veröffentlicht,
   überwacht und zurückgerollt werden?

6. Monitoring and Maintenance
   Bleibt das System im Betrieb zuverlässig und relevant?
```

Über alle Phasen:

```text
Risiken identifizieren
        ↓
Qualitätsmaßnahmen definieren
        ↓
Nachweise erzeugen
        ↓
Quality Gate entscheiden
        ↓
ML Test Score aktualisieren
```

---

# 24. Abschließende Einordnung

Dieses Vorgehensmodell liefert:

* einen etablierten Entwicklungslebenszyklus,
* eine konkrete technische Prüfrubrik,
* verbindliche Quality Gates,
* klare Verantwortlichkeiten,
* eine Eskalationslogik,
* Anpassbarkeit an Projektgrößen,
* eine nachvollziehbare GenAI-Erweiterung.

Es garantiert keinen Projekterfolg.

Es reduziert jedoch das Risiko, dass:

* ein ungeeigneter Use Case umgesetzt wird,
* ein Prototyp ungeprüft produktiv geht,
* Daten- oder Modellprobleme unbemerkt bleiben,
* Qualitätsanforderungen erst am Ende betrachtet werden,
* Verantwortlichkeiten im Betrieb ungeklärt sind,
* technische Produktionsreife nur subjektiv behauptet wird.
