# AP4-03 – geführte Referenz

## Scope und Diagnose

- Problem: Freitextanfragen benötigen manuelle Klassifikation und Entwurfsvorbereitung.
- Prozessstart: Kundenanfrage trifft per E-Mail ein.
- Prozessende: Servicemitarbeiter entscheidet über die tatsächlich versendete Antwort.
- Rollen: Kunde und Servicemitarbeiter.
- Systeme: CRM ist führend; E-Mail-Inhalte dürfen gelesen werden; Schreibschnittstelle im Pilot nicht zugesagt. [S2]
- Daten: E-Mail-Freitext sowie Kunden- und Vorgangsdaten im CRM.
- Bestätigter Kernbefund: Semantische Freitextarbeit verursacht Vorbereitungsaufwand; externer Versand erfordert immer menschliche Freigabe. [S1, S2]
- Unknown: Volumen, Bearbeitungszeit, Fehlerquote, personenbezogene Detailkategorien und Hostingmodell.

## Lösungsvergleich und Entscheidung

- Option 1: Vorlagen und manuelle Kategorisierung verbessern.
- Option 2: regelbasierte Klassifikation bekannter Schlüsselwörter.
- Option 3: Controlled-LLM-Assistenz für Kategorie und Antwortentwurf, ohne Versand- oder CRM-Schreibrecht.
- Entscheidung: Option 3 als begrenzter Pilotkandidat.
- Begründung: Freie Sprache erfordert semantische Verarbeitung; die menschliche Entscheidung bleibt unverändert.
- Architecture Mode: Controlled LLM.
- Human Gate: jeder externe Versand; Governance-Fakten und formale Reviews vor Approval.

## Use Case, Governance und Pilot

- Use Case: Antwortentwürfe für Servicemitarbeitende vorbereiten.
- Erwarteter Nutzen: weniger Vorbereitungsaufwand; nicht quantifiziert.
- Baseline/Ziel: unbekannt.
- Pilot: nur Entwurf, lesender Kontext, kein autonomer Versand, kein direktes CRM-Schreiben.
- Messung: aktive Vorbereitungszeit und fachliche Korrekturquote.
- Governance: personenbezogene Kundendaten sind plausibel, aber Umfang und Hosting sind nicht vollständig belegt; daher WAITING_HUMAN vor Approval.
- Formale Freigaben: keine automatisch bestanden.

## Provenance

- S1: `01_service_process.md`
- S2: `02_system_note.md`
- Alle Tatsachen sind belegt; Nutzen, Pilot und Lösungsoptionen sind als Ableitungen/Hypothesen gekennzeichnet.
