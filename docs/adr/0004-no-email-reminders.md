# ADR 0004: Keine E-Mail-Reminder im ersten Umsetzungsschritt

## Status
Akzeptiert

## Entscheidung
Fälligkeiten werden über Dashboard, Monatsreview und einen überwachten Scan sichtbar gemacht. SMTP-Versand wird zurückgestellt.

## Konsequenzen
`NotificationLog` und Servicegrenzen sind vorbereitet. Der spätere Versand benötigt keine Änderung des Lifecycle- oder Review-Datenmodells.
