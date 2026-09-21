# ADR 0007: Bestehendes Lifecycle-Review für Go-live und Abschluss wiederverwenden

## Status

Akzeptiert am 22.07.2026.

## Kontext

Der Golden Path benötigt verbindliche Entscheidungen für `Pilot → Betrieb` und den Abschluss. Reviewer, Entscheidungsbegründung, alter und neuer Status sowie eine ausdrückliche Go-live-Ausnahme sind bereits im bestehenden `Review`-Modell vorhanden.

## Entscheidung

Das bestehende Lifecycle-Review bleibt die einzige führende Entscheidungs- und Historienquelle.

- `GO_LIVE` ist verbindlich mit `Pilot → Betrieb` gekoppelt.
- `END` ist verbindlich mit dem Zielstatus `Beendet` gekoppelt.
- Eine Ausnahme bei verfehltem Ziel wird im bestehenden Review gespeichert.
- Die Ausnahme darf ausschließlich ein Mitglied der Gruppe `KI-Koordinator` bestätigen.
- Use Case, Review, Reviewer, Begründung, Ausnahme und Statuswechsel werden in einer Datenbanktransaktion gespeichert.
- Bestandsfälle werden nicht rückwirkend verändert; die Gates gelten bei zukünftigen Übergängen.

## Konsequenzen

- kein neues Review- oder Entscheidungssystem
- kein zusätzlicher Lifecycle-Status
- keine Zwei-Personen-Freigabe in diesem Inkrement
- keine erfundenen Backfills für bestehende Mess- oder Abschlussdaten
- technische Administratoren dürfen eine Go-live-Ausnahme nicht allein aufgrund ihrer technischen Rolle bestätigen
