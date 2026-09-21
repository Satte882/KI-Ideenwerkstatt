# Repository-Arbeitsregeln

Vor jeder fachlichen Produktänderung müssen folgende Quellen gelesen werden:

1. [`docs/ROADMAP.md`](docs/ROADMAP.md)
2. relevante Architecture Decision Records unter [`docs/adr/`](docs/adr/)
3. die zum aktuellen Auftrag gehörenden Anforderungen und Akzeptanzkriterien

Vor jeder Änderung an Benutzeroberflächen muss zusätzlich [`DESIGN.md`](DESIGN.md)
vollständig gelesen und als verbindliches Design-System angewendet werden.

## Verbindliche Regeln

- Nur den in der Roadmap als **Nächster verbindlicher Umfang** markierten Produktpunkt umsetzen, sofern der Auftrag keine ausdrücklich dokumentierte Änderung der Reihenfolge enthält.
- Spätere Roadmap-Punkte nicht vorziehen und nicht zu einem großen PR bündeln.
- Bestehende `JourneyState`-, Berechtigungs- und Hard-Gate-Logik erweitern, statt parallele Statuslogik einzuführen.
- Jeden PR klein, abnehmbar und mit expliziten Nicht-Zielen halten.
- Nach einem relevanten Merge `docs/ROADMAP.md` aktualisieren: erledigte Punkte abhaken, Datum ergänzen und den nächsten verbindlichen Umfang festlegen.
- `OPEN_QUESTIONS.md` enthält offene Betriebs- und Konfigurationsfragen; die fachliche Produktreihenfolge steht ausschließlich in `docs/ROADMAP.md`.

## Verbindliche UI-Regeln

- Ausschließlich die semantischen Tokens aus `DESIGN.md` verwenden.
- Bestehende URLs, Berechtigungen, Formulare und serverseitige Abläufe bei visuellen Änderungen erhalten.
- Neue Oberflächen vor Abschluss gegen die Abnahmekriterien in `DESIGN.md` prüfen.
- Harte Verbote aus `DESIGN.md` dürfen nicht stillschweigend umgangen werden.
- Begründete Ausnahmen müssen vor ihrer Umsetzung ausdrücklich freigegeben werden.
