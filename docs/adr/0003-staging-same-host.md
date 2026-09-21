# ADR 0003: Staging auf demselben Host

## Status
Akzeptiert für Einzelbetrieb

## Entscheidung
Staging läuft als separater Docker-Compose-Stack mit eigener Datenbank, eigenen Volumes, Secrets, Netzwerk und Port auf demselben Host.

## Konsequenzen
Logische Trennung ist gegeben, physische Ausfallsicherheit nicht. Staging ersetzt keine Offsite-Backups.
