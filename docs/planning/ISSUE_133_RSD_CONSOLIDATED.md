# Issue #133 – konsolidierte fachliche Validierung A–D

> Historischer Bericht vor der methodischen Produktnacharbeit. Der aktuelle
> [konsolidierte Abnahmebericht](ISSUE_133_METHODICAL_ACCEPTANCE.md) dokumentiert
> Änderungen, erneute Modellprüfungen und die weiterhin nicht erfüllte Gesamtabnahme.

Stand: 21.10.2026, Europe/Berlin. Produktstand:
`095062aa52efe5b2a9a3770b6bd04b1a3f41907e`.
Auftrag: [GitHub #133](https://github.com/Satte882/KI-Ideenwerkstatt/issues/133).

**Entscheidung: fachlich noch nicht abgenommen; Issue offen lassen.**
Die Anwendung kann aus allen vier natürlichen Problembeschreibungen selbstständig
strukturierte Discovery-Entwürfe erstellen. Die untersuchten Ergebnisse belegen
jedoch keine ausreichend fundierte, lösungsoffene und umsetzbare Endentscheidung.
Der Modellprüfer akzeptiert mehrfach unbelegte oder widersprüchliche Aussagen.
Nachweise für Lösungsauswahl, Umsetzung und Wirkung fehlen weiterhin.

**Alle Eingaben sind ausdrücklich synthetisch.** Keine Aussage beschreibt ein
festgestelltes Problem der RSD Touristik GmbH. Es wurden keine Unternehmensursache,
Geschäftskennzahl, Pilotwirkung oder menschliche Freigabe erfunden.

## 1. Was gegenüber dem Erstbericht neu ist

Der [Erstbericht](ISSUE_133_RSD_VALIDATION.md) dokumentiert eine Offline-Probe A und
123 bestandene Mechanismen-/Regressionstests. Deren Ergebnisse bleiben erhalten.
Die Tests wurden nicht erneut ausgeführt; seitdem gab es keine Produktänderung.

Die Prüfung der lokalen Konfiguration ergab einen vorhandenen OpenRouter-Schlüssel.
Das frühere `not_configured` war durch den Offline-Runner absichtlich erzeugt worden
und ist **kein Befund über eine fehlende lokale Providerkonfiguration**.
Nach der ausdrücklichen Nutzungsfreigabe des Nutzers („du hast die freigabe“)
wurden echte Modellaufrufe innerhalb der Anwendung ausgeführt.

Discovery verwendet in diesem Stand effektiv den vorhandenen Default
`google/gemini-3.6-flash`. Das allgemeine `OPENROUTER_MODEL` ist zwar auf
`deepseek/deepseek-v4.1-flash` gesetzt, wird für diese Discovery aber durch den
Default in `config/settings/base.py` übersteuert. Es wurde kein anderes Modell
gewählt. Die öffentliche Modellliste des Providers bestätigte Preise und
Unterstützung strukturierter Ausgaben; alle Antworten nennen das Discovery-Modell.

## 2. Teststrategie, Isolation und Grenzen

- Vier Fälle mit den unveränderten Ersttexten aus
  [Szenarien und Testkontexten](ISSUE_133_RSD_SCENARIOS.md).
  Keine Kontextkarte, Ursache, Lösung oder Kennzahl im ersten Request.
- Danach je Fall genau eine faktische Antwortrevision auf tatsächlich gestellte
  Modellfragen. Nur passende synthetische Karten beziehungsweise deren Teilinformationen;
  unbekannte Fakten bleiben unbekannt. Keine redaktionelle Reparatur der Modellantworten.
- A: A-K1, A-K2 als konkretes Informationsbeispiel und A-K3 zur unbekannten Häufigkeit.
  B: B-K2/B-K3 zu Ablauf-/Zeitfragen und B-K1 zum Zielrahmen.
  C: C-K2 zu Kanal/Kontaktdaten. D: D-K1 zu Beteiligten und Kommunikationsmitteln.
  C-K1/C-K3 und D-K2/D-K3 wurden nicht pauschal freigegeben.
- Bestehende Inbox-/Discovery-Views, Formulare, Services, Prompts, Schemas,
  Quoten, Verifier und begrenzter Repair unverändert. Der Teststarter beobachtet
  den echten Providertransport und erfindet keine Antworten.
- Eigene SQLite-Datenbank und Quellenablage je Fall unter `work/issue133-live/`;
  ausschließlich synthetischer Business Owner, kein Superuser. Keine lokale oder
  produktive PostgreSQL-Datenbank verändert. Private Datenbanken sind kein Deliverable.
- Gemeinsame Testgrenze 5 USD. Vor jedem Aufruf konservative Reservierung aus
  aktuellen Katalogpreisen, Eingabebytes und maximalen Ausgabetokens mit Faktor 10.
  Provider-Istkosten ersetzen bekannte Reservierungen. Das ist die Teststeuerung,
  keine Änderung des Providerkontos oder des Produktbudgets.
- Kein Submit einer verbindlichen Scope-/Fokusbestätigung, Ursachenvalidierung,
  Lösungspräferenz, Freigabe, Übergabe oder Lifecycle-Entscheidung. Die Providerfreigabe
  wird nicht als fachliche Bestätigung später erzeugter Inhalte interpretiert.
- Keine neue Browser-UX-Abnahme, kein PostgreSQL-Locktest, keine statistische
  Zuverlässigkeitsmessung und kein Vergleich verschiedener Modelle.

Die Fallfolge der Erstläufe war A, B, C, D. Bei den letzten Klärungsläufen
überlappten C und D entgegen der geplanten Reihenfolge durch einen Fehler in der
Teststeuerung. Die Falldaten blieben getrennt. Die 18 vollständigen Aufrufnachweise
wurden aus gesicherten Ledgerständen ohne erneuten Modellaufruf zusammengeführt;
ihre Kosten stimmen je Fall bis auf die Rundung des Datenbankfelds mit den
gespeicherten Analysen überein. Ursprüngliche Sequenznummern überschneiden sich;
`call_id` ist eindeutig. Der Teststarter besitzt jetzt eine exklusive Laufsperre;
deren Abweisung wurde ohne Provideraufruf geprüft. Aus diesen Läufen wird keine
vergleichende Latenz-/Performanceaussage abgeleitet.

## 3. Tatsächliche Modellleistung und Kosten

| Fall | Revisionen | Echte Aufrufe | Vorhandener Repair | Provider-Istkosten USD | Anwendungsstatus am Ende |
|---|---|---:|---|---:|---|
| A – Kundenservice | Ersttext + eine Klärung | 4 | keiner | 0,06813225 | beide Analysen `success`, Verifier `approved` |
| B – Geschäftsführung | Ersttext + eine Klärung | 4 | keiner | 0,06398100 | beide Analysen `success`, Verifier `approved` |
| C – reisende Person | Ersttext + eine Klärung | 6 | einmal nach Verifierbefund | 0,09250200 | nach Repair `success`, Verifier `approved` |
| D – lokaler Partner | Ersttext + eine Klärung | 4 | keiner | 0,05113800 | beide Analysen `success`, Verifier `approved` |
| Gesamt | acht Analysefassungen | **18** | ein Repair | **0,27575325** | technische Vertrags-/Modellprüfung bestanden |

Ein Erstlauf umfasst jeweils Generator und Verifier. Die Klärungsrevision C
umfasst Generator, Verifier, Repair und erneuten Verifier. Es gab keinen manuellen
Neustart bis zu einem besseren Ergebnis. Alle Revisionen und Antworten sind erhalten.
Der Verifier ist ein getrennter Aufruf **desselben Modells**, keine unabhängige
menschliche Fachprüfung. `success / approved` ist daher kein fachliches Abnahmeurteil.

## 4. Fachliche Befunde pro Fall

### A – brauchbares Problemgerüst, zu starke Ursachenaussagen

**Selbst erkannt:** Suche in Buchung und E-Mails, interne Rückfragen und wartender
Kunde. Der vorgeschlagene Service-Wertstrom passt grundsätzlich zum Anlass. Das
Modell fragt nach den konkret fehlenden Informationen und der Rückfragehäufigkeit.
Nach der Klärung übernimmt es die synthetischen Zeiten 09:00/10:00 und die unbekannte
Gültigkeit; Messwerte und Kostendaten werden nicht erzeugt.

**Nicht ausreichend fundiert:** Schon R0 nennt `focus.rationale` die Suche den
„primären Engpass“ und setzt `economic_potential = high`, ohne Mengen oder Zeitbasis.
R1 behauptet dort weiter, die Recherche sei der Engpass, der „zu widersprüchlichen
Angaben“ führe. Das vertauscht eine Tätigkeit mit einer unbelegten Entstehungsursache.
Die Hauptursache steht zwar im Hypothesenfeld, definitive Aussagen treten aber auch
in anderen Diagnosefeldern auf. Der Process Scope reicht weiterhin vom Anruf bis
zur Auskunft, während der Fokus nur auf Recherche liegt. Beide Verifier akzeptieren das.

**Endpunkt:** Diagnoseentwurf; führende Information, Ursachen und wirtschaftlicher
Hebel bleiben ungeklärt. Kein Nachweis, dass eine zentrale Ansicht oder KI nötig ist.

### B – Ziel erkannt, verfrühte Verengung und inkonsistenter Klärstatus

**Selbst erkannt:** Ziel mehr Buchungen bei begrenztem Personalaufbau; Bedarf an
Ablauf-, System- und Zeitinformationen. Nach der Klärung werden fehlende Daten und
die konkurrierenden Aussagen aus Verkauf/Reiseorganisation sichtbar übernommen.

**Nicht ausreichend fundiert:** R0 verschärft den Ersttext zu der als Fakt bezeichneten
Aussage „Ein kontinuierlicher Personalaufbau ... ist ausgeschlossen“. Außerdem wird
Buchungserfassung ohne Vergleichsmessung fokussiert. Nach der Klärung wechselt der
Fokus auf Rückfragen im Verkauf; dessen Aufwand gilt nun als vermuteter primärer
Engpass, obwohl die konkurrierende Reiseorganisation nicht belastbar verglichen wurde.
`economic_potential` und Problemintensität bleiben `high`.

In **beiden Revisionen** steht eine Frage nach dem genauen Ablauf und den eingesetzten
Systemen auf `clarifications[].blocking = true`; gleichzeitig lautet der Verifierstatus
`approved` und die gespeicherte Analyse `success`. Die Materialisierungslogik prüft
diesen Boolean nicht separat, sondern unter anderem den Analyse-/Verifierstatus.
Das ist eine belegte Inkonsistenz der angezeigten Entscheidungsreife, kein in diesem
Test ausgeführter Gate-Bypass. Es wurde keine Scopebestätigung eingereicht.

**Endpunkt:** Noch kein belastbar ausgewählter Untersuchungsbereich. Erforderlich
sind Ablaufaufnahme und vergleichbare Aufwands-/Qualitätsdaten, kein weiterer
sprachlicher Klärungszyklus mit denselben unbekannten Fakten.

### C – sichtbarer Repair und einfachere Kläroption, Kundenergebnis bleibt offen

**Selbst erkannt:** widersprüchliche Treffpunktangaben, unsicherer Ansprechpartner
und Rückfrage nach Kanal/Kontaktdaten. In R0 wird zugleich als Ausnahme unbelegt
gesetzt, es seien keine Kontaktdaten auffindbar. Die passende Karte liefert eine
vorhandene, noch nicht angerufene Telefonnummer und zeitweise fehlenden Internetempfang.

**Wirksame Kontrolle:** In der Klärungsrevision moniert der Verifier
`SCOPE_NOT_NARROWER_THAN_VALUE_STREAM`. Der vorhandene einmalige Repair grenzt den
Process Scope ein; die anschließende Modellprüfung akzeptiert ihn. Der finale Entwurf
behandelt einen Anruf ausdrücklich als mögliche Klärung, **falls** die Nummer erreichbar
ist, und behauptet weder deren Erreichbarkeit noch einen gültigen Treffpunkt.
Das ist eine konkrete einfache organisatorische Handlungsoption im Entwurf.

**Grenze:** Es ist kein Vergleich mehrerer SolutionOptions und keine bestätigte
No-AI-Präferenz. Der Endzustand ist Kontaktvorbereitung, nicht die verlässliche
Klärung von Ort/Zeit. Finale Treffpunktabstimmung wird im Entwurf sogar aus dem
Scope ausgeschlossen; das ursprüngliche Kundenergebnis ist damit nicht erreicht.
Unbekannte Erreichbarkeit wird zugleich im Bottleneckfeld geführt, ohne als tatsächliche
Ursache nachgewiesen zu sein. Die nächste Prüfung muss eine befugte Auskunft liefern.

### D – Partnerbezug verbessert, Vollmacht nicht systematisch erfragt

**Selbst erkannt:** mehrere Kommunikationspartner, fehlender sicherer Informationsstand
und Unsicherheit über eine Busumbestellung. Nach D-K1 werden Reiseorganisation,
lokaler Partner, Busunternehmen und Reiseleitung passend unterschieden. Die Regel
„Eine Anfrage ist noch kein bestätigter Auftrag“ wird korrekt übernommen; das Modell
löst keine Bestellung aus. Der zu breite anfängliche Busreise-Scope wird auf
Änderungskoordination und Entscheidungsvorbereitung eingegrenzt.

**Nicht ausreichend fundiert:** Als Bottleneck ergänzt R1 „ohne zentralen
Bestätigungsnachweis“, obwohl ein fehlender zentraler Nachweis nicht festgestellt
wurde. Die Modellfragen betreffen vor allem Kommunikationsmittel und Empfängerliste.
Die entscheidende Vollmacht für Bestellung/Mehrkosten wird in den ausgegebenen
Klärfragen nicht ausdrücklich abgefragt. D-K2/D-K3 bleiben deshalb in diesem Lauf
unveröffentlicht; sie wurden nicht nachträglich eingespeist, um diesen Befund zu verdecken.

**Endpunkt:** Koordinationsentwurf ohne vollständige Entscheidungs-/Freigaberegeln.
Eine zentrale Plattform oder KI ist daraus nicht als beste Lösung ableitbar.

## 5. Quellen und Traceability

Inbox-Originale bleiben unverändert; die Anwendung speichert Antworten als
versionierte `session.answers.corrections`. Analysen tragen `source_revision`,
`source_hash`, Prompt-/Schema-Version und Discovery-Snapshot-ID. Alle ausgegebenen
Evidence-Referenzen der untersuchten Entwürfe lauten `U0` und sind auf den jeweiligen
Nutzereingabestand zurückführbar. Das belegt Herkunft, **nicht die Wahrheit jeder Ableitung**.

Die Kontextkarten kamen über das vorhandene Korrekturfeld und damit gesammelt in
`U0`, nicht als getrennte Dokumentquellen. Insbesondere bleibt A-R1
`contradictions = []`, obwohl der Zeitwiderspruch im Beobachtungstext erhalten ist.
Der aktuelle Contract verlangt für einen strukturierten Widerspruch zwei verschiedene
Quellenreferenzen. Dieser Lauf prüft deshalb die Erhaltung eines berichteten
Widerspruchs, nicht den vollständigen Abgleich zweier unabhängig hochgeladener Dokumente.
Die Zuordnung von Karten zu Antworten steht im Bericht und im Korrekturtext;
eine feinere Karten-Provenance wurde nicht als Produktleistung behauptet.

Es wurden keine Discovery-Entwürfe in verbindliche Domainobjekte materialisiert.
Der frühere manuelle A-Zweig besitzt weiterhin nur die im Erstbericht dokumentierte
Herkunftslücke. Er wurde nicht als Fortsetzung der echten Modellläufe verwendet.

## 6. Menschlicher Aufwand und erforderliche Unterstützung

Je Fall gab es drei skriptgesteuerte Eingabeaktionen: Inbox anlegen, Discovery starten,
eine Antwortrevision einreichen. Die Anwendung formulierte Fragen und Entwürfe;
der Testagent musste passende Karten auswählen, Antworten zusammenstellen und
sämtliche Ergebnisse fachlich gegenprüfen. C benötigte zusätzlich den autonomen Repair.

**Es wurde keine reale menschliche Arbeitszeit gemessen.** Skriptlaufzeiten,
Providerwartezeiten und diese Eingabeanzahl sind kein Nachweis für eingesparte
Mitarbeiterminuten, geringe Bedienlast oder wirtschaftliche Wirkung. Gemäß dem
vorhandenen AP4 Measurement Contract bleibt `human_time_measured = false`.
Echte Menschen müssen insbesondere die unbelegten Ursachen-/Engpassaussagen erkennen,
den Scope bestätigen, die Daten beschaffen und spätere Entscheidungen verantworten.

## 7. Abnahme gegenüber #133 und dem Folgeauftrag

| Kriterium | Belegter Stand | Abnahme |
|---|---|---|
| Natürliches Problem wird strukturiert | A–D liefern passende Grundgerüste und Rückfragen | teilweise erfüllt; keine Endentscheidung |
| Annahmen bleiben Annahmen | eigene Hypothesenfelder vorhanden; definitive Ableitungen auch in anderen Feldern | nicht durchgängig erfüllt |
| Fehlende Fakten sichtbar | Zeit-/Datenlücken und unbekannte Erreichbarkeit bleiben erkennbar | weitgehend im Discovery-Entwurf; semantische Übertreibungen bleiben |
| Passender Value Stream / Fokus | A/C grundsätzlich passend; B früh verengt; D verbessert nach Klärung | teilweise erfüllt |
| Herkunft über gesamten Lifecycle | Eingabe-/Revisionsherkunft belegt; keine materialisierte Domain-/Lifecycle-Kette | nicht nachgewiesen |
| Organisatorische/klassische Lösung besser als KI erkennen | C nennt bedingten Telefonanruf; keine KI erzwungen | Alternativenvergleich und No-AI-Auswahl nicht erreicht |
| Perspektive konsistent | Rollen nach Klärung besser; B verengt Managementziel, D anfangs zu breiter Scope | teilweise erfüllt |
| Fundierte, umsetzbare Entscheidung | keine Ursache validiert, keine begründete Lösungspräferenz | nicht erreicht |
| Reale menschliche Arbeitsersparnis | keine gemessene Teilnehmerzeit | nicht nachgewiesen |

**Kein aktueller Provider- oder Freigabeblocker für diese 18 Aufrufe.** Der konkrete
verbleibende Blocker ist die fachliche Evidenz: tatsächliche Abläufe, Häufigkeiten,
Aufwände, gültige Informationsstände und Entscheidungsrechte fehlen. Zusätzlich
benötigen die erzeugten, teilweise fehlerhaften Scope-/Diagnoseentwürfe eine
verbindliche fachliche Prüfung. Ein weiterer Modellzyklus könnte diese Fakten und
Autorität nicht ersetzen. Deshalb keine weiteren künstlichen Schleifen.

Nachgelagert fehlen Ursachenvalidierung, vollständig bewertete Alternativen,
gegebenenfalls KI-Use-Case, Governance, unabhängige Freigaben, Delivery-Handover und
reale Pilot-/Betriebsnachweise. Die vorhandenen grünen Regressionen belegen die
Mechanismen, dürfen diese fehlende Szenarioevidenz aber nicht ersetzen.

Empfehlung: Die Anwendung für diese Fälle derzeit als **begleitete Discovery**
einordnen. Vor einer fachlichen Abnahme zuerst die konkreten Befunde zu Grounding,
blockierenden Klärfragen und Scope gegen die vorhandene Policy fachlich entscheiden.
Danach gezielt den tatsächlich blockierten Abschnitt mit geeigneten Quellen und
echter Scope-/Ursachenprüfung fortsetzen. Kein Anlass für einen Architekturumbau
oder neue Features aus diesem Test allein.

## 8. Reproduktion und Nachweispaket

- `artifacts/issue133/live/A.json` bis `D.json`: beide gespeicherten Analysefassungen,
  Erstinput, Antworten, Source-Hashes, Verifier und Status pro Fall.
- `artifacts/issue133/live/provider-ledger.json`: alle 18 echten Requests, unveränderten
  Modelltexte, Nutzungs-/Kostendaten und eindeutigen `call_id`; keine Zugangsschlüssel.
- `results-summary.json`, `protocol.json`, `provider-preflight.json`,
  `model-metadata.json` im gleichen Verzeichnis: Kostenabgleich, Grenzen und Konfiguration.
- Historische Offline-Evidenz bleibt unter `artifacts/issue133/` erhalten.
- `scripts/run_issue133_live.py`: ausdrücklicher CLI-Opt-in, getrennte Datenbanken,
  Kostenreservierung, Wiederverwendung vorhandener Ergebnisse und Laufsperre.
  Kein automatisch von pytest/CI gestarteter kostenpflichtiger Test.

Für einen vorhandenen Fall zeigt folgender Aufruf den gespeicherten Stand ohne
erneuten Modellaufruf; in einer frischen Testablage entstehen echte Kosten und es
ist erneut die autorisierte Providerkonfiguration erforderlich:

```powershell
.\.venv\Scripts\python.exe scripts/run_issue133_live.py --case A --confirm-real-provider
```

Vor einem frischen Lauf muss `work/issue133-model-metadata.json` mit den passenden
Preisdaten vorhanden sein (im Paket: `artifacts/issue133/live/model-metadata.json`);
Preise vor neuer Ausführung erneut aus der offiziellen Modellliste prüfen.
Eine Antwort kann einmal über `--correction-file <pfad>` eingereicht werden.
Die tatsächlich verwendeten Antworten stehen vollständig in den exportierten
`session_answers`, nicht in nachträglich erfundenen Quellen.

Neue zielgerichtete Prüfungen: Ruff Check und Formatprüfung der drei Python-Dateien
bestanden; exklusive Laufsperre ohne Modellaufruf geprüft; 18 Rohantworten vollständig,
Kosten pro Fall mit der Anwendung abgeglichen. Die früheren 123 bestandenen Tests
bleiben historische Mechanismen-Evidenz und wurden nicht unnötig wiederholt.

**Abschlussentscheidung:** Nachweise und konkrete Blocker in #133 dokumentieren;
keinen Abnahme-PR mergen und das Issue nicht schließen. Eine erfolgreiche
Vollabnahme oder menschliche Fachfreigabe liegt nicht vor.

Diese Entscheidung samt Einzelbefunden, Kosten und Nachweisverzeichnis wurde in
[Issue-Kommentar 6313951190](https://github.com/Satte882/KI-Ideenwerkstatt/issues/133#issuecomment-6313951190)
veröffentlicht und anschließend wortgleich zurückgelesen. Das Issue bleibt offen.
Die lokale Ergebnissammlung wurde nicht als abgenommener Stand committed;
PR-, CI-, Merge- und Schließschritte wurden wegen der nicht erfüllten fachlichen
Abnahme nicht ausgelöst.
