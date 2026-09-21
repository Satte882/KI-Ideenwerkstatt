# PR A – Scope und Herkunft

## Ausgangspunkt

PR #7 (`feature/strategy-evidence-benefit-loop`) wurde bewusst geschlossen und nicht gemergt. Er vermischte Strategie-, Bewertungs-, Benefit- und Portfoliofunktionen und verwendete Confidence teilweise als frei gesetztes Feld sowie neue Anforderungen nur als Prüfhinweise.

PR A beginnt deshalb neu auf `main`.

## Selektiv übernommene Ideen aus PR #7

- versionierte strukturierte Bewertung
- getrennte Begründung und Evidenz
- eigenständige Ansicht für Bewertung und Entscheidung

Die Implementierung wurde jedoch fachlich neu aufgebaut:

- Confidence wird deterministisch hergeleitet
- positive Entscheidungen besitzen echte serverseitige Sperren
- Bewertung und Entscheidung sind personell getrennt
- Auflagenfreigaben benötigen eine zweite unabhängige Bestätigung

## Demo-Daten

Es gibt keine Datenmigration oder Kompatibilitätslogik für vorhandene Demo-Use-Cases. Für eine saubere lokale Abnahme wird die Entwicklungsdatenbank zurückgesetzt oder der vorhandene Befehl `python manage.py clear_demo_data` verwendet. Danach werden nur benötigte Nutzer, Rollen und Organisationseinheiten neu angelegt.

Der bestehende optionale Demo-Seed bleibt technisch erhalten, ist aber keine fachliche Abnahmegrundlage für PR A.

## Nicht enthalten

- Strategieziele und Strategieaggregation
- Benefit-Messhistorie und Forecast-vs.-Actual
- Portfolio-Ranking oder Kalibrierung
- Delivery-Handover
- semantische Duplikatserkennung
- Multi-Tenancy
