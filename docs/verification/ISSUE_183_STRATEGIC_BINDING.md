# #183 – begrenzter strategischer Bindungsvertrag

Datierter Nachtrag vom 26.10.2026. Ausgangspunkt `main` / `a3b2644`, einschließlich
#185–#189. Der aktuelle Nutzerauftrag autorisiert ausdrücklich die bereits empfohlene
strategische Alternative zum globalen Screening. Die alten Audit-/D1-/D2-/D3-/#189-
Berichte bleiben als historische Nachweise unverändert. Kein Merge, kein realer
Modellaufruf und keine Änderung an Produktivdaten.

## Entscheidung und minimale Grenze

Das globale Screening bleibt bestehen. Ausschließlich ein belegter strategischer
Vorgang darf die neue Alternative an der bindenden Lösungswahl verwenden:

- Aktiver Outcome- **und** Vergleichsvertrag; keine rückwirkende Kohortenaktivierung.
- Tatsächlich materialisierte strategische Discovery mit unveränderlichem menschlichem
  Untersuchungsrahmen, Person/Zeitpunkt und passendem Prozess-/Phasen-/Quellennachweis.
  `has_strategic_exploration` bleibt die vorhandene Herkunftsprüfung; ein Request-Flag
  oder eine bloß manuell gewählte Pfadbezeichnung ersetzt diese Provenance nicht.
- Globaler Status `candidate` oder `not_screened`. Explizite Zurückstellung und Ablehnung,
  fehlender Fokusdatensatz und ein inkonsistent unvollständiger `selected`-Stand erhalten
  keine Ausnahme. Ein vollständig ausgewählter globaler Fokus nutzt den bisherigen Weg.
- Derselbe aktuell bestätigte Vorhaben-Outcome mit Beitrag, Wirkannahme, Owner, Kriterien
  und Messabsicht bzw. begründeten offenen Messangaben aus #189; zugehöriger menschlicher
  Phasenfokus und bewusst eingeordneter Strategiepfad mit Potenzial/Validierungsschritt.
- Bestehender #188-Vertrag: mindestens zwei aktive bewertete Ansätze, optionenspezifischer
  Outcome-Beitrag, Aufwand/Umstellung, Risiken und Evidenz; ausdrückliche Begründung
  verschiedener Handlungshebel und Annahme verbleibender Unsicherheiten. Das vorhandene
  Unsicherheitsfeld erläutert in dieser Route ausdrücklich die offenen globalen Screeningfragen
  und warum die begrenzte Entscheidung trotzdem vertretbar ist.

Keine zusätzliche Rolle, Pflicht-Baseline, erfundene Ursache, Pflicht-ROI oder neue
Freigabestufe. Der berechtigte auswählende Mensch verantwortet die begrenzte Entscheidung.
Die Unterscheidung von Hypothese, Evidenz und bestätigtem Erfolg bleibt erhalten.
Inhaltliche Plausibilität und Vollständigkeit der Freitexte bleiben menschliches Urteil;
keine semantische Wahrheitsgarantie. Eine Begründung macht Unknowns nicht zu Messwerten.

Der Auftrag konkretisiert diese bereits empfohlenen Voraussetzungen hinreichend.
Es wurde kein zusätzlicher fachlicher Trade-off außerhalb dieser Grenze implementiert.

## Gemeinsamer Gate-/Snapshot-/Aktualitätspfad

`strategic_binding_basis` projiziert ausschließlich die geprüfte strategische Grundlage.
`focus_readiness_blockers`, vorhandene Auswahl-View und vorhandener Outcome-Snapshot nutzen
sie gemeinsam. Outcome-/Phasen-/Pfadvalidierung und Vergleichsprüfung verbleiben in ihren
bestehenden Services. Die unverbindliche Entwurfsberechtigung wird nicht pauschal in eine
Auswahlberechtigung umgedeutet.

Der vorhandene unveränderliche `outcome_snapshot` enthält zusätzlich die verwendete
strategische Grundlage: Scope-Provenance, globaler Status, tatsächlich vorhandene
Screeningangaben, fehlende Angaben, Pfadreferenz und Evidenzgrenze. Der vorhandene
`quality_snapshot` hält die ausdrücklich begründete Annahme offener Screeningfragen fest.
Keine Ratings werden geschrieben. Die kanonische Auswahl sperrt neben Prozess und
Vorhaben den vorhandenen Fokusdatensatz während der Entscheidung; Rollen-, Versions-
und atomarer Schreibschutz bleiben bestehen.

Die vorhandene selektive Prüfung `snapshot_is_stale` berücksichtigt die strategische
Grundlage. Neue Screeningkenntnis, terminaler Fokusstatus oder geänderter materieller
Outcome-/Pfad-/Phasen-/Vergleichsbezug verlangen erneute Interpretation. Historische
Auswahl-, Mess- und Reviewnachweise bleiben unverändert. Rein formale Titeländerungen
oder Capture-Aufbewahrung bei erhaltenem eingefrorenem Quellennachweis entwerten die
unveränderte Grundlage nicht. Keine pauschale Rückstufung laufender Piloten.

Es gibt keine neuen Modelle, Migrationen, Generator-/Prompt-Schemata oder globale
Fokuszusammenführung. Problemgetriebene und Legacy-Routen behalten ihre bisherigen
Voraussetzungen; Governance-, KI-Freigabe-, Delivery-, Pilot- und Go-live-Regeln ändern
sich nicht. Strategische KI-Auswahl verweist weiterhin auf den existierenden KI-Handoff.

## Bestehende Oberfläche und Fortsetzung

Die Vergleichsansicht benennt den Ersatzbezug und die offenen Screeningangaben vor
bewusster Auswahl. In der Auswahlhistorie bleiben diese Angaben sichtbar. Gesperrte
Entwürfe verlieren keine Formulareingaben. Die bestehende Journey führt nach aktueller
Non-KI-Wahl zum gemeinsamen Wirkungsreview, nach geänderter Grundlage zur Neuauswahl;
sie behauptet keine fehlende Prozessdiagnose oder globale Screeningbestätigung.
Externe organisatorische Umsetzung benötigt keinen künstlichen KI-Use-Case oder Non-KI-Pilot.
Die Fortsetzungsanzeige verwendet die bestehenden Vorhaben-Reviewrechte; Lösungswahl
vermittelt keine zusätzliche Reviewberechtigung. Ein begründeter Abbruch bleibt terminal
und führt nicht zu einer unzulässigen Neuauswahl.

## B-Kette: technische Prüfung und Evidenzgrenze

`tests/test_issue_183_strategic_binding.py` verwendet einen ausdrücklich synthetischen,
RSD-nahen Servicekontext. Es startet nicht bei einer ausgefüllten Prozess-/Optionsfixture:

1. Menschlicher Untersuchungsrahmen → echte strategische Discovery mit eingefrorenen
   Quellen und deterministischen Providerantworten → reale Materialisierung.
2. Unmittelbares GET/POST/Wiederaufnahme des Prozessentwurfs und reguläre Optionsanlage
   ohne vorgezogene Pfad-/Outcome-Bestätigung. Baseline, Engpass und Ursache bleiben leer.
3. Spätere menschliche Outcome-/Messplan-/Strategiepfad-/Phasenbestätigung. Zwei Ansätze
   werden regulär bewertet: verbindliche Quelle/Zuständigkeit gegenüber assistierter
   Quellenanzeige. Beide beziehen sich auf denselben begrenzten Service-/Buchungsbeitrag.
4. Verbindlicher POST im bestehenden Vergleich: Non-KI wird begründet gewählt, weil die
   organisatorische Regel Verbindlichkeit unmittelbar klärt; technische Anzeige schafft
   diese Autorität nicht. Adoption, Aufwand, Kosten und globale Screeningfragen bleiben
   ausdrücklich offen. Auswahl und menschliche Unsicherheitsannahme sind immutable.
5. **Externe Umsetzung im deterministischen Test:** eine außerhalb der Domain-Modelle
   geführte synthetische Rolloutakte hält Entscheidung, nachfolgenden Umsetzungszeitpunkt,
   fachliche Verantwortung, benannte Quelle/Vertretung, Testanfrage und Rückfallweg fest.
   Der Review referenziert diese Akte samt Hash. Kein Delivery-System wird erfunden.
6. Tatsächlicher POST des gemeinsamen Wirkungsreviews: organisatorische Durchführung
   dokumentiert; Prozessnutzen und Buchungswirkung noch nicht gemessen, Attribution
   ungeklärt. Historischer Kriterien-/Messplanbezug bleibt die ursprüngliche Auswahl.
7. Regulärer Vorhabenabschluss per Formular mit begründetem `unclear`; der Review bleibt
   aktuell. Kein künstlicher KI-Use-Case, keine Ursache, Baseline oder Screeningzahl.

**Technisch erlaubt und automatisiert belegt:** die vollständige synthetische B-Kette
vom legitimen Scope bis zum zulässigen ungeklärten Abschluss. Der bisherige globale
Bindungsblocker ist für die freigegebene Alternative ersetzt. Der Vergleich begründet
unterschiedliche Hebel und Unknowns; er beweist keinen realen wirtschaftlichen Non-KI-Sieg.

**Nicht fachlich als realer Erfolg abgenommen:** Eine Test-Rolloutakte ist keine tatsächliche
Unternehmensumstellung und kein unabhängiger Nachweis externer Ausführung. Reale Durchführung,
Messgüte, Buchungswirkung, Attribution und die Nutzerabnahme #161 bleiben unbelegt.
Keine bestandene Realumsetzung, Geschäftswirkung oder kausaler ROI wird daraus abgeleitet.
Eine tatsächliche Firmenumstellung ist nicht Teil dieses Codeauftrags und wurde nicht ausgeführt.

## Regression und CI

Gezielte PostgreSQL-Tests prüfen fehlenden/gefälschten Bezug, fehlende Bestätigung und
Phase, abweichenden Pfad, terminale/invalide globale Zustände, erhaltene Legacy-Kohorte,
Vergleich/Unsicherheitsannahme, Rechte, Eingabeerhalt, Prozesskonflikt, Capture-Retention,
Metadaten und neue Screeningkenntnis. Vorhandene #185/#189-Gegenfälle bleiben negative
Tests eines unvollständigen Vergleichs; sie behaupten nicht mehr das inzwischen ersetzte Gate.
Bestehende #146/#147/#158/#178/#186/#188- und Governance-/Journey-Regressionen bleiben erhalten.

Vollständige unveränderte CI einschließlich PostgreSQL-Gesamtsuite, separatem Architecture-
E2E, Lint/Format, Lockfile, Django/Migrationen, Sicherheits-/Abhängigkeitsaudit, allen drei
Compose-Konfigurationen und beiden Docker-Images. Finale Ergebnisse und der CI-Link stehen
im eigenen Draft-PR und Chat; ein laufender Check wird nicht als bestanden ausgegeben.

Parent #183 wird hier nicht geschlossen. Mehrprozessaggregation, reale Modellqualität,
Menschentest #161 und andere Themen werden nicht vorgezogen.
