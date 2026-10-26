# #187 – Messreferenzschutz für KI-haltige Interventionen

## Auftrag und freigegebene Grenze

Basis: aktuelles `main` / `ed5a2ebb3267a87c52967f8c631922c5d44c0bfa`,
26.10.2026, einschließlich #185, #188 und #186. Parent #183, vollständige
Issues #187/#189 sowie ADR 0009 und ADR 0002 wurden abgeglichen.
Die Phase-0-Empfehlung und anschließende ausdrückliche Nutzerfreigabe wurden
im ursprünglichen Analysechat nachvollzogen: kleine explizite Messabgrenzung
für andere organisatorische Teilwirkungen, bestehende KI-Metrik referenzieren,
keine semantische Wahrheitsgarantie. Der aktuelle Auftrag autorisiert #187.

Der historische Auditstand bleibt unverändert. Die drei neuen Negativtests
scheiterten auf unverändertem `main` mit `DID NOT RAISE ValidationError`:
`hybrid`, `custom_software`, `other`, jeweils mit KI-Anteil, erlaubten die
Finalisierung eines separaten Prozessmessstands ohne Use-Case-Referenz.
Die Reproduktion verwendet vorhandenen synthetischen Fixture-Baselinetext;
keine reale Unternehmensmessung oder erfundene Nutzenbehauptung.

## Enger Messvertrag

- `SolutionOption.starts_ai_use_case` bestimmt den KI-Bezug auch bei gemischten
  Typen. Ein Typname ist keine Aussage über die Gleichheit zweier Messgrößen.
- Ohne ausdrückliche andere Einordnung darf bei KI kein separater Prozessmessstand
  als aktuell geprüft bestätigt werden. Dieselbe KI-Größe bleibt ausschließlich
  in `UseCase.metric_*`; der Review referenziert den bestehenden historischen Stand.
- Zwei optionale Felder am vorhandenen Review ergänzen die minimale Abgrenzung:
  `process_measurement_kind=organizational` und `process_measurement_boundary`.
  Letzteres verlangt die menschliche Benennung von Messgröße, organisatorischer
  Komponente, Methode/Population und Unterschied zur KI-Metrik. Der vorhandene
  `process_measurement` bleibt zuständig für Definition, Zeitraum, Stand und Nachweis.
  Es gibt kein zweites Prozessmessobjekt, keine Messreihe und keine kopierten KI-Werte.
- Bei KI und zusätzlichem organisatorischem Messbefund ist vor Bestätigung auch
  der tatsächlich zugehörige Use Case erforderlich. Vorhaben und, bei gewählter
  Auswahl, Prozess-/Optionsherkunft werden weiterhin serverseitig überprüft.
  Das Umbenennen einer Kopie oder eine beliebige Erklärung beweist keine andere
  Größe: Einordnung und inhaltliche Tragfähigkeit bleiben menschlich zu beurteilen.
- Andere organisatorische Teilwirkung, Geschäftsresultat und Attribution bleiben
  getrennt. Ein erreichtes organisatorisches Prozessziel bestätigt keinen
  Geschäftserfolg und keine Kausalität. `unclear` bleibt legitim.
- Wirkliche Non-KI-Varianten benötigen weiterhin keinen künstlichen Use Case und
  keine neue Einordnung. Unbekannte Prozesswirkung bleibt ohne neue Messpflicht.
  Der bisher erlaubte Review nur einer KI-Auswahl ohne Prozessmessbehauptung bleibt
  zulässig; es wird kein neuer genereller Referenzzwang eingeführt.

## Entwürfe, Historie und #186

Die bestehende Entwurfsgrenze bleibt erhalten: Ein Hybrid-/Custom-/Other-Entwurf
ohne Use-Case-Referenz kann unvollständige bisher erlaubte Inhalte sichern.
Bei bereits referenzierter KI oder festen KI-Typen bleibt die bisherige direkte
Kopiersperre erhalten. Die ausdrückliche organisatorische Einordnung ermöglicht
hier ebenfalls unvollständige Entwürfe; Referenz und Abgrenzung werden spätestens
bei der bewussten Prüfung verlangt. Positive/negative organisatorische Ergebnisse
benötigen wie Non-KI einen Messstand/Nachweis auch neben einer KI-Referenz.

Die additive Migration `0023` ergänzt leere Felder an Review und Auditmodell.
Keine bestehenden Messwerte, Prüfer, Zeitpunkte, Historienreferenzen oder Snapshots
werden fachlich geändert; keine automatische Zuordnung oder semantischer Backfill.
Alte betroffene Reviews bleiben lesbar und werden mit konkretem Referenz-/
Abgrenzungshinweis prüfbedürftig. Der bestehende Reviewweg erlaubt bewusste
Neueinordnung oder Rückkehr zur autoritativen KI-Referenz. Historische Zeilen bleiben.

Dieselbe kleine Messreferenzregel dient Modellvalidierung, Finalisierung und
abgeleitetem Prüfbedarf. Die neuen Felder gehören zu `REVIEW_FIELDS` und damit
zum bestehenden historischen Inhaltsvergleich aus #186. Metadatenänderungen
entwerten unveränderte Messungen weiterhin nicht; geänderte KI-Messpopulation,
Abgrenzung, Messung und Intervention benötigen erneute Betrachtung.
Revisionen, Sperren, Rollen und atomare Services bleiben unverändert.

## Aufrufer und Nachweise

Geprüfte Aufrufer: `InitiativeImpactReview.clean/review_required`,
`save_impact_review`, `ImpactReviewForm`/GET/POST, `impact_review_context`,
Vorhaben-/Reviewanzeige einschließlich historischer Tabelle und die bestehenden
Wirkungslabels/Dashboardprojektionen. ModelForm und Service verwenden dieselben
Felder; die fachliche Regel wird nicht in JavaScript oder Formularlogik dupliziert.
Geschäftsmessung und deren bestehende `measurement_difference` bleiben getrennt.

PostgreSQL 17.5, isolierter Testcontainer:

- Parametrisierte KI-/Non-KI-Matrix für Hybrid/Custom/Other sowie feste KI-/Non-KI-Typen.
- Kopierte Messung bzw. bloßes separates Ergebnis ohne Abgrenzung zurückgewiesen;
  andere organisatorische Größe mit zugehörigem Use Case zugelassen.
- Fremdes Vorhaben, fehlende/falsche Optionsherkunft, unvollständige Abgrenzung,
  legitime Entwürfe, View-Eingabeerhalt und Wiederbestätigung.
- Historischer Messstand bleibt sichtbar; additive Migration bewahrt sämtliche
  alten Review-/Auditfelder ohne erfundene Abgrenzung.
- Abgrenzungs-/Messänderung und KI-Populationsänderung erzeugen Prüfbedarf;
  formale Titeländerung bleibt unschädlich. Bestehende #145/#146/#147/#158/#186-
  und Outcome-Review-Regressionen ergänzen diese Fälle.

Desktopprüfung bei 1440×1000 auf isolierten synthetischen Daten: zusätzliche
Einordnung, Abgrenzung und KI-Originalmetrik im bestehenden Formular; getrennte
Anzeige der organisatorischen Messung und KI-Quelle. Keine neue Layout-/CSS-Welt.
Die vollständige unveränderte PR-CI prüft zusätzlich Gesamtsuite, separaten
Architecture-Real-DEMO-E2E, Lockfile, Lint/Format, Django/Migrationen, Sicherheit,
Abhängigkeiten, alle drei Compose-Konfigurationen sowie beide Images.
Finale Zahlen und CI-Verweis stehen im PR und im Chat.

## Verbleibende Grenzen

Keine automatische semantische Duplikaterkennung oder Nachweisgarantie aus Freitext.
Ein Review referenziert weiterhin eine Auswahl und einen Use Case; keine vollständige
strukturierte Mehrprozessaggregation oder ROI-Summierung. Historischer Vorab-Messplan,
Kriterienabgleich, Delivery-/Skalierungskontext und vollständige A/B/C-Abnahme bleiben
#189. Strategisches Auswahl-Gate und Menschentest #161 bleiben getrennt.
Keine realen Modellaufrufe, Produktivdatenänderungen oder Pilot-/Go-live-Änderungen;
Draft-PR, kein Merge.
