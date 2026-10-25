# D1: Strategische Entwürfe vor globalem Screening

Datierter Nachtrag vom 25.10.2026 zu #185 / Parent #183. Geprüfte Ausgangsbasis:
`main` / `abbfb302747510106a4eac0db807b50bc254deb2`. Historische Auditdateien
aus Dokumentations-PR #184 bleiben unverändert.

## Reproduktion und enger Fix

Die bestehende deterministische Fixture aus `test_issue_178_strategic_discovery.py`
materialisiert eine echte strategische Discovery mit menschlichem Scope und unbekannten
Ist-Daten. Ohne spätere Outcome-/Pfadbestätigung liefern die regulären Editier- und
Optionsanlage-Views auf der Ausgangsbasis 302 zum Value Stream. Das unmittelbar
anschließende Prozessformular verlangt trotz dieser Provenance Baseline und Engpass.
Die Journey verweist weiterhin auf globales Screening.

Die neuen Abnahmetests reproduzieren auf einem separaten unveränderten Checkout drei
Fehler: Editorzugang, Formularvertrag ohne Pfadbestätigung und nächste Aktion.
Eine spätere Pfadbindung wird dabei nicht vorgezogen.

Der Fix erkennt ausschließlich serverseitig belegte strategische Materialisierungen:
Prozess, Phase, menschlicher Scope und Quellennachweis müssen zusammenpassen.
Neue Materialisierungen bewahren den Kontext im vorhandenen unveränderlichen
Investigation-Quellensnapshot; die Entwurfsbearbeitung bleibt auch nach Capture-Löschung
möglich. Bereits gespeicherte Materialisierungen werden über ihre bestehenden
Capture-/Analyse-/Quellen-/Materialisierungsverknüpfungen geprüft, auch nach Ablauf der
Capture-Sitzung. Ohne erhaltenen Herkunftsnachweis greift keine Ausnahme.

Nur Prozessbearbeitung, Optionsanlage und Optionsbearbeitung erhalten die Ausnahme.
Baseline und Engpass dürfen im Prozessformular leer bleiben. Rechte, servereigene
Provenance, Kohortenzuordnung und eigenständige Prozessvalidierung bleiben erhalten.
Die vorhandene Oberfläche zeigt erreichbare Entwurfsaktionen und unterscheidet sie von
der weiterhin blockierten bindenden Auswahl. Explizit zurückgestellte/nicht ausgewählte
Wertströme erhalten keine Ausnahme. Keine neuen Modelle oder Migrationen.

## Szenario B: tatsächlich erreichter Stand

Automatisiert geprüft auf PostgreSQL 17.5:

1. Tatsächliche strategische Materialisierung mit gemocktem Provider, menschlichem Scope,
   leerer Baseline, leerem Engpass und ohne bestätigte Ursache.
2. Sofortiges GET des Prozessformulars, POST mit leeren Diagnosefeldern, Speicherung und
   erneutes Öffnen; keine vorherige Pfad-/Outcome-Bestätigung.
3. GET/POST einer organisatorischen Optionshypothese, erneutes Öffnen, Bearbeiten und
   Speichern als Entwurf. Keine Bewertung oder Wirksamkeit behauptet.
4. Erst nach dieser Entwurfsarbeit werden bestehende menschliche Outcome-/Strategiepfad-/
   Phasenbestätigungen ergänzt. Die Vergleichsmatrix ist erreichbar. Ein bindender POST
   bleibt abgewiesen und erhält Auswahl und Begründung im Formular. Ein direkter
   Serviceaufruf bleibt ebenfalls abgewiesen.
5. Das unveränderte globale Screening-Gate blockiert also weiterhin vor einer Lösungswahl;
   zusätzlich prüft eine eigenständige Gegenprobe denselben negativen Bindungsvertrag.

Ergebnis: Unverbindliche Weiterarbeit ist technisch erlaubt und automatisiert belegt.
Ein fachlich begründeter Non-KI-Sieg, externe Umsetzung, Wirkungsreview und
Skalierungs-/Beendigungsentscheidung sind in der durchgehenden B-Kette **nicht erreicht**.
Keine Ursache, globale Screeningbewertung oder Messzahl wurde zum Fortfahren erfunden.
Synthetische Hypothesen sind keine realen Unternehmensbefunde oder ROI-Nachweise.

## Fachliche Vorlage für #183 – keine Gate-Änderung freigegeben

Zu entscheiden ist, ob eine spätere bindende strategische Lösungswahl trotz unbekanntem
globalem Screening zulässig sein soll. `ValueStreamFocus.is_selected` und
`solution_selection.focus_readiness_blockers` bleiben in diesem Fix unverändert.

| Variante | Folge und verbleibender Entscheidungsbedarf |
|---|---|
| Bestehendes bindendes Gate beibehalten | Entwurfsarbeit funktioniert; Auswahl bleibt bis zu tatsächlich belegbarem globalem Screening gesperrt. Fehlende Daten dürfen nicht durch Ratings ersetzt werden. |
| Separaten strategischen Bindungsvertrag ausdrücklich freigeben | Vor einer Implementierung in #183 festlegen, welche menschliche vorhabensbezogene Phasenwahl, Outcome-Beiträge, strategischen Annahmen/Validierungsschritte, echten Vergleichsgrundlagen und Evidenz-/Unknowns-Angaben das globale Screening an dieser bindenden Stelle ersetzen dürfen. Rollen-, Revisions- und Snapshotschutz erhalten; problemgetriebene und Legacy-Routen unverändert lassen. Vergleichsqualität mit #188 abstimmen. |

Der zweite Weg benötigt eine ausdrückliche Auftraggeberentscheidung in #183 und einen
anschließend abgegrenzten Implementierungsauftrag. Dieser PR entscheidet ihn nicht und
schließt weder Parent #183 noch die vollständige B-Integrationsabnahme aus #189 ab.

## Prüfung

- 17 gezielte D1-Regressionen: tatsächliche Views und Formulare, Speicherung/Wiederaufnahme,
  Rechte, manipulierte/fremde Herkunft, Capture-Aufbewahrung, historische Materialisierung,
  explizite Zurückstellung, keine Selbstvalidierung, negativer Bindungsversuch und Eingabeerhalt.
- Erweiterte gezielte Suite mit strategischer Discovery, Outcome-Vertrag und
  Aufbewahrungsregressionen: 81 bestanden vor den vier zusätzlichen D1-Gegenproben;
  anschließend alle 17 D1-Tests bestanden.
- Vollständige PostgreSQL-Suite und GitHub-CI: abschließende Ergebnisse werden im PR
  und im Chat berichtet. Keine abgeschlossene Prüfung aus laufenden Tests ableiten.
- Externe Socket-Verbindungen der lokalen Testprozesse sind gesperrt; Provider-Antworten
  stammen aus vorhandenen deterministischen Fixtures. Keine realen Modellaufrufe,
  keine Produktivdatenänderung, kein Merge.
