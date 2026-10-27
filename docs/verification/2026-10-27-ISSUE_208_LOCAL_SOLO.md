# Issue #208 / PR #209: lokaler Praxistest mit echter KI-Anbindung

## Zweck und Grenzen

Der lokale Einstieg erleichtert einem einzelnen Tester den Wechsel zwischen getrennten
Testidentitäten. Die Anwendung verwendet die produktiven Fachservices, Prompts, Schemas,
Modelltransporte und Validierungen. Es gibt keinen eigenen Solo-Discovery-Workflow,
keine festen KI-Antworten und keinen positiven Offline-Verifier.

Echte Modellaufrufe mit synthetischen Daten sind für diesen Auftrag ausdrücklich erlaubt.
Quellen und Kontext werden an die konfigurierte Modellanbindung übermittelt; dabei können
Kosten entstehen. Keine Unternehmensdaten oder personenbezogenen Echtdaten verwenden.
Die lokale Datenhaltung verhindert diese ausdrücklich gewollten Modellaufrufe nicht.

Ein Rollenwechsel ersetzt keine unabhängige menschliche Beurteilung. Die vorhandenen
Vier-Augen-, Berechtigungs-, Evidenz- und Freigaberegeln bleiben unverändert. #161 bleibt
unverändert und zurückgestellt. Technische Tests sind keine fachlichen Abnahmeergebnisse.

## Start und Datenhaltung

Voraussetzungen: bestehende Python-/uv-Umgebung, lokale PostgreSQL-Datenbank auf Port 5433
und die normale Modellkonfiguration in `.env`. Die Solo-Settings überschreiben weder
API-Schlüssel noch Modellnamen oder API-Endpunkt.

```powershell
.\scripts\start-solo.ps1 -Prepare
```

Die Vorbereitung erstellt bei Bedarf ausschließlich `ki_radar_solo`, migriert diese
Datenbank und legt Testkonten idempotent an. Bestehende Daten und Passwörter werden nicht
ersetzt. Anschließend reicht `.\scripts\start-solo.ps1`.

Der Starter startet den regulären `run_investigation_worker` im Hintergrund und den
Webserver auf `127.0.0.1:8000`. Der Worker verwendet dieselben Solo-Settings und dieselbe
isolierte Datenbank wie der Webserver. Seine Protokolle und PID-Datei liegen unter
`var/solo/`; der Webserver endet mit Strg+C. Der Hintergrundworker bleibt für ausstehende
Untersuchungen aktiv. Vor einem manuellen Beenden den Prozess anhand der PID-Datei und
seiner Kommandozeile prüfen; keine fremden Worker beenden.

Einstieg: `http://127.0.0.1:8000/solo/`. Benutzer: `solo_master`. Das zufällige lokale
Passwort liegt in `secrets/solo-master-password.txt`, außerhalb von Git.

Nur der explizite Settings-Einstieg `config.settings.solo`, DEBUG, lokale Hosts und eine
lokale PostgreSQL-Datenbank mit Präfix `ki_radar_solo` erlauben den Rollenwechsel.
`SOLO_DATABASE_NAME` und `SOLO_DATABASE_PORT` erlauben weitere isolierte lokale Datenbanken;
eine normale `DATABASE_URL` kann diese Datenbankauswahl nicht überschreiben. Session- und
CSRF-Cookies, Quellen und Anonymisierungsledger sind vom normalen lokalen Betrieb getrennt.
Der Server akzeptiert nur lokale Zugriffe. In normalen Settings existieren die Solo-Routen
nicht. Ein bloßes Flag aktiviert sie nicht.

## Identitäten

| Auswahl | Tatsächlicher Benutzer | Zweck |
| --- | --- | --- |
| Master | `solo_master` | Testverwaltung und Rollenwechsel, keine Fachaktionen |
| Business Owner | `solo_owner` | Eigene Szenarien erfassen und fachlich bearbeiten |
| KI-Koordination | `solo_coordination` | Strukturierte Bewertung gemäß normalen Rechten |
| Zweite KI-Koordination | `solo_review` | Getrennte Benutzeridentität für technische Freigabeschritte |
| Technischer Administrator | `solo_technical` | Bestehende technische Fachrolle, kein Superuser |
| Leser | `solo_reader` | Leseberechtigte Sicht und Prüfung abgewiesener Änderungen |

Der signierte Master-Nachweis läuft nach vier Stunden ab und wird bei Logout,
Passwortänderung, deaktivierten Konten oder veränderten Zielrechten ungültig.
Wechsel sind CSRF-geschützte POSTs und auf die Testkonten begrenzt. Pro Wechsel werden
Master, vorheriger und wirksamer Benutzer protokolliert. Fachaktionen werden unter der
tatsächlichen Zielidentität gespeichert. Nur die beiden normalen Intake-Entwurfsschlüssel
werden pro Identität beim Wechsel erhalten; Authentifizierungsdaten werden nicht kopiert.

## Praktischer Durchlauf mit eigenen Szenarien

1. Als Master anmelden, auf der Solo-Seite **Business Owner** wählen. Einen eigenen
   synthetischen Kontext und passende `.md`-, `.txt`- oder `.csv`-Quellen vorbereiten.
   Unbekannte Baselines, Quoten und Zeitwerte ausdrücklich als unbekannt kennzeichnen.
2. **A – Eigenes Geschäftsproblem untersuchen:** normalen Discovery-Einstieg öffnen,
   Testorganisation auswählen, Problem und Kontext eingeben, eigene Quellen hochladen.
   Die echte Modellanalyse erzeugt Wertstrom, Phasen und Fokusvorschläge; der reguläre
   Review kann Rückfragen, Fehler oder eine Bestätigungsmöglichkeit ergeben. Diese
   Ergebnisse selbst auf Quellenbezug und fachliche Stimmigkeit prüfen.
3. **B – Eigenes strategisches Ziel untersuchen:** strategischen Einstieg öffnen,
   Ziel und vorläufige Untersuchungsgrenze formulieren. Scope, Wertstromergebnis,
   Geschäftsergebnis, Prozessbeitrag und Wirkannahme getrennt prüfen. Eine Tätigkeit
   ist kein überprüfbares Ergebnis. Hypothesen sind keine nachgewiesenen Verbesserungen.
   Den Scope erst nach eigener Prüfung über die normalen Schritte bestätigen.
4. **C – Eigenen direkten Use Case erfassen:** normalen Use-Case-Einstieg verwenden.
   Kontext, Nutzenhypothese und benötigte Nachweise selbst eintragen. Für KI-Funktionen
   die normalen angebotenen Aktionen verwenden. Keine Ergebnisse oder Freigaben werden
   durch den Solo-Einstieg vorgegeben.
5. In allen drei Wegen die folgenden regulären Schritte einschließlich Untersuchung,
   Lösungsalternativen, Bewertung und weiterer Ergebnisse durchlaufen, soweit die
   Anwendung sie für den aktuellen Stand zulässt. Der normale Hintergrundworker führt
   angeforderte Untersuchungen bis zur nächsten fachlichen Grenze aus. Offene Nachweise,
   Quellen- oder Modellfehler bleiben sichtbar und blockieren gemäß den vorhandenen Regeln.
6. Für eine andere Fachsicht über das Banner zur Solo-Seite zurückgehen und die passende
   Identität wählen. Ein Wechsel ersetzt keine erforderliche Bestätigung. Getrennte
   Benutzerkonten machen aus einem Tester keine zwei unabhängigen Menschen.

Befunde getrennt von Anwendungsentscheidungen protokollieren: Kennung A1/B1/C1, Rolle,
Schritt oder URL, eigener Eingabekontext, beobachtetes Ergebnis, erwartetes Ergebnis und
gegebenenfalls Screenshot. Keine Qualität oder Verbesserung als erreicht markieren,
bevor sie tatsächlich geprüft beziehungsweise gemessen wurde.

## Vorhandene Offline-Daten

Historische Analysen mit Modellkennung `solo/offline*` bleiben unverändert gespeichert,
einschließlich Quellen und bisheriger Prüfpayloads. Die Review-Seite kennzeichnet sie als
feste historische Testentwürfe. Sie gelten nicht mehr als unterstützte Discovery-Analysen
und können nicht als aktuelle KI-Qualitätsevidenz materialisiert werden. Für den echten
Test eine neue Untersuchung anlegen oder über den normalen Pfad erneut analysieren.

## Technische Prüfungen

`tests/test_issue_208_solo.py` prüft Isolation, getrennte Rollen, unabhängige Freigaben,
CSRF, Widerruf, Entwurfserhalt, idempotente Vorbereitung und die Abwesenheit der Routen
im normalen Betrieb. Zusätzlich prüft es identischen konfigurierten Modelltransport mit
und ohne Solo-Flag, eigene A/B-Eingaben über die produktiven Views und den unveränderten
Erhalt historischer Offline-Payloads bei gesperrter Bestätigung.

Unit-Tests ersetzen ausschließlich die externe HTTP-Verbindung beziehungsweise beobachten
den normalen Analyse-Aufruf. Diese Testdoubles sind kein Laufzeitprovider und liefern
keine fachlichen Qualitätsergebnisse für den Praxistest. Die gesamte CI bleibt aktiv.

Ein realer Aufruf am 27.10.2026 über den regulären HTTP-Discovery-Einstieg mit einer neu
hochgeladenen synthetischen Geräteausleihe-Quelle erreichte OpenRouter und
`google/gemini-3.6-flash`: Transport/Analyse erfolgreich, ca. 62 Sekunden, 14.630 Tokens,
protokollierte Aufrufkosten 0,0362415 USD. Dies ist ausschließlich ein technischer
Verbindungsnachweis; keine fachliche Abnahme. Die drei historischen Offline-Analysen
blieben dabei nach Hashvergleich unverändert.

Auch der strategische Einstieg B wurde mit derselben neuen synthetischen Quelle über
den normalen HTTP-Pfad ausgeführt: echte Producer-, Verifier-, Repair- und erneute
Verifier-Aufrufe, Analyse technisch erfolgreich, 39.712 Tokens und protokollierte Kosten
0,078192 USD. Die historischen Offline-Analysen blieben erneut unverändert. Der
konfigurierte Standardtransport mit `deepseek/deepseek-v4.1-flash` beantwortete zusätzlich
einen realen kurzen Verbindungstest. Kein Scope und keine fachliche Freigabe wurden
bei diesen technischen Verbindungstests bestätigt.

Die Einstiege A/B/C wurden im Browser geöffnet; die Solo-Seite wurde bei 1440×1000
geprüft. Ein zweiter Start verwendete denselben vorhandenen Worker-Supervisor weiter.
Die Vorbereitung akzeptiert auch UTF-8-Passwortdateien mit Windows-BOM; zufällige
Passwörter werden über eine mit Windows PowerShell kompatible Kryptografie-API erzeugt.
