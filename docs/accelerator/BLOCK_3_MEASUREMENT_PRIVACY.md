# Block 3 – Messung und Datenschutz

## Zweckbindung

Die Capture-Funktion speichert ausschließlich drei technische Messgrößen:

1. kumulierte aktive Eingabezeit in Sekunden,
2. Anzahl erfolgreicher Speicherungen,
3. Abschlusszeitpunkt.

Die Kalenderdauer ergibt sich getrennt aus Anlage- und Abschlusszeitpunkt. Aktive Eingabezeit und Kalenderdauer werden nicht vermischt.

## Progressive Zeitmessung

- Der Wizard funktioniert vollständig ohne JavaScript; fehlende clientseitige Messwerte werden als null Sekunden behandelt.
- JavaScript zählt nur Zeit, in der ein natives Capture-Feld fokussiert und das Dokument sichtbar ist.
- Pro Speicherung werden serverseitig höchstens 900 Sekunden übernommen.
- Negative oder nicht numerische Werte werden nicht als Messwert akzeptiert.
- Es werden keine Tastendrücke, Klickpfade, Feldinhalte, Zwischenstände oder Gerätekennungen als Telemetrie erfasst.

## Schutz der Rohantworten

- Start- und Wizard-POST-Daten sind für Django-Fehlerberichte vollständig als sensibel markiert.
- Service- und Validierungsfehler verwenden generische Meldungen und geben keine Antwortinhalte zurück.
- Standardlogs enthalten keine Capture-Antworten, Prompts oder vollständigen Formdaten.
- Die Messung sendet keine Daten an externe Endpunkte und verwendet weder Browser-Speicher noch Analytics-Schnittstellen.

## Abgrenzung

Block 3 führt keine Produkt-Analytics-Plattform ein. Die Messwerte sind eine kleine technische Grundlage für die spätere Wirksamkeitsbetrachtung in Block 9 und dürfen nicht für detaillierte Verhaltensprofile verwendet werden.
