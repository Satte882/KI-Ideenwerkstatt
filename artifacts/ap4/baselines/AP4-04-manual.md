# AP4-04 – geführte Referenz

## Scope und Diagnose

- Problem: Rechnungsabweichungen werden teilweise deterministisch, teilweise durch manuelle Freitextauswertung geklärt.
- Prozessstart: Rechnung, Bestellung und Wareneingang liegen zur Prüfung vor.
- Prozessende: Sachbearbeitung entscheidet über Klärung, Buchung oder Rückgabe.
- Rollen: Sachbearbeitung; weitere Rollen nicht belegt.
- Daten/Systeme: Rechnungsnummer, Bestellnummer, Betrag, Lieferant, Bestellung, Wareneingang, Freitextnotizen.
- Regelpfad: formale Übereinstimmungen benötigen keine semantische Interpretation. [S1]
- Ausnahmebefund: R02, R03 und R05 haben `formal_match=false`, Freitextnotiz und `manual_review`; R01 und R04 sind Standardfälle. [S2]
- Bestätigter Kernbefund: Der belegte Engpass liegt im manuellen Zusammenfassen von Freitext bei formalen Abweichungen, nicht im Standardpfad.
- Unknown: Fallvolumen, Bearbeitungszeit, Systeme/Schnittstellen und fachliche Ausnahmegrenzen.

## Lösungsvergleich und Entscheidung

- Option 1: deterministische Prüfung unverändert lassen und Freitext manuell zusammenfassen.
- Option 2: ausschließlich regelbasierte Erweiterung für neue strukturierte Ausnahmegründe.
- Option 3: Hybrid-Workflow – deterministische Prüfung zuerst, begrenzte LLM-Zusammenfassung nur bei Freitextabweichungen, anschließend menschliche Entscheidung.
- Entscheidung: Option 3 als Pilotkandidat.
- Begründung: Der Fall trennt strukturierte Regeln und semantische Ausnahmebearbeitung explizit.
- Architecture Mode: LLM Workflow/Hybrid.
- Human Gate: Klärung, Buchung oder Rückgabe bleibt ausschließlich bei der Sachbearbeitung.

## Use Case, Governance und Pilot

- Use Case: Freitextabweichungen zusammenfassen und mit dem deterministischen Prüfergebnis vorlegen.
- Erwarteter Nutzen: weniger manuelle Zusammenfassungsarbeit; nicht quantifiziert.
- Baseline/Ziel: unbekannt.
- Pilot: nur R02/R03/R05-artige Abweichungsfälle; keine automatische Buchungsfreigabe.
- Messung: aktive Klärungszeit, Korrekturen an Zusammenfassung, unzulässige Freigabeversuche.
- Governance: Datenarten, Hosting und weitere Review-Fakten sind nicht vollständig belegt; vor Approval klären.
- Formale Freigaben: keine automatisch bestanden.

## Provenance

- S1: `01_invoice_process.md`
- S2: `02_exceptions.csv`, fünf Fälle; drei Abweichungsfälle mit Freitext und manueller Prüfung.
- Keine Ursache, Baseline oder Zielzahl wurde als Fakt erfunden.
