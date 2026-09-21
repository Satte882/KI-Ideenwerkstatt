# ADR 0002: django-simple-history

## Status
Akzeptiert

## Entscheidung
Fachliche Modelle werden mit `django-simple-history` historisiert. Fachliche Entscheidungen bleiben zusätzlich eigenständige Review-Datensätze.

## Konsequenzen
Technische Änderungen und fachliche Entscheidungen sind getrennt nachvollziehbar. Benutzeranonymisierung muss die Darstellung historischer `history_user`-Referenzen berücksichtigen.
