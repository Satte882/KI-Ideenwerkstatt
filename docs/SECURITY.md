# Sicherheitskonzept

## Grundsätze

- kein Secret im Repository
- serverseitige Berechtigungsprüfung
- HTTPS in Produktion
- PostgreSQL nicht öffentlich erreichbar
- getrennte Secrets und Datenbanken für Staging und Produktion
- Argon2 als bevorzugter Passwort-Hasher
- Login-Sperre über django-axes
- CSP, HSTS, sichere Cookies und CSRF-Schutz

## Secrets

Produktive Secrets werden als Dateien unter einem geschützten Hostpfad gespeichert und durch Docker Compose Secrets eingebunden.

```text
django_secret_key
db_password
sentry_dsn
monitoring_token
```

Dateirechte unter Linux: `600`, Eigentümer `root`.

## Öffentliche Erreichbarkeit

Ohne SSO mit MFA ist die Anwendung auf internes Netz oder VPN zu beschränken. Nginx-Rate-Limiting und django-axes ersetzen kein MFA.

## Logging

Nicht protokollieren:

- Passwörter
- Tokens und Session-Cookies
- Secret-Werte
- vollständige vertrauliche Formularinhalte
- unnötige personenbezogene Daten
- vollständige LLM-Prompts oder Capture-Antworten
- vollständige rohe LLM-Antworten

Für LLM-Aufrufe sind ausschließlich bereinigte technische Metadaten zulässig, beispielsweise Aufrufzweck, Provider, Modell, interner Zielobjektbezug, Laufzeit, Eingabe-/Ausgabegröße, Ergebnisstatus, Fehlercode sowie Token- und Kostenwerte, soweit verfügbar.

Die verbindlichen Accelerator-Datenfluss-, Logging- und Retention-Regeln stehen in [`accelerator/BLOCK_1_FOUNDATION.md`](accelerator/BLOCK_1_FOUNDATION.md).

## Datenschutz

Anonymisierung entfernt direkt identifizierende Benutzerattribute und erhält nur die interne relationale ID. Eine rückführbare Klarnamenzuordnung wird nicht geführt. Das externe Ledger enthält lediglich technische interne IDs und anonymisierte Benutzernamen zur Wiederanwendung nach Restore.

## Sicherheitsprüfung vor Release

```bash
python manage.py check --deploy
ruff check .
bandit -c pyproject.toml -r ki_radar config
pip-audit
pytest
```
