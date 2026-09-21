# VS1 Baseline – manueller/assistierter Untersuchungsweg

Issue: #2  
Baseline-Commit: `3dc648111087956fe8f6a3c2da6a17876b0685dd`  
Erfasst vor Änderungen an produktiven Pfaden für VS1/1.

## Zweck

Diese Baseline hält den bestehenden Weg fest, bevor der begrenzte Quellenraum und die reproduzierbaren Untersuchungswerkzeuge implementiert werden. Sie ist kein Wirksamkeitsnachweis und enthält keine nachträglich auf das neue Ergebnis zugeschnittenen Vergleichsschritte.

## Neutraler Startzustand

- bestehender, bearbeitbarer `ProcessAnalysis`-Entwurf;
- Business Owner als kanonischer fachlicher Nutzer;
- Problem-/Entscheidungsfrage noch ohne vorentschiedene Diagnose oder Lösungsoption;
- Quellen liegen außerhalb der Anwendung und müssen vom Nutzer mit externen Werkzeugen gelesen bzw. ausgewertet werden;
- vorhandene ProcessAnalysis-Felder tragen Ablauf, Rollen/Systeme, Beobachtungen/Ursachen und Baseline, aber keinen eingebauten Fallordner-Reader und keine reproduzierbaren CSV-Auswertungswerkzeuge.

## Zugängliche Schritte im heutigen Produkt

1. Nutzer öffnet bzw. bearbeitet die Prozessanalyse.
2. Externe TXT/MD/CSV-Quellen werden außerhalb der Anwendung gesucht und gelesen.
3. Relevante Aussagen oder Kennzahlen werden manuell identifiziert.
4. CSV-Auswertungen müssen mit einem separaten Tabellen-/Analysewerkzeug durchgeführt werden.
5. Ergebnisse werden fachlich in die bestehenden ProcessAnalysis-Felder oder nachgelagerte Artefakte übertragen.
6. Herkunft und Berechnungsschritte sind nur soweit reproduzierbar, wie sie separat dokumentiert wurden.

## Artefakte der Baseline

- `ProcessAnalysis` und vorhandene Provenance-/Validierungsobjekte;
- externe Quelldateien außerhalb des Produktdatenmodells;
- gegebenenfalls manuell erzeugte Tabellen-/Analyseergebnisse;
- keine persistenten Source-IDs, kein unveränderlicher Quellen-Snapshot und keine eingebauten `list/search/read/profile/compare`-Werkzeugresultate.

## Messgrenzen

- **Keine menschliche Bearbeitungszeit wurde in dieser Session gemessen.**
- Ein später gemessener Human-Work-Wert muss als eigene Messung protokolliert werden und darf nicht rückwirkend als heutige Messung ausgegeben werden.
- Quellen-Erstellungsaufwand, Source-Pack-Vorbereitung und vorbereiteter Kontext sind im späteren A/B/C-Benchmark separat sichtbar zu halten.
- Technische Laufzeiten aus automatisierten Tests sind kein Ersatz für menschliche Bearbeitungszeit.

## Vergleichsregel für VS1

Der Vergleich darf diese Baseline nicht nach Kenntnis der Ergebnisse von VS1/1–VS1/3 verengen. Der neue Pfad muss insbesondere zusätzlichen Quellen-/Tooling-Aufwand, Korrekturen, fachliche Qualität, Laufzeit und Providerkosten getrennt ausweisen.
