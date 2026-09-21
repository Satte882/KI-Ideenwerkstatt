# KI-Radar lokal starten

## 1. Voraussetzungen

- Git for Windows
- Visual Studio Code
- Docker Desktop mit aktivierter WSL-2-Engine

Optional für native Entwicklung: Python 3.13 und uv 0.10.x.

## 2. Repository aktualisieren

```powershell
cd C:\Users\user\Documents\GitHub\KI-UseCase-Radar
git fetch origin
git pull --ff-only origin main
```

Bei einer Erstinstallation:

```powershell
cd C:\Users\user\Documents\GitHub
git clone https://github.com/Satte882/KI-UseCase-Radar.git
cd KI-UseCase-Radar
code .
```

## 3. Lokale Konfiguration

Falls noch keine `.env` vorhanden ist:

```powershell
Copy-Item .env.example .env
```

Für den optionalen semantischen Review-Copilot kann in `.env` eingetragen werden:

```dotenv
OPENROUTER_API_KEY=<eigener-key>
OPENROUTER_MODEL=<optionaler-modell-slug>
```

Ohne API-Key funktionieren alle verbindlichen Discovery-, Bewertungs-, Governance-, Portfolio- und Delivery-Funktionen vollständig. Die `.env` ist durch `.gitignore` ausgeschlossen und darf nicht committed werden.

## 4. Anwendung mit Docker starten

```powershell
docker compose -f compose.local.yml up --build
```

Beim Start werden automatisch:

- PostgreSQL gestartet,
- alle Migrationen ausgeführt,
- die vier Rollen angelegt,
- statische Dateien gesammelt,
- der Django-Entwicklungsserver gestartet.

Anwendung:

```text
http://127.0.0.1:8000
```

## 5. Demo-Daten für den End-to-End-Test

Ein zweites Terminal öffnen:

```powershell
docker compose -f compose.local.yml exec app `
  python manage.py seed_demo_data --password "Demo-Test-2026!"
```

Anmeldung als KI-Koordinator:

```text
Benutzer: demo_ki_koordinator
Passwort: Demo-Test-2026!
```

Der Demo-Datensatz enthält:

- Lifecycle- und Governance-Fälle,
- strukturierte Erfolgsmetriken,
- einen Value Stream „Beschaffung bis Zahlung“,
- eine detaillierte Prozessanalyse zur Eingangsrechnungsprüfung,
- eine bevorzugte Lösungsoption,
- einen daraus abgeleiteten und final freigegebenen Use Case,
- ein vorausgefülltes Delivery Package im Status „Bereit zur Übergabe“.

Dadurch können Discovery, TOGAF-light-Artefakte, Use-Case-Governance, Portfolio und Delivery-Handover ohne zusätzliche Stammdaten getestet werden.

Demo-Daten entfernen:

```powershell
docker compose -f compose.local.yml exec app python manage.py clear_demo_data
```

Die Befehle sind wiederholbar. Ein bereits übergebenes Demo-Package bleibt bei erneutem Seeding unverändert.

## 6. Empfohlener fachlicher Testablauf

### Discovery und Business Architecture

1. In der Sidebar **Analyse** öffnen.
2. Den Value Stream **[DEMO] Beschaffung bis Zahlung** öffnen.
3. Auslöser, Ergebnis, Scope, strategisches Ziel, Stakeholder und Leitplanken prüfen.
4. Die Phase **Eingangsrechnung prüfen** öffnen beziehungsweise ihre Detailinformationen prüfen.
5. Die Prozessanalyse **Eingangsrechnungsprüfung** öffnen.
6. Ist-Ablauf, Rollen, Systeme, Datenobjekte, Regeln, Übergaben, Bottlenecks und Baseline nachvollziehen.
7. Die bevorzugte Lösungsoption mit organisatorischen beziehungsweise technischen Alternativen vergleichen.

### Use Case, Entscheidung und Portfolio

8. Den verknüpften Use Case **[DEMO] Automatische Rechnungspruefung** öffnen.
9. Herkunft, Nutzenmetrik, Governance und finale Freigabe prüfen.
10. Im Bereich **Portfolio** die Einordnung nach Nutzen, Machbarkeit, Entscheidungsstatus und Confidence ansehen.
11. Auf Dashboard und Detailseite die bearbeitbaren Blocker anderer Demo-Use-Cases testen.

### Delivery-Handover

12. Den Bereich **Delivery** öffnen.
13. Das vorhandene Delivery Package zur Rechnungsprüfung öffnen.
14. Scope, Zielbild, Anforderungen, MVP, Akzeptanzkriterien, Testfälle und initiales Backlog prüfen.
15. Markdown exportieren.
16. Das Package als KI-Koordinator an Delivery übergeben.
17. Prüfen, dass die übergebene Version nicht mehr bearbeitet werden kann.
18. Über die Delivery-Übersicht eine neue Version erzeugen und als neuen Entwurf bearbeiten.

### Optionaler Copilot

19. Bei gesetztem `OPENROUTER_API_KEY` auf einer Use-Case-Detailseite die semantische Review-Analyse starten.

Der Copilot liefert ausschließlich Hinweise. Er darf keine Freigabe, keinen Lifecycle-Übergang und keinen Delivery-Handover auslösen.

## 7. Eigenes Administratorkonto

```powershell
docker compose -f compose.local.yml exec app python manage.py createsuperuser
```

Danach:

```text
http://127.0.0.1:8000/accounts/login/
http://127.0.0.1:8000/admin/
```

Im Admin mindestens eine Organisationseinheit und die benötigten Benutzer anlegen. Benutzer werden einer oder mehreren Gruppen zugeordnet:

- Technischer Administrator
- KI-Koordinator
- Business Owner
- Leser

## 8. Qualitätsprüfungen

```powershell
docker compose -f compose.local.yml exec app pytest
docker compose -f compose.local.yml exec app ruff check .
docker compose -f compose.local.yml exec app ruff format --check .
docker compose -f compose.local.yml exec app python manage.py check
docker compose -f compose.local.yml exec app python manage.py makemigrations --check --dry-run
docker compose -f compose.local.yml exec app bandit -q -r ki_radar config
docker compose -f compose.local.yml exec app pip-audit
```

Produktionscontainer lokal bauen:

```powershell
docker build -t ki-radar:local .
```

## 9. Native Entwicklung mit uv

Bei nativer Ausführung lädt Django die `.env` nicht automatisch. Zuerst PostgreSQL starten und Abhängigkeiten synchronisieren:

```text
docker compose -f compose.local.yml up -d db
uv sync --frozen --dev
```

Die `.env.example` verwendet für die native Verbindung den Host-Port `5433`.

Unter Linux und macOS:

```bash
cp .env.example .env  # nur falls noch keine .env vorhanden ist
set -a
source .env
set +a

uv run python manage.py migrate
uv run python manage.py seed_roles
uv run pytest -q
uv run python manage.py runserver
```

Unter PowerShell die Einträge sicher zeilenweise in die Prozessumgebung laden:

```powershell
$envFile = ".env"
Get-Content -LiteralPath $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $name, $value = $line -split "=", 2
        if ($name) {
            [Environment]::SetEnvironmentVariable(
                $name.Trim(),
                $value,
                "Process"
            )
        }
    }
}

uv run python manage.py migrate
uv run python manage.py seed_roles
uv run pytest -q
uv run python manage.py runserver
```

## 10. Health-Checks

```text
http://127.0.0.1:8000/health/live
http://127.0.0.1:8000/health/ready
```

## 11. Lokale Daten vollständig zurücksetzen

**Achtung:** Löscht die lokale Datenbank und lokale Volumes.

```powershell
docker compose -f compose.local.yml down -v
docker compose -f compose.local.yml up --build
```

## 12. Häufige Fehler

### OpenRouter-Schaltfläche ist deaktiviert

Prüfen, ob `OPENROUTER_API_KEY` in `.env` gesetzt wurde. Anschließend den App-Container neu starten:

```powershell
docker compose -f compose.local.yml up -d --force-recreate app
```

### Anwendung startet nach einem Codewechsel nicht

```powershell
docker compose -f compose.local.yml down
docker compose -f compose.local.yml up --build
```

### Migrationen fehlen

```powershell
docker compose -f compose.local.yml exec app `
  python manage.py makemigrations --check --dry-run
```

### Port 8000 oder 5433 ist belegt

In `compose.local.yml` den linken Host-Port ändern. Der Container-Port bleibt unverändert.

## 13. Wo UI-Eingaben gespeichert werden

Fachliche Eingaben aus der Weboberfläche werden nach erfolgreicher Validierung in der lokalen PostgreSQL-Datenbank gespeichert. Sie landen nicht in Python-, HTML- oder Konfigurationsdateien und werden nicht durch einen Git-Commit auf GitHub übertragen.

Der lokale Docker-Compose-Stack verwendet das benannte Volume:

```text
local_db → /var/lib/postgresql/data
```

Da der Compose-Projektname `ki-radar-local` lautet, heißt das durch Docker verwaltete Volume normalerweise:

```text
ki-radar-local_local_db
```

Der konkrete physische Pfad wird von Docker Desktop beziehungsweise Docker Engine verwaltet und liegt nicht im Repository.

### Was erhalten bleibt

Diese Vorgänge lassen die lokale Datenbank normalerweise bestehen:

```powershell
docker compose -f compose.local.yml stop
docker compose -f compose.local.yml down
docker compose -f compose.local.yml up --build
```

Auch `git pull`, Branchwechsel, Merge und Code-Rebuild übertragen oder löschen die fachlichen Daten nicht. Git und PostgreSQL sind voneinander getrennt.

### Was Daten löscht

Der bereits in Abschnitt 11 dokumentierte Befehl

```powershell
docker compose -f compose.local.yml down -v
```

löscht das Datenbank-Volume und damit alle ausschließlich lokal gespeicherten Anwendungsdaten. Dasselbe gilt für das manuelle Löschen des Volumes in Docker Desktop.

Persistenz im Volume ist kein Backup. Für das lokale Entwicklungssetup besteht keine automatisch zugesicherte externe Sicherung.

### Volumes prüfen

```powershell
docker volume ls --filter name=ki-radar-local
docker volume inspect ki-radar-local_local_db
```

Der tatsächliche Volumename kann abweichen, wenn beim Start ein anderer Compose-Projektname verwendet wurde.

### Externe Übertragung durch den optionalen Copilot

Ohne `OPENROUTER_API_KEY` werden keine Use-Case-Daten an OpenRouter gesendet. Wird der Review-Copilot ausdrücklich gestartet, überträgt die Anwendung ausgewählte Use-Case-Daten an die konfigurierte OpenRouter-API. Der Copilot ist optional und keine Freigabeinstanz.

Die vollständige Übersicht zu gespeicherten Datenarten, Historie, Nachweislinks, Staging, Produktion, Backups und externen Übertragungen steht in [`docs/DATA_STORAGE.md`](docs/DATA_STORAGE.md).