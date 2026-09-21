# Offene Punkte und dokumentierte Entscheidungen

Dieses Dokument enthält bewusst alle Anforderungen, die nicht stillschweigend vereinfacht wurden. Punkte mit dem Status **offen** benötigen vor einer konkreten Produktivinstallation eine Entscheidung oder externe Konfiguration.

## 1. E-Mail-basierte Reminder

**Status:** bewusst offen / vom ersten Umsetzungsschritt ausgenommen

Es wird noch kein SMTP-Versand implementiert. Stattdessen sind umgesetzt:

- Dashboard mit fälligen und überfälligen Reviews,
- Monatsreview-Ansicht,
- Management-Command `scan_due_reviews`,
- operatives Job-Monitoring über `SystemJobRun`,
- bereits vorhandenes `NotificationLog` als späterer technischer Anknüpfungspunkt.

Für die Nachrüstung ist ein separater Benachrichtigungsservice vorgesehen. Status- und Fälligkeitslogik müssen dafür nicht verändert werden.

Vor der Nachrüstung zu entscheiden:

- SMTP-Relay oder API-basierter Maildienst,
- Absenderadresse,
- Empfänger- und Eskalationslogik,
- Aufbewahrungsdauer personenbezogener Versandprotokolle,
- Verhalten bei deaktivierten oder anonymisierten Benutzern.

## 2. Repository ist aktuell öffentlich

**Status:** offen und sicherheitsrelevant

Die Spezifikation nennt ein privates GitHub-Repository. Das bereitgestellte Repository `Satte882/KI-UseCase-Radar` ist zum Zeitpunkt der Umsetzung öffentlich.

Im Repository befinden sich keine Secrets oder produktiven Daten. Für einen späteren produktiven Betrieb sollte entschieden werden, ob das Repository privat geschaltet wird. Ein öffentliches Repository ist technisch möglich, erfordert aber weiterhin strikte Trennung von Code, Secrets und Betriebsdaten.

## 3. Repository-Lizenz

**Status:** offen

Es wurde keine Open-Source-Lizenz hinzugefügt. Bei einem öffentlichen Repository bedeutet das nicht automatisch, dass Dritte den Code beliebig verwenden dürfen. Vor einer externen Weitergabe ist eine Lizenzentscheidung erforderlich.

## 4. Leserechte

**Entscheidung:** alle authentifizierten aktiven Benutzer dürfen alle nicht archivierten Use Cases lesen

Die Spezifikation verwendet die Formulierung „freigegebene Use Cases“, definiert aber kein separates Freigabefeld. Für die erste Version gilt deshalb:

- alle authentifizierten Benutzer sehen alle nicht archivierten Use Cases,
- Bearbeitungsrechte bleiben rollen- und ownerabhängig,
- komplexe Sichtrechte nach Organisationseinheit sind nicht Bestandteil der ersten Version.

Falls vertrauliche Use Cases nur eingeschränkt sichtbar sein sollen, muss ein eigenes Sichtbarkeitsmodell ergänzt werden.

## 5. Pausieren und Überarbeiten

**Entscheidung:** kein zusätzlicher Lifecycle-Status

Die Entscheidungen „Pausieren“ und „Überarbeiten“ verändern den fünfstufigen Lifecycle-Status nicht. Sie werden als Review-Entscheidung mit Begründung und offenen Maßnahmen dokumentiert.

Da die Spezifikation sonst keinen eindeutigen Übergang von „Idee“ zu „Prüfung“ und keine Bedienhandlung für zulässige Rückstufungen enthält, wurden zwei Review-Entscheidungen ergänzt: „Prüfung starten“ und „In frühere Phase zurücksetzen“. Die fünf Lifecycle-Status bleiben unverändert.

## 6. Short-ID

**Entscheidung:** transaktionssicherer Datenbankzähler

Use Cases erhalten IDs wie `KI-0001`. Dafür wird eine separate Datenbanktabelle `UseCaseCounter` verwendet. Dies vermeidet die Race Condition einer Berechnung über den zuletzt vorhandenen Use Case.

Gelöschte oder verworfene Zählerwerte werden nicht wiederverwendet.

## 7. Statusänderungen

**Entscheidung:** Lifecycle-Änderungen erfolgen ausschließlich über Reviews

Das normale Bearbeitungsformular enthält kein frei editierbares Statusfeld. Statuswechsel erfolgen über den Review-Service und werden dadurch fachlich begründet, validiert und historisiert.

Administrative Notfallkorrekturen bleiben im Django Admin möglich und müssen organisatorisch begründet werden.

## 8. Governance-Prüfungen

**Entscheidung:** Screening setzt Prüfflags, bestätigt aber keine rechtliche Konformität

Das zuletzt gespeicherte Governance-Screening aktualisiert die Flags:

- Datenschutzprüfung erforderlich,
- Informationssicherheitsprüfung erforderlich,
- rechtliche Prüfung erforderlich.

Der Abschluss der jeweiligen Fachprüfung wird am Use Case dokumentiert. Die Anwendung trifft keine automatische AI-Act-Klassifizierung.

## 9. SSO und öffentliche Erreichbarkeit

**Status:** offen für die Produktivinstallation

Lokale Django-Anmeldung ist implementiert. Vor öffentlicher Internet-Erreichbarkeit ist laut Spezifikation Unternehmens-SSO mit MFA erforderlich. SSO ist nicht implementiert, weil kein konkreter Identity Provider und keine Mandantenkonfiguration vorliegen.

Bis dahin ist der Produktivzugriff auf internes Netz oder VPN zu beschränken.

## 10. Domain, TLS-Zertifikat und DNS

**Status:** offen

Nginx- und HTTPS-Konfiguration sind vorhanden. Nicht festgelegt sind:

- produktiver Hostname,
- Staging-Hostname,
- Zertifikatsbereitstellung,
- DNS-Konfiguration,
- Zertifikatserneuerung.

Die Dateien unter `deploy/certs/` sind absichtlich nicht Bestandteil des Repositorys.

## 11. Externes Fehlertracking

**Status:** technisch integriert, extern noch zu konfigurieren

Sentry oder ein kompatibler Dienst wird aktiviert, sobald `SENTRY_DSN` gesetzt ist. Ohne DSN läuft die Anwendung ohne externes Fehlertracking.

Vor Produktivbetrieb zu klären:

- Sentry Cloud oder selbst betriebene Alternative,
- Auftragsverarbeitung und Speicherort,
- Aufbewahrungsdauer,
- Alarmempfänger.

## 12. Externe Uptime-Überwachung und Alarmierung

**Status:** offen für die konkrete Infrastruktur

Health-Endpunkte und operative Jobzustände sind implementiert. Ein externer Monitoring-Account kann ohne Anbieter- und Empfängerdaten nicht automatisch eingerichtet werden.

Zu konfigurieren sind:

- Anbieter oder selbst betriebener Monitor,
- Prüfintervall,
- `X-Monitoring-Token`,
- unabhängiger Alarmierungskanal,
- Eskalationsziel.

## 13. Externe Backup-Kopie

**Status:** Backup technisch implementiert, Offsite-Ziel offen

Das Backup-Skript erstellt und verifiziert PostgreSQL-Custom-Format-Backups und unterstützt optional `RCLONE_REMOTE`. Für eine echte Offsite-Kopie fehlen noch Zielsystem und Zugangsdaten.

Vor Produktivbetrieb festzulegen:

- Offsite-Speicher,
- Verschlüsselungsverfahren,
- Schlüsselaufbewahrung,
- Aufbewahrungsfristen,
- Alarmierung bei fehlgeschlagener Übertragung.

## 14. Staging auf demselben Server

**Entscheidung:** separater Compose-Stack, keine physische Redundanz

Staging verwendet:

- eine eigene Datenbank,
- eigene Volumes,
- eigene Secrets,
- ein eigenes Netzwerk,
- Port `127.0.0.1:8001`.

Staging darf keine Produktionsdatenbank und keine realen Empfänger verwenden. Die Lösung schützt nicht gegen einen vollständigen Host-Ausfall.

## 15. Einzelbetrieb

**Status:** Solo-Betriebsfreigabe möglich, vollständige personelle Redundanz offen

Die technischen Solo-Anforderungen sind dokumentiert. Eine zweite eingearbeitete Person ist aktuell nicht vorhanden. Das verhindert nicht lokale Entwicklung oder einen dokumentierten Einzelbetrieb, aber die vollständige betriebliche Abnahme bleibt bis zur Übergabe an eine zweite Person offen.

## 16. Bootstrap-Bereitstellung

**Entscheidung:** fest gepinnte CDN-Dateien mit SRI

Bootstrap 5.3.8 wird über jsDelivr geladen und durch Subresource Integrity abgesichert. Die Content-Security-Policy erlaubt ausschließlich den festgelegten CDN-Host.

Bei Betrieb ohne Internetzugriff sollten die beiden Bootstrap-Dateien später lokal vendort werden. Die Anwendung bleibt fachlich nutzbar, aber ohne CDN nicht vollständig formatiert.

## 17. Volltextsuche

**Entscheidung:** relationale `icontains`-Suche für die erwartete Datenmenge

Bei 10–30 Use Cases ist eine PostgreSQL-Full-Text-Search-Konfiguration nicht erforderlich. Die Suche umfasst ID, Titel, Problemstellung und erwarteten Nutzen.

Bei deutlich größeren Datenmengen kann ein PostgreSQL-Suchvektor ergänzt werden.

## 18. Dokumentenlinks

**Entscheidung:** keine Berechtigungsprüfung externer Links

KI-Radar speichert ausschließlich URLs. Berechtigungen und Verfügbarkeit des Zielsystems werden nicht synchronisiert. Nutzer können daher Links sehen, deren Ziel sie nicht öffnen dürfen.
