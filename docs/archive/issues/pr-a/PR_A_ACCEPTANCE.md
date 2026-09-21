# PR A – Fachliche Abnahme

## Geführte Aufnahme

- Eine fachlich verantwortliche Person kann einen Use Case in fünf kurzen Schritten erfassen.
- Problemformulierungen, die nur eine Technologie nennen, werden mit einem Plausibilitätshinweis abgewiesen.
- Baseline und Ziel müssen zur Optimierungsrichtung passen.
- Die Vorprüfung zeigt die vollständigen Angaben und den Status `Bereit zur Bewertung`.

## Bewertung

- Nur berechtigte KI-Koordinatoren können eine Bewertung anlegen.
- Bewertungen werden fortlaufend versioniert.
- Confidence wird aus Evidenzqualität, Aktualität, Abdeckung, unabhängiger Prüfung und geklärten Annahmen hergeleitet.
- Eine neue Bewertung setzt eine frühere Freigabe zurück auf `Bereit zur Bewertung`.

## Verbindliche Entscheidung

- Bewertende und entscheidende Person müssen verschieden sein.
- Die fachlich verantwortliche Person darf den eigenen Use Case nicht freigeben.
- Niedrige Confidence, niedrige technische Machbarkeit, niedrige Datenreife und hohes Risiko blockieren positive Entscheidungen.
- Offene Pflichtprüfungen und eine fehlende Governance-Bestätigung blockieren positive Entscheidungen.
- `Freigegeben mit Auflagen` benötigt Auflage, Verantwortung, Frist und eine zweite unabhängige Bestätigung.
- Der Entscheidungsstatus wird bei einer Auflagenfreigabe erst nach dieser zweiten Bestätigung geändert.

## Lifecycle-Kopplung

- Ein Wechsel in `Pilot` oder `Betrieb` ist ohne positive Freigabeentscheidung serverseitig blockiert.
- Die bisherigen Lifecycle-, Governance-, Metrik- und Go-live-Prüfungen bleiben zusätzlich aktiv.

## Technische Abnahme

Die reguläre Pull-Request-Pipeline prüft Linting, Formatierung, Django-Systemcheck, Migrationsparität und -anwendung, fachliche Tests, Security-Scan, Abhängigkeiten, Compose-Konfigurationen sowie Produktions- und Entwicklungsbuild.

## Bewusste Abgrenzung

Nicht Bestandteil von PR A sind Duplikatsprüfung, Benefit-Kalibrierungsloop, Portfolio-Auswertung, Strategieaggregation, Delivery-Handover und Multi-Tenancy.
