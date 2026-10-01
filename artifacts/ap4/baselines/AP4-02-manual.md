# AP4-02 – geführte Referenz

## Scope und Diagnose

- Problem: Spesenprüfungen erzeugen manuellen Aufwand.
- Prozessstart: Spesenfall mit Kostenart, Betrag und gegebenenfalls Beleg liegt vor.
- Prozessende: Fall ist formal verarbeitet oder zur manuellen Prüfung markiert.
- Rollen: einreichende Person und manuelle Prüfstelle; weitere Rollen nicht belegt.
- Regeln: Beleg vorhanden und Betrag innerhalb veröffentlichter Kostenart-Grenze → formal verarbeiten; sonst manuelle Prüfung. [S1]
- CSV-Befund: E02, E03 und E06 benötigen nach genau diesen Regeln manuelle Prüfung; E01, E04 und E05 nicht. [S2]
- Bestätigter Kernbefund: Die Entscheidung ist durch stabile tabellarische Regeln vollständig deterministisch beschrieben.
- Unknown: heutige Bearbeitungszeit und Fallvolumen.

## Lösungsvergleich und Entscheidung

- Option 1: regelbasierte automatische Vorprüfung mit Übergabe der Ausnahmen an Menschen.
- Option 2: manuelle Prüfung beibehalten.
- Entscheidung: Option 1.
- Begründung: Die vorhandenen Daten und Richtlinien tragen eine deterministische Entscheidung; semantisches Reasoning ist nicht erforderlich.
- AI-/Non-AI-Zweig: Non-AI/Rule Automation; kein KI-Use-Case.
- Human Gate: Richtlinienänderungen und Ausnahmeentscheidungen bleiben menschlich autorisiert.

## Messung

- Baseline: unbekannt; keine Bearbeitungszeit in den Quellen.
- Pilot: Regeln gegen einen abgegrenzten Satz neuer Spesenfälle ausführen.
- Messung: Regelübereinstimmung, Anteil automatisch vorgeprüfter Fälle, manuelle Korrekturen.
- Abbruch: Regelabweichung oder nicht nachvollziehbare Ausnahmezuordnung.

## Provenance

- S1: `01_policy.md`
- S2: `02_cases.csv`, sechs Fälle, davon drei `manual_review=true`.
- Keine unbelegte Zeit-, Kosten- oder Qualitätszahl wurde ergänzt.
