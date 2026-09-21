# Monitoring und Observability

## Endpunkte

- `/health/live`: Prozess reagiert
- `/health/ready`: Datenbankzugriff funktioniert
- `/health/operations`: Backup- und Review-Scan sind aktuell; benötigt Header `X-Monitoring-Token`

## Operative Jobs

Die Anwendung erwartet erfolgreiche Läufe für `database_backup` und `review_scan`. Standardmäßig gilt ein Lauf nach 26 Stunden als veraltet.

```bash
python manage.py check_operational_health
```

## Sentry

Aktivierung durch `SENTRY_DSN` beziehungsweise Docker Secret `sentry_dsn`.

Vorgaben:

- `send_default_pii=False`
- Request-Bodies werden nicht gesendet
- Umgebungen `staging` und `production` getrennt
- keine Secrets, Cookies oder Authorization-Header erfassen

## Mindestalarme

- Anwendung fünf Minuten nicht erreichbar
- Readiness fehlerhaft
- operativer Health-Endpunkt liefert 503
- kein erfolgreiches Backup innerhalb von 26 Stunden
- kein erfolgreicher Review-Scan innerhalb von 26 Stunden
- TLS-Zertifikat weniger als 14 Tage gültig
- Speicherplatz unter definierter Schwelle
- wiederholte Container-Neustarts

Die konkrete externe Alarmierung ist in `OPEN_QUESTIONS.md` dokumentiert.
