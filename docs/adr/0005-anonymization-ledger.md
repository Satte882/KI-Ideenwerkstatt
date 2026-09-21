# ADR 0005: Externes Anonymisierungs-Ledger

## Status
Akzeptiert

## Entscheidung
Anonymisierungen werden zusätzlich in einer append-only JSONL-Datei mit interner Benutzer-ID dokumentiert.

## Konsequenzen
Nach Restore eines älteren Backups können spätere Anonymisierungen erneut angewendet werden. Das Ledger darf keine Klarnamen oder realen Kontaktinformationen enthalten und muss separat gesichert werden.
