# Kontrollierte Datenkorrekturen

Fachliche Anwendungsdaten liegen in PostgreSQL und nicht im Git-Repository. Eine reine Datenkorrektur benötigt deshalb einen expliziten Nachweis, auch wenn keine Migration oder dauerhafte Programmlogik geändert wird.

## Grundsätze

1. Repository-Evidenz wird vor der Zielumgebung geprüft.
2. Die Zielumgebung wird zunächst nur gelesen.
3. Sollwerte werden fachlich festgelegt und niemals aus Freitext heuristisch abgeleitet.
4. Eine Änderung ist auf einen exakten Datensatz, exakte Vorherwerte und einen exakten Zeitstempel begrenzt.
5. Vorher-/Nachherwerte und die Prüfung verwandter Datensätze werden in einem privaten Audit dokumentiert.
6. Private Pläne und Audits dürfen nicht in dieses öffentliche Repository committed werden.

## Issue #106: Real-DEMO-Scope

Der Befehl `correct_real_demo_scope` ist ausschließlich für den Datensatz
`[Real-DEMO] Beschaffungsbedarf bis Bestellung` vorgesehen. Er zerlegt keinen Text automatisch und ändert keine weiteren Value Streams.

### 1. Repository prüfen

Auf einem vollständigen Checkout des aktuellen `main`:

```powershell
git grep -n -F "[Real-DEMO] Beschaffungsbedarf bis Bestellung"
git grep -n -F "Beschaffungsbedarf bis Bestellung"
git grep -n -F "Nicht im Scope"
git grep -n -E "fixture|loaddata|import.*ValueStream|update_or_create.*ValueStream"
```

Das Ergebnis wird als private Arbeitsnotiz oder über eine geeignete interne Referenz dokumentiert.

### 2. Zielumgebung nur lesen

Im lokalen Docker-Setup heißt der Anwendungsservice `app`:

```powershell
docker compose -f compose.local.yml exec app python manage.py correct_real_demo_scope --inspect
```

Der Befehl gibt den exakten Zieldatensatz und alle derzeit vorhandenen `[Real-DEMO]`-Value-Streams als JSON aus. Alle aufgeführten Datensätze müssen fachlich geprüft werden.

### 3. Privaten Korrekturplan erstellen

Der Plan wird zunächst außerhalb des Repository-Verzeichnisses auf dem Host erstellt, beispielsweise unter `C:\private\issue-106-plan.json`:

```json
{
  "issue": 106,
  "environment": "local",
  "operator": "Name der ausführenden Person",
  "backup_reference": "Referenz auf Sicherung oder begründete lokale Rückfalloption",
  "repository_check_reference": "Referenz auf das Ergebnis der Repository-Prüfung",
  "target": {
    "id": "UUID aus --inspect",
    "name": "[Real-DEMO] Beschaffungsbedarf bis Bestellung",
    "expected_updated_at": "ISO-Zeitstempel aus --inspect",
    "expected_scope_in": "Exakter bisheriger Wert",
    "expected_scope_out": "Exakter bisheriger Wert",
    "new_scope_in": "Fachlich bestätigter eingeschlossener Umfang",
    "new_scope_out": "Fachlich bestätigte ausdrückliche Abgrenzung"
  },
  "real_demo_review": {
    "reviewed_ids": [
      "UUID jedes über --inspect ausgegebenen Real-DEMO-Value-Streams"
    ],
    "conclusion": "Ergebnis der fachlichen Prüfung aller Real-DEMO-Value-Streams"
  }
}
```

Der lokale Compose-Stack bindet das persistente, nicht versionierte Volume `local_var` unter `/app/var` ein. Der Plan wird dorthin kopiert:

```powershell
docker compose -f compose.local.yml exec app mkdir -p /app/var/data-corrections
docker compose -f compose.local.yml cp "C:\private\issue-106-plan.json" app:/app/var/data-corrections/issue-106-plan.json
```

### 4. Plan ohne Änderung validieren

```powershell
docker compose -f compose.local.yml exec app python manage.py correct_real_demo_scope --plan /app/var/data-corrections/issue-106-plan.json
```

Der Dry Run prüft:

- Issue und exakten Datensatznamen,
- UUID und Zeitstempel,
- exakte Vorherwerte,
- Vollständigkeit der geprüften `[Real-DEMO]`-IDs,
- tatsächlich abweichende Sollwerte.

Die Ausgabe enthält nur SHA-256-Prüfsummen der Scope-Texte und keine fachlichen Rohwerte.

### 5. Änderung atomar anwenden

```powershell
docker compose -f compose.local.yml exec app python manage.py correct_real_demo_scope --plan /app/var/data-corrections/issue-106-plan.json --apply --audit-path /app/var/data-corrections/issue-106-audit.md
```

Die Änderung wird nur ausgeführt, wenn UUID, Name, `scope_in`, `scope_out`, `updated_at` und die vollständige Real-DEMO-Inventarliste weiterhin dem geprüften Plan entsprechen. Es muss exakt eine Datenbankzeile geändert werden.

Der Audit wird zunächst mit Status `PREPARED` angelegt und nach erfolgreichem Commit durch den Status `APPLIED` ersetzt. Bleibt `PREPARED` bestehen, muss vor einem erneuten Versuch geprüft werden, ob eine Änderung stattgefunden hat.

Der private Audit kann anschließend auf den Host kopiert werden:

```powershell
docker compose -f compose.local.yml cp app:/app/var/data-corrections/issue-106-audit.md "C:\private\issue-106-audit.md"
```

### 6. Abschlussnachweis

Für den Abschluss von Issue #106 werden im GitHub-Issue nur nicht vertrauliche Angaben dokumentiert:

- Umgebung und Ausführungszeitpunkt,
- Datensatz-UUID,
- Anzahl geänderter Zeilen,
- SHA-256 des privaten Audits,
- Ergebnis der UI-Prüfung,
- Ergebnis der Prüfung aller weiteren `[Real-DEMO]`-Value-Streams.

Die fachlichen Vorher-/Nachherwerte verbleiben ausschließlich im privaten Audit.
