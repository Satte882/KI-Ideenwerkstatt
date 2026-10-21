# Issue #133 – methodische Evidence-to-Decision-Abnahme

Stand: 21.10.2026. Ausschließlich synthetische Touristikfälle; keine Aussagen über
tatsächliche RSD-Probleme, Unternehmensursachen, Geschäftszahlen oder Pilotwirkungen.
Der Bericht konsolidiert die ursprüngliche negative Prüfung und die anschließende
Produktnacharbeit. Der frühere [Bericht](ISSUE_133_RSD_CONSOLIDATED.md) bleibt als
historischer Befund erhalten.

**Nicht vollständig abgenommen. Issue #133 bleibt offen; kein Merge als erledigter
Testauftrag.** Die Anwendung wurde verbessert und die Quellenläufe A–D enden begründet
offen. Der Originalfehler B wird aber trotz gezielter Nacharbeit nicht vollständig
automatisch korrigiert. Zudem fehlt ein erfolgreicher echter Lösungs-Critic-/Repair-
Durchlauf. Der verbleibende Blocker ist reproduzierbar fachlich und technisch belegt;
ein realer RSD-Pilot oder eine zusätzliche menschliche Produktivfreigabe fehlen hier
nicht als Abnahmevoraussetzung.

## Auftrag und unabhängiger Bewertungsmaßstab

Geprüft wird, ob natürlich beschriebene Probleme nachvollziehbar zu einem fachlich
gerechtfertigten nächsten Entscheidungsstand führen. Eine begründete Zurückstellung
ist ein zulässiges Ergebnis. Reale Unternehmensmessungen, Pilotdurchführung und
produktive Freigaben sind ausdrücklich kein Bestandteil dieser synthetischen Abnahme.

Die Kriterien wurden **vor den neuen Modellaufrufen** in
[`criteria.json`](../../tests/fixtures/issue133_methodology/criteria.json) festgelegt.
Jeder Lauf speichert deren SHA-256. Bewertet werden Quellenwahrheit in allen Feldern,
Beobachtung/Hypothese/Ursache, Prozessgrenze, wirksame Rückfragen, automatische
Korrektur und erneute Prüfung, ernsthafte Nicht-KI-Alternativen und unveränderte
menschliche Entscheidungsrechte. Die Auswertung erfolgt durch Quellenvergleich und
Domain-Prüfungen außerhalb des erzeugenden Modells; sie ist keine RSD-Fachfreigabe.

Die [natürlichen Ersttexte A–D](ISSUE_133_RSD_SCENARIOS.md) bleiben unverändert.
Ergänzende Fallakten liegen getrennt unter
[`tests/fixtures/issue133_methodology/`](../../tests/fixtures/issue133_methodology/).
Sie werden erst nach dem initialen Discovery-Lauf auf passende Fragen zu Ablauf,
Beispielen, Dokumenten, Kontakten oder Vollmachten freigegeben. Der Teststarter speichert
vorherige Modellfragen, freigegebene Dateihashes und den Quellen-Snapshot. Ein späterer
Quellenlauf ist keine nachträgliche Anreicherung des natürlichen Erstinputs.

## Tatsächlich umgesetzte Änderungen

- Die vorhandenen Discovery-Generator-, Verifier- und Repair-Prompts verlangen
  Quellenwahrheit auch in Fokusbegründungen, Ausnahmen, Übergaben und Trade-offs.
  Symptome belegen keine Hauptursache. Unbekannte Erreichbarkeit ist kein Ausfall;
  eingeschränkte Einstellungsmöglichkeiten sind kein Einstellungsverbot. Qualitative
  Wirkungen sind ohne Beleg bedingte Erwartungen.
- Konservative serverseitige Prüfungen ergänzen den bestehenden Contract um die
  konkret beobachteten Kausal-/Modalitätsfehler und kopierte vollständige Phasenketten.
  Diese Sprachmuster sind keine allgemeine Wahrheitsmaschine. Semantische Prüfung und
  externe Quellenbewertung bleiben erforderlich.
- Bei einem methodisch fehlerhaften, strukturell lesbaren Generatorentwurf sammelt
  derselbe Verifier vor der **einen** Reparatur auch die semantischen Befunde. Die
  Reparatur muss den Zusammenhang korrigieren; anschließend prüft der Verifier erneut.
  Keine zusätzliche Reparaturschleife oder parallele Facharchitektur wurde eingeführt.
- `blocking=true` bleibt nach technisch positiver Prüfung entscheidungswirksam.
  Oberfläche und bestehender Materialisierungsservice verhindern die verbindliche
  Übernahme. Entwürfe bleiben zur Exploration lesbar. Historische Analysen werden nicht
  umgeschrieben; vor neuer Übernahme brauchen sie eine aktuelle Prüfung. Bereits
  abgeschlossene Materialisierungen bleiben idempotent erreichbar.
- Der bestehende Lösungsvergleich behält seine drei Kandidatenbahnen. Organisation,
  vorhandene Standardsoftware/klassische Regeln und Assistenz sind ernsthafte Optionen.
  Der Critic erhält jetzt auch nicht vom Generator zitierte Diagnosefelder einschließlich
  Ursachenhypothesen, bestätigter Ursachen und Validierungsstand. Fit und Nutzen dürfen
  nicht aus Hypothesen zu Tatsachen werden. Bestehende Quellen- und Statement-Verträge
  bleiben maßgeblich; gespeicherte ältere Vorschauen bleiben lesbar.

Aktive Discovery-Promptkennung: `ap1-methodology-v7`, Verifier `ap1-ver-method-v7`;
unveränderte Schemas `ap1-discovery-v1`/`ap1-discovery-verifier-v1`.
Lösungsgenerator/Critic/Repair: `1.3`/`1.3`/`1.1`, Schemas unverändert.
Die Kennungen passen in die bestehenden Datenbankfelder; keine Migration erforderlich.

## Versuchsaufbau und Grenzen der Autonomie

[`accept_issue133_methodology.py`](../../scripts/accept_issue133_methodology.py)
verwendet bestehende Inbox-/Discovery- und Lösungsservices, Quellensnapshots, Contracts,
Quoten sowie den realen Anwendungstransport. Je Fall bestehen eigene SQLite-Datenbank
und Quellenablage unter `work/issue133-methodology/`. Keine produktiven Datensätze wurden
verändert. Technische Regressionen laufen separat gegen einen eigens erstellten lokalen
PostgreSQL-17.5-Container mit blockiertem externem Netzwerk und leeren Provider-Schlüsseln.

Die historische echte Generatorantwort wird in `replay` unverändert eingespielt;
Verifier, Repair und erneuter Verifier sind echte neue Anwendungscalls. Das ist ein
Wiederverwendungstest einer realen Modellantwort, kein neuer natürlicher Erstlauf.
`fresh` erfasst den natürlichen Erstinput neu, `sources` liefert die Fallakten,
`revalidate` prüft unveränderte gespeicherte echte Entwürfe unter dem korrigierten
Vertrag. Wiederverwendung speichert Herkunfts-Call-ID und Hash ausdrücklich.

Die Lösungsprobe richtet aus dem Quellenentwurf eine kanonische **DRAFT**-Prozessanalyse
als Testfixture ein. Das ist ein manueller Testaufbau, keine autonome Materialisierung
oder Scopefreigabe. Bestätigte Ursachen bleiben leer. Die bestehenden Generator-/Critic-/
Repair-/Final-Critic-Services explorieren daran Optionen. Damit wird der Optionsmechanismus
geprüft, nicht eine selbstständig genehmigte durchgängige Produktentscheidung behauptet.
Bei B bleibt schon die Auswahl des zu untersuchenden Prozesses fachlich zurückgestellt.

Die Testleitung lieferte Ersttext und passende synthetische Akten, verglich Ergebnisse
mit den vorher festgelegten Kriterien und korrigierte nachgewiesene Produktfehler.
Sie redigierte keine Modellantwort zum Bestehen und bestätigte weder Ursache, Scope,
Lösungsvorzug noch reale Maßnahmen. Arbeitszeit- und Wirtschaftlichkeitsmessungen wurden
nicht als Abnahmemaßstab eingesetzt.

## Nacharbeit und erhaltene Negativnachweise

Alle Kalibrierungen und technischen Unterbrechungen bleiben unter
[`artifacts/issue133/methodology/`](../../artifacts/issue133/methodology/) erhalten.
Es wurde nicht nur der letzte positive Modelllauf ausgewählt:

- Frühe A-Reparatur korrigierte nur den Scope und ließ die unbelegte Hauptursache stehen.
- B/D zeigten, warum ein rein formaler Scope-Repair die einzige Korrekturmöglichkeit
  verbrauchen kann, bevor der Verifier die übrigen fachlichen Fehler benennt. Daraus
  folgt die gemeinsame Befundsammlung vor dem bestehenden einmaligen Repair.
- C-Quellenlauf v4 enthielt einen unbelegten ausschließlichen Klärweg sowie einen noch
  nicht ausgeführten Handoff. Calls 42–43 erkannten und reparierten diese Aussagen,
  einschließlich einer ausdrücklich möglichen statt behaupteten Telefonausnahme.
  Call 44 verweigerte jedoch die Anerkennung der nun ausdrücklich geplanten Übergabe.
  Diese falsche erneute Beanstandung führte zu einer gezielten Verifier-Kalibrierung;
  die Nichtkonvergenz wurde nicht nachträglich als Erfolg umetikettiert.
- D enthielt in einem Trade-off noch das unbedingte Wirkungsversprechen „sichert die
  Informationskette“. Das führte zur ergänzten Prüfung qualitativer Wirkungsbehauptungen.
- Ein Providerfehler und eine zu konservative Kostenreservierung unterbrachen Teile
  des ersten Durchgangs. Unvollständige technische Versuche wurden archiviert. C nutzte
  seine bereits bezahlte echte Generatorantwort weiter; separate Wiederaufnahmesitzungen
  verhindern, dass später freigegebene Quellen rückwirkend als Erstinput erscheinen.
- Das normale Tageslimit des synthetischen Kontos stoppte weitere Kalibrierung. Nur
  die isolierte Kampagne verwendet seitdem 80 User-/100 globale Calls pro Tag; Quoten
  werden weiter durchgesetzt. Die gemeinsame 3-USD-Grenze bleibt zusätzlich wirksam.
  Produktionswerte und Providerkonto wurden nicht verändert.

Das neue Budget wird getrennt von der vorausgegangenen 18-Call-Baseline geführt.
[`provider-ledger.json`](../../artifacts/issue133/methodology/provider-ledger.json)
enthält vollständige Requests, Antworten, Nutzung und eindeutige Call-IDs. Bei bekannten
Istkosten ersetzen diese die Reservierung. Für den fehlgeschlagenen Aufruf bleibt eine
Obergrenze mit unbekannter tatsächlicher Belastung reserviert. Sie beruht auf den
gespeicherten maximalen veröffentlichten Endpointpreisen, Eingabebytes mit Rahmenaufschlag
und maximaler Ausgabe; es wird keine kostenlose Fehlanfrage behauptet.

85 echte Aufrufversuche: 80 abgeschlossene Antworten mit gemeldeten **1,06028208 USD**;
für fünf Fehler bleiben höchstens **0,59838165 USD** reserviert. Zusammen
**1,65866373 USD**, unter der freigegebenen Grenze von 3 USD. Keine weiteren
Modellaufrufe oder künstlichen Bestehensschleifen sind für diesen Abschluss vorgesehen.

## Endgültige Fallbewertung

Die strukturierte externe Auswertung liegt in
[`independent-assessment.json`](../../artifacts/issue133/methodology/independent-assessment.json).
Die folgenden Bewertungen beruhen auf den Quellen und den tatsächlichen Texten,
nicht nur auf dem Verifier-Status.

| Fall | Quellenlauf unter v7 | Tatsächlich gerechtfertigter Stand |
|---|---|---|
| A | `waiting_human`, Call 59 | 09:00/10:00-Widerspruch und einfacher Gegenfall bleiben erhalten. Verbindlichkeitsregel erfragt; keine aktuelle Transferzeit, Hauptursache oder Maßnahme bestätigt. |
| B | `waiting_human`, Call 60 | Zwei subjektive Aufwandsberichte bleiben konkurrierend. Fokus und Lösungsvorzug zurückgestellt; kein Einstellungsverbot und kein erfundener Ist-Ablauf im Quellenentwurf. |
| C | `waiting_human`, Call 61 | Telefonnummer vorhanden, nicht angerufen; Widerspruch bleibt offen. Geplanter Kontakt ist ausdrücklich nicht durchgeführt. Keine Entscheidung für Uhrzeit oder Treffpunkt. |
| D | Repair 62–63, erneuter Verifier 64: `waiting_human` | Wirkungsversprechen im Trade-off korrigiert zu „soll … verbessern“. Anfrage ist kein Auftrag; Zusatzpreis, Treffpunktbestätigung und Vollmacht bleiben offen. |

**Originalfehler-Replay:** A (65–68) und C (73–76) korrigieren den dokumentierten
Fokus-/Scopefehler automatisch und werden erneut geprüft. Das ist ein begrenzter
Erfolg des vorhandenen Repair-Mechanismus, keine bestätigte Geschäftsentscheidung.

**Primärer Abnahmeblocker B:** Die ersten beiden Reviews 69–70 benennen ausschließlich
die überzogene Personalbehauptung. Repair 71 korrigiert diese, behält jedoch
`process_analysis.current_flow` mit „Aufrufen der Kundendaten, Erfassung der gewünschten
Reisedetails, Validierung der Buchungsdaten …“ bei. Im natürlichen Ersttext steht
keiner dieser Schritte. Erst Verifier 72 erkennt erfundene Teilschritte/Nacharbeiten
und eine fälschlich als `indicative` gekennzeichnete Phase. Ergebnis:
`verification_not_converged`, keine Materialisierung. Sicheres Stoppen funktioniert;
die geforderte vollständige automatische Korrektur A–D ist damit **nicht nachgewiesen**.
Ein zweiter Repair oder Erfolgssampling wurde nicht hinzugefügt.

**Zusätzliche Verifier-Grenze A:** Trotz Zustimmung 68 enthält
`stage_3_interne_rueckfrage.pain_points` noch die nicht belegte Erklärung
„Zusätzliche Verzögerung durch Abhängigkeit von der Verfügbarkeit der Büromitarbeiter“.
Die Quelle berichtet Rückfragen und Warten, aber keine Prüfung der Büroverfügbarkeit
als Verzögerungsursache. Auch ein als Vorschlag zu kennzeichnendes strategisches Ziel
bleibt unqualifiziert. Der gezielt korrigierte Hauptfehler ist daher kein Beleg für
zuverlässige Quellenwahrheit sämtlicher Nebenfelder.

**D-Replay 77–79:** Ein Guard lehnte das im Repair ausdrücklich verwendete Wort
„hypothetisch“ irrtümlich ab. Die Wortform ist korrigiert und durch einen gezielten
Offline-Regressionstest abgesichert. Für den gescheiterten realen Replay wird kein
nachträglicher terminaler Erfolg behauptet. Der separate echte Quellenlauf 62–64
ist davon unabhängig und bleibt erfolgreich bis zur berechtigten Zurückstellung.

### Technologieoffene Optionen und Grenze des Nachweises

Die echten B-/C-Generatorantworten (81/83) enthalten konkrete organisatorische
Klärungswege, prüfen vorhandene Standardsoftware vor eigener Regelautomation und
benennen ausdrücklich den fehlenden belegten KI-Zusatznutzen. Unsicherheit,
Annahmen und offene Evidenz werden feldweise ausgegeben; keine Rangfolge, Auswahl,
numerische Pilotwirkung oder menschliche Freigabe wird erfunden.

Das ist ein belegter Fortschritt in der Lösungsoffenheit. Die fachliche Kette bleibt
dennoch offen: B hat keine gerechtfertigte Prozesspräferenz; die Optionsprobe setzt
einen ausdrücklich manuellen DRAFT-Aufbau voraus. In C wird die ungeprüfte
Telefonerreichbarkeit mehrfach als dokumentierter Engpass bezeichnet, obwohl die
Fallakte nur eine offene Voraussetzung belegt. Ein Verweis auf ein Prozessfeld macht
die zugrundeliegende Deutung nicht zu einer bestätigten Ursache.

Der Initial-Critic bricht bei B/C mit `output_truncated` ab (82/84), statt ein
verwertbares fachliches Urteil abzugeben. A liefert `empty_response` (80), D läuft
in `timeout` (85). Die Fehler sind im Ledger mit unbekannter tatsächlicher Belastung
reserviert. Somit gibt es **keinen vollständigen echten Lösungs-Repair-/Final-Critic-
Nachweis A–D**. Deterministische bestehende Tests belegen weiterhin technische
Patchbindung und Gates, ersetzen aber diese fehlende semantische Evidenz nicht.

| Abnahmekriterium | Quellenbasierte Bewertung |
|---|---|
| Unbelegte Ursachen in sämtlichen Feldern ausgeschlossen | Teilweise; verbleibende A-Nebenaussage widerlegt einen vollständigen Nachweis. |
| Blockierende Lücken wirksam, Exploration möglich | Belegt durch vier offene Quellenläufe sowie UI-/Service-Regressionen einschließlich historischer Analysen. |
| Scope/Optionen passend zur belegten Diagnose | Teilweise; A/C enger, B-Reparatur mit erfundenem Ablauf, C-Optionen mit vorzeitigem Engpassetikett. |
| Nicht-KI-Alternativen vollwertig | In B/C-Optionsentwürfen belegt; keine freigegebene Präferenz behauptet. |
| Verifier erkennt dokumentierte Fehler zuverlässig | Nicht erfüllt: selektiver B-Erstbefund, A-Nebenfeld übersehen. |
| Automatische Korrektur und erneute Validierung A–D | Teilweise; B konvergiert nicht, D-Replay bleibt technisch fehlgeschlagen, Lösungs-Critics unvollständig. |
| Keine erfundenen realen Daten/Freigaben/Pilotwirkungen | Keine solchen Nachweise oder Freigaben behauptet; fachlich unbelegte Prozessdetails werden ausdrücklich als Fehler dokumentiert. |

## Technische Absicherung und Abschlussentscheidung

Die erste vollständige PostgreSQL-Regression fand 47 Fehler: vor allem eine zu lange
Prompt-Versionskennung sowie Tests mit historischen Versionsannahmen. Kennungen wurden
verkürzt; eingefrorene Referenzen und Checksummen bleiben unverändert, ihre Tests
unterscheiden historische Verträge von aktuellen Prompts. Alle 47 Fehler bestanden
danach gezielt. Eine weitere vollständige Regression bestand mit 2.210 Tests und zwei
plattformbedingt übersprungenen Symlink-Tests. Der v7-Durchgang bestand anschließend
mit **2.211 Tests und zwei Symlink-Skips**. Nach der letzten Wortformkorrektur
„hypothetisch“ bestanden die **15 gezielten Methodiktests** erneut. Die vollständige
CI wird für den finalen Review-Commit zusätzlich geprüft. Technische Einzelheiten
stehen im Prüfprotokoll; der finale CI-Status wird im PR und in #133 festgehalten.

Ruff, Formatprüfung, Django-Systemprüfung, Migrationsprüfung, Bandit und Lockfileprüfung
sind erfolgreich. Der Dependency-Audit meldet mit den unveränderten fünf expliziten
Repository-Waivern keine bekannten weiteren Schwachstellen. Keine neue Migration,
Abhängigkeit, Datenbanktabelle oder Produktarchitektur wurde eingeführt.

**Entscheidung:** Änderungen und Nachweise zur Review bereitstellen, Gesamtabnahme
verweigern und #133 offen lassen. Die nächsten fachlichen Arbeiten müssen die
unvollständige Befundsammlung vor dem einmaligen Repair und verbleibende unbelegte
Nebenfelder lösen; die realen Optionsprüfungen brauchen verwertbare Critic-Antworten.
Ein grüner technischer Testlauf allein rechtfertigt hier keinen Merge als erfüllten
methodischen Auftrag. Es wird kein weiterer Plan als erfolgreiche Umsetzung ausgegeben.

## Reproduktion ohne neue Kosten

1. Tests und Quellen aus diesem Commit verwenden. `criteria.json` und die gespeicherten
   Datei-/Implementierungshashes erlauben die Zuordnung zum jeweiligen Lauf.
2. `python scripts/validate_rsd_issue133.py tests/test_issue133_methodology.py
   tests/test_issue_98_autonomous_business_discovery.py` blockiert Netzwerkaufrufe
   und prüft bestehende sowie neue Mechanismen kostenfrei mit SQLite.
3. Den fachlichen B-Blocker im Ledger über Call-IDs 69–72 und
   `B-replay-v7.json` nachvollziehen: Quelle U0 gegen benannte Prozessschritte und
   beide Verifier-Findings vergleichen. A-Nebenfeld entsprechend mit Call 67/68 prüfen.
4. Für die vollständige technische Absicherung den unveränderten PostgreSQL-/CI-
   Ablauf aus `.github/workflows/ci.yml` nutzen. Der normale Testlauf ruft keinen
   echten Provider auf.
5. Der Live-Starter erfordert ausdrücklich `--confirm-real-provider`, nutzt ein
   exklusives Kampagnen-Lock und verweigert vorhandene Ergebnisdateien. Er ist kein
   automatischer pytest-Test. Die gespeicherten Nachweise reichen zur Bewertung;
   neue echte Aufrufe sind für diese dokumentierte Entscheidung nicht erforderlich.
