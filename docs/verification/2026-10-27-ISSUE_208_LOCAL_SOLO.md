# Lokaler Solo-Praxistest – #208

Basis: `main` / `b91260d`, nach #202. Dies ist eine technische lokale
Erprobungsumgebung für eine Person. #161 bleibt unverändert und zurückgestellt.
Getrennte Konten bedeuten hier keine unabhängigen menschlichen Testpersonen.
Keine Nutzerzeiten, realen Modellqualitäten, Wirkungen oder Abnahmen werden behauptet.

## Start und Zugang

Im Repository `Satte882/KI-Ideenwerkstatt` unter PowerShell:

```powershell
.\scripts\start-solo.ps1 -Prepare
```

PostgreSQL muss lokal erreichbar sein (standardmäßig Port 5433, beispielsweise der
vorhandene lokale Compose-Datenbankcontainer). Das Kommando legt ausschließlich
die Datenbank `ki_radar_solo` an, wendet die vorhandenen Migrationen an und richtet
die Testkonten ein. Es löscht keine Daten und überschreibt bestehende Passwörter
oder Rollen nicht. Erneutes Vorbereiten erhält deine Versuche. Ein bestehender
Testbenutzer mit unerwarteten Rechten führt zum Abbruch statt zur stillen Korrektur.

Danach genügt `.\scripts\start-solo.ps1`. Stoppen mit Strg+C. Einstieg:
`http://127.0.0.1:8000/solo/`. Master: `solo_master`; das zufällige Passwort liegt
unter `secrets/solo-master-password.txt`, außerhalb von Git. Nicht veröffentlichen.
Die bereits vorhandene normale Datenbank `ki_radar` bleibt unverändert.

`SOLO_DATABASE_PORT` und optional `SOLO_DATABASE_NAME` konfigurieren die eigene
lokale Datenbank; der Name muss mit `ki_radar_solo` beginnen. Der explizite
Settings-Einstieg ist `config.settings.solo`. Ein bloßes Umgebungsflag aktiviert
den Rollenwechsel in normalen Entwicklungs-/Produktionssettings nicht.

## Rollenwechsel

Auf jeder lokalen Testseite stehen Modus und tatsächlicher Benutzer sichtbar.
Über **Testrolle wechseln / Testfälle** zur Auswahl wechseln und bestätigen:

| Identität | Vorhandene Fachgruppe |
| --- | --- |
| `solo_owner` | Business Owner |
| `solo_coordination` | KI-Koordinator, etwa für strukturierte Bewertung |
| `solo_review` | Zweiter KI-Koordinator für unabhängige Freigabe nach den bestehenden Regeln |
| `solo_technical` | Technischer Administrator ohne Superuser- oder Staff-Flag |
| `solo_reader` | Leser |

Der Master dient nur der Testverwaltung. Schreibende Fachaktionen sind für ihn
gesperrt. Ein Wechsel führt einen echten Django-Login in die gewählte Identität
aus, verändert keine Gruppen und erhöht deren Fachrechte nicht. Die Fachservices
sehen und auditieren diese Identität. Der bewertende Benutzer kann weiterhin nicht
seine eigene positive Entscheidung freigeben. Der technische Administrator behält
exakt die bestehenden Fachregeln; es gibt keinen zusätzlichen Test-Override.

Die Testkonten haben keine direkt nutzbaren Passwörter. Eine auf die Masteranmeldung
zurückführbare, signierte Wechselberechtigung bleibt höchstens vier Stunden gültig.
Abmeldung, Master-Passwortänderung und veränderte Testrechte entwerten sie.
Wechsel werden mit Master-, vorheriger und effektiver Benutzer-ID protokolliert.
Nach Ablauf wieder als Master anmelden.

Alle Tabs desselben Browsers verwenden dieselbe aktuelle Identität. Nach einem
Wechsel andere Tabs neu laden; alte Formulare können wegen rotierendem CSRF-Token
abgelehnt werden. Für den Solo-Test möglichst einen Tab verwenden.

## Drei Fälle selbst durchspielen

1. **A – problemgetriebene Kundenbetreuung:** Business Owner wählen, auf der Solo-Seite
   eine neue A-Discovery starten. Das unveränderliche synthetische Quellenpaket ist
   bereits zugeordnet. **Analyse erneut starten**, Testentwurf lesen, anschließend
   selbst Scope/Fokus übernehmen. Die erzeugte Prozessanalyse manuell bearbeiten,
   organisatorische, regelbasierte und KI-Alternativen gegeneinander abwägen.
   Vorhaben, Geschäftsergebnis, Beitrag, Wirkannahme und Messabsicht selbst vorbereiten;
   fehlende Messwerte offen lassen. Eine Ursachenannahme ausdrücklich als Annahme
   einordnen. Eine begründete KI-Auswahl führt in den normalen Use-Case-Pfad.
2. **B – strategisches Servicewachstum:** Neue B-Discovery starten. Ist-Ablauf,
   Einzelursache, Baseline und globale Screeningwerte bleiben offen. Den vorbereiteten
   menschlichen Untersuchungsrahmen selbst prüfen. Im normalen Prozess-/Outcome-Pfad
   strategischen Ursprung und begrenzten Beitrag bestätigen. Alternativen manuell
   vergleichen; eine begründete organisatorische Auswahl erzeugt keinen künstlichen
   KI-Use-Case. Geschäftswirkung bleibt bis zur tatsächlichen Messung ungeklärt.
3. **C – direkte interne Wissenssuche:** Den direkten Use-Case-Einstieg auf der Solo-Seite
   verwenden. Synthetischen Anwendungsfall und eigene Outcome-/Messabsicht erfassen,
   ohne eine Idee oder Discovery künstlich anzulegen. Als KI-Koordination die Prüfung
   starten und die strukturierte Bewertung vornehmen; für die zulässige Freigabe zur
   getrennten Prüferidentität wechseln. Fehlende Governance-/Outcome-Voraussetzungen
   werden weiterhin blockiert. Kein Pilot, Go-live oder Geschäftserfolg wird vorgegeben.

Arbeitsobjekte über den normalen Arbeitsvorrat, die Analyseübersicht oder das
Use-Case-Register wieder öffnen. Es werden keine fertigen Lösungsentscheidungen,
Freigaben, Pilotmesswerte oder Ergebnisse vorbereitet.

## Offline-Grenze und Sicherheit

Die Transportgrenze fängt im expliziten Solo-Modus sämtliche OpenRouter-Aufrufe
ab. Ausschließlich die unveränderten Pakete A/B-v1 einschließlich Quelleninhalt,
Eingangstext, Kontext und strategischem Scope erhalten deterministische Discovery-
Testentwürfe und einen passenden technischen Test-Verifier. Dieser ist kein
unabhängiger Modell- oder Fachprüfer. Der gespeicherte Modellname lautet
`solo/offline-fixture-v1`; die normale Transportkategorie bleibt OpenRouter.
Die bestehende Schema-, Quellen-, Methodik- und Übernahmevalidierung läuft weiter.

Fremde Eingaben, Zusatzquellen, Korrekturen oder fremde Verifier-Entwürfe werden
abgelehnt. Es gibt keinen Rückfall auf einen Live-Provider. Frei formulierte
Discovery-Experimente außerhalb dieser Pakete sind somit ein konkreter Offline-
Blocker. Auch vertiefende Investigation, Optionsgenerierung, AP2-Generatoren und
sonstige KI-Tasks sind offline nicht verfügbar. Sie dürfen nicht als erfolgreich
getestet gelten. Die normale manuelle Prozess-/Alternativen-/Outcome-/Entscheidungs-
strecke bleibt ausführbar. Keine zusätzlichen Worker mit echten Providern starten.

Nur Loopback-Bindung, keine Freigabe ins LAN, kein Reverse Proxy und kein Deployment
dieser Settings. Wechsel und Einstieg werden zusätzlich bei nichtlokaler Adresse,
fremdem Host, falschem Settings-Modul, fehlendem Debug-Modus, fremder Datenbank oder
fehlender Masterberechtigung verweigert. Produktionsrechte und fachliche Freigaben
werden nicht geändert. Der reguläre Organisationskatalog bleibt ebenfalls unverändert:
die eindeutig als synthetisch benannte Organisation benutzt ausschließlich in der
eigenen Solo-Datenbank die normale aktive Katalogklasse, die Discovery benötigt.

## Technische Verifikation

22 neue PostgreSQL-Fälle: tatsächliche Identitäten und Gruppen, Master-Schreibsperre,
Rollenrechte und unabhängige Freigabe, ungültige/abgelaufene Berechtigung, Passwort-
und Rollenänderung, Abmeldung, POST/CSRF, nichtlokale/ anonyme Requests,
idempotente Vorbereitung, Isolation und fehlende Routen im normalen Betrieb.
A/B laufen über reale Discovery-, Analyse-, Materialisierungs- und Auswahlrouten;
eine Netzwerksperre im Test beweist, dass kein echter Provider aufgerufen wird.
Danach aktueller A-KI-Handoff und B-Non-KI-Auswahl ohne erfundene Baseline/Ursache.
Veränderte Pakete, Zusatzquellen, fremde Scope- und Verifier-Eingaben sowie ein
Modusflag ohne isolierte Settings werden ebenfalls ausdrücklich abgelehnt.
Der C-Fall prüft die neue Outcome-Kohorte: ohne Zuordnung keine Freigabe,
danach weiterhin keine Selbstfreigabe durch den Bewerter, schließlich positive
Entscheidung unter der getrennten Prüferidentität. Abschließend erneut bestanden.

Gemeinsam mit den Regressionen zu #166, #183/#198 und #189/#202: **77 bestanden**.
Lockfile, Lint/Format, Django-System-/Migrationsprüfung und Bandit sowie die
vollständige PostgreSQL-CI werden im PR dem jeweils geprüften Commit zugeordnet.
Browserkontrolle prüft echte lokale Anmeldung, Rollenwechsel, synthetische Discovery
und direkten Einstieg. Dies sind technische Agentenkontrollen, keine Beobachtungen
eines unabhängigen Fachanwenders und keine Änderung des Status von #161.

Die lokale Instanz wurde mit eigener vollständig migrierter Datenbank gestartet;
Systemprüfung und `/health/live` erfolgreich. Die Browserkontrolle zeigt Master-
Login, echte Ummeldung, A/B-Offline-Auswertung mit sichtbaren Unknowns und den
direkten C-Intake. Das Browser-Prüffenster wurde auf 1440×1000 eingestellt; kein
horizontaler Überlauf. Vorbereitet sind Konten und Quellenpakete, keine fachlichen
Entscheidungen oder Freigaben in der tatsächlichen Solo-Datenbank.
