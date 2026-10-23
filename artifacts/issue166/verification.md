# Issue #166: Rollenrichtiger Prüfungsstart

Basis: `main` / `9b342287738561716fb2d9d0e1da685abf4d75ae`, synchronisiert am 23.10.2026.

## Verhalten

- Beide Erzeugungsrouten speichern weiterhin `IDEA/READY`. Die Aufnahme erzeugt weder eine Review-Entscheidung noch eine Bewertung oder Freigabe.
- Business Owner und Leser sehen den ausstehenden Prüfungsstart ohne unzulässigen Aktionslink. Die KI-Koordination erhält **Prüfung starten** im bestehenden Review-Formular und Arbeitsvorrat.
- Erst der dokumentierte `start_review` über den unveränderten kanonischen Service erzeugt `REVIEW` samt Review und technischer Historie. Anschließend ist **Bewertung anlegen** ausführbar.
- `READY` bleibt Entscheidungsreife; die Anzeige behauptet bei `IDEA/READY` keine bereits ausführbare Bewertung. Review-Formular, lokale Navigation und Lifecycle-Kontext benennen den Prüfungsstart.
- Transition-Policy, Berechtigungen, bestehende Bewertungs-/Freigabe-Services, Governance-Gates, Outcome-Vertrag und Herkunftssnapshots bleiben unverändert. Keine Migration und keine rückwirkende Statuskorrektur.
- Die zentrale bestehende Rollenvererbung behandelt technische Administratoren als Koordinatoren; diese Berechtigung bleibt erhalten und ist ausdrücklich getestet. Business Owner mit zusätzlicher Koordinatorrolle dürfen die Prüfung starten und bewerten, aber weiterhin nicht ihre eigene positive Bewertung freigeben.

## PostgreSQL und Qualitätsprüfungen

Isolierte PostgreSQL-17.5-Datenbanken; Python 3.13.5, Django 5.2.17. Kein SQLite-Ersatz. Keine echten LLM-Aufrufe.

| Prüfung | Ergebnis |
| --- | --- |
| Gesamtsuite `pytest -q` | **2463 passed**, 476 bestehende Warnungen, 864,40 s; Coverage 83 % |
| Abschließende Journey-Regression `pytest -q --no-cov` | **62 passed**, 31 Warnungen, 105,02 s |
| Ruff Lint / Format | Grün; 604 Python-Dateien formatiert |
| Django System Check | Keine Probleme |
| `makemigrations --check --dry-run` | Keine Änderungen |
| `uv lock --check` | Grün |
| Bandit | Keine Findings; bestehende `nosec`-Hinweise |
| Dependency Audit mit den unveränderten expliziten CI-Waivern | Keine bekannten Schwachstellen |

Vollständige Ausgaben: [PostgreSQL-Gesamtsuite](postgres-regression.txt), [abschließende Journey-Regression](journey-regression.txt).

Die abschließende Journey-Regression umfasst:

```text
tests/test_issue_166_review_start.py
tests/test_guided_journey.py
tests/test_issue_59_status_dimensions.py
tests/test_guided_workflow_ux.py
tests/test_issue_52_65_handover_decision_ux.py
tests/test_issue_58_final_journey_order.py
tests/test_delivery_handover.py
tests/test_outcome_journey_consistency.py
```

Die neuen Akzeptanztests durchlaufen die fünf Intake-POSTs und die abschließende Anlage beziehungsweise den bestehenden menschlichen Lösungsentscheid und Handoff. Sie verwenden keine Status- oder Assessment-Fixtures für den geprüften Pfad. Review und Bewertung werden über echte HTTP-POSTs gespeichert. Geprüft werden außerdem Historien-Actor, erneuter Prüfungsstart ohne zweite Entscheidung, direkte GET-/POST-Bewertung aus `IDEA`, Rollen ohne Berechtigung, fehlender Intake mit zulässiger Korrektur, bestehendes `REVIEW`, Mehrfachrollen, unveränderte Auswahl-Snapshots sowie Outcome-, Governance- und Selbstfreigabe-Gates.

Ältere Tests für bereits bewertete oder freigegebene Fälle setzen nun den dafür erforderlichen `REVIEW`-Status statt künstlich `IDEA`. Ihre Governance-, Priorisierungs- und Delivery-Erwartungen bleiben erhalten.

## Echte Desktop-Browserprüfung

Headed Chromium über Playwright gegen einen lokalen Django-Server und eine isolierte PostgreSQL-Datenbank. Desktop-Viewports ausschließlich **1440×1000** und **1024×1000**, kein Geräteprofil, keine Tablet-/Mobile-UI-Änderungen, keine CSS-Änderungen.

- Business Owner durchläuft den vollständigen direkten Intake in der Oberfläche. Erfolgsmeldung und Detailseite nennen die Übergabe zur Prüfung. Kein Link zum Prüfungsstart oder zur Bewertung für diese Rolle.
- KI-Koordinator öffnet **Prüfung starten**, bestätigt den bestehenden Review und erreicht anschließend die Bewertungsmaske. Dasselbe ist für den aus einer gewählten KI-Lösung erzeugten Use Case geprüft. Die Herkunft wurde über die bestehenden menschlichen Auswahl-/Bestätigungsservices vorbereitet.
- Beide Pfade speichern eine strukturierte Bewertung mit positiver Empfehlung auf ausdrücklich synthetischer Annahmenbasis. Der Entscheidungsstatus bleibt `READY`; es entsteht keine ApprovalDecision. Outcome-/Governance-Blocker bleiben sichtbar.
- Der primäre Prüfungsstart ist über einen echten Link und Tastaturfokus/Enter erreichbar. Bei beiden Breiten wurde `document.documentElement.scrollWidth <= innerWidth` geprüft. Screenshots wurden visuell kontrolliert; keine abgeschnittene Primäraktion oder horizontaler Seitenüberlauf.
- Im unveränderten Assessment-Template blockiert die bestehende CSP ein vorhandenes Inline-Script zur dynamischen Nachweis-Pflichtanzeige. Die regulären Formulare lassen sich dennoch speichern; serverseitige Validierung und CSP wurden nicht geändert oder umgangen.

| Zustand | 1440×1000 | 1024×1000 |
| --- | --- | --- |
| Owner: Prüfungsstart ausstehend | [Screenshot](owner-pending-1440.png) | [Screenshot](owner-pending-1024.png) |
| Koordination: Prüfung starten | [Screenshot](coordinator-start-1440.png) | [Screenshot](coordinator-start-1024.png) |
| Bestehendes Review-Formular | [Screenshot](review-form-1440.png) | [Screenshot](review-form-1024.png) |
| Nach Review: Bewertung anlegen | [Screenshot](reviewed-assessment-1440.png) | [Screenshot](reviewed-assessment-1024.png) |
| Positive Bewertung ohne Freigabe | [Screenshot](assessed-not-approved-1440.png) | [Screenshot](assessed-not-approved-1024.png) |
| Lösungshandoff: Prüfung starten | [Screenshot](selected-solution-start-1440.png) | [Screenshot](selected-solution-start-1024.png) |
| Lösungshandoff nach Review | [Screenshot](selected-solution-reviewed-1440.png) | [Screenshot](selected-solution-reviewed-1024.png) |

Die Screenshots zeigen ausschließlich synthetische lokale Testdaten. GitHub-CI und Draft-Status werden im PR nachgewiesen; kein Merge.
