# ADR 0006: Process Mining bleibt eine externe Analysemethode

## Status
Akzeptiert

## Kontext

KI-Radar unterstützt die Auswahl eines relevanten Value Streams, den Prozess-Deep-Dive, die Dokumentation von Bottlenecks und Baseline-Kennzahlen sowie den Vergleich organisatorischer, klassischer und KI-gestützter Lösungsoptionen.

Es wurde geprüft, Process Mining als zusätzliche Produktfunktion zu ergänzen. Ein minimaler Ansatz hätte im Wesentlichen nur dokumentiert, ob Process Mining für einen Prozess geeignet sein könnte. Ein weitergehender Ansatz mit Event-Log-Import, Konnektoren, Process Discovery, Variantenanalyse oder Conformance Checking würde dagegen einen eigenständigen großen Produktbereich eröffnen.

Die bestehende Prozessanalyse kann Ergebnisse externer datenbasierter Analysen bereits aufnehmen. Die Prozessvalidierung kann dazu einen externen Nachweis verlinken. Ein zusätzlicher Readiness-, Befund- oder Bestätigungsworkflow würde diese vorhandenen Strukturen teilweise duplizieren und zusätzlichen Pflegeaufwand erzeugen, ohne aktuell einen ausreichenden Produktmehrwert zu belegen.

## Entscheidung

Process Mining wird nicht als eigene Funktion in KI-Radar umgesetzt.

Insbesondere werden nicht eingeführt:

- Process-Mining-Readiness-Assessment oder zusätzliche Readiness-Felder,
- Speicherung oder Import von Event Logs,
- CSV- oder XES-Import für Process Mining,
- Konnektoren zu ERP-, CRM- oder Process-Mining-Plattformen,
- Process Discovery, Variantenanalyse oder Conformance Checking,
- eigene Befund-, Confidence- oder Bestätigungsworkflows,
- kontinuierliches Prozessmonitoring oder operative Prozessautomatisierung.

Process Mining bleibt eine externe Analysemethode, vergleichbar mit BPMN-Modellierung, Wertstromanalyse, Interviews oder BI-Auswertungen.

Ergebnisse aus Celonis, SAP Signavio, UiPath, Apromore, PM4Py, SQL, BI oder vergleichbaren Werkzeugen können weiterhin in die bestehenden Felder der Prozessanalyse einfließen. Ein externer Bericht oder Analysenachweis kann über die bestehende Prozessvalidierung referenziert werden.

## Begründung

- Ein reiner Eignungscheck liefert keinen ausreichenden Mehrwert gegenüber der bestehenden Prozessanalyse.
- Ein funktional relevanter Ausbau würde einen zweiten großen Produktbereich mit hohem Integrations-, Betriebs- und Pflegeaufwand schaffen.
- Bestehende Prozessanalyse-, Befund- und Validierungsstrukturen reichen aus, um externe Erkenntnisse entscheidungsrelevant zu dokumentieren.
- Es liegt derzeit kein mehrfach bestätigter Nutzerbedarf für Import, Integration oder eigene Mining-Funktionen vor.
- Die Entscheidung hält den Produktkern auf Business Architecture, Use-Case-Auswahl, Decision Governance und Delivery Readiness fokussiert.

## Konsequenzen

- Es werden keine GitHub-Issues oder Roadmap-Blöcke für Process-Mining-Funktionen angelegt.
- Externe Process-Mining-Aktivitäten verbleiben in spezialisierten Werkzeugen und Projekten.
- KI-Radar speichert nur die daraus abgeleiteten fachlichen Prozessinformationen und Evidenzverweise innerhalb der vorhandenen Strukturen.
- Der bestehende Golden Path und die Accelerator-Roadmap bleiben unverändert.

## Neubewertung

Die Entscheidung wird nur neu bewertet, wenn mehrere reale Nutzer- oder Kundenfälle einen konkreten, wiederkehrenden Bedarf belegen, der mit den bestehenden Prozessanalyse- und Evidenzfunktionen nicht ausreichend abgedeckt werden kann.

Eine Neubewertung muss mindestens klären:

- welcher konkrete Arbeitsaufwand oder Medienbruch beseitigt werden soll,
- warum ein Link oder die Übernahme bestätigter Ergebnisse nicht ausreicht,
- welche minimale Funktion einen messbaren Mehrwert erzeugt,
- wie Event-Daten, Datenschutz, Berechtigungen und Betrieb beherrscht werden,
- ob der erwartete Nutzen den dauerhaften Produkt- und Wartungsaufwand rechtfertigt.
