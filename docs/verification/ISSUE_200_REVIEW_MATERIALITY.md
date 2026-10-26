# Issue #200 – Einheitliche Materialität im historischen Wirkungsreview

Stand: 26.10.2026. Ausgangspunkt: `main` / `b8207c923e879c0620bf9abca880797338fe5a74`.
Referenzen: #200, verbindlicher Re-Audit #196 (F4, P4/P7), Parent #197.

## Änderung und fachliche Grenze

`criteria_review_blocker` verwendet für die fünf bestehenden `PLAN_FIELDS` und
`evaluation_criteria` dieselbe Funktion `_formal_text` wie die Outcome-Aktualität
und der Vergleich der bereits geprüften Vorhabensaussage. Die bestehende Regel
erlaubt Leerraum, Unicode-Komposition (NFC) und einen optionalen abschließenden
Satzpunkt. Es gibt keine weitere Normalisierungsdefinition.

Die Speicher-, Bestätigungs-, Berechtigungs- und Revisionsregeln bleiben führend:
Ein begründet ergänzter Satzpunkt kann eine formale Korrektur sein; die bloße
Angabe „Schreibkorrektur“ legitimiert keine geänderte fachliche Aussage. Zielzahlen,
Zeiträume, Populationen, Vergleichsverfahren, Negationen und offene Messangaben
bleiben materiell. Ein fehlender historischer Messplan wird nicht nachgetragen.

Die Änderung betrifft ausschließlich Gleichheitsbewertung. Ursprüngliche Auswahl,
Kriterien-Snapshot und Review-Belege werden weder umgeschrieben noch automatisch
neu bestätigt. Ein ausdrücklich erneuter Review hält den ursprünglichen Anker fest
und speichert den dann aktuellen Kriterienstand separat. Keine Migration und keine
produktive UI-Änderung erforderlich.

## Abnahmeszenarien

`tests/test_issue_200_review_materiality.py` enthält 28 PostgreSQL-Fälle:

- 18 Kombinationen aus sechs Kriterien-/Messplanfeldern und Leerraum, Unicode-
  Komposition beziehungsweise begründetem Satzpunkt: Auswahl und Review bleiben
  aktuell; derselbe bestätigte Geschäftsergebnisnachweis trägt den Abschluss.
  Unveränderte historische Snapshots und Review-Historie werden direkt geprüft.
- Zwei echte Outcome-Vorbereitungsrouten (Entwurf speichern / fachlich bestätigen):
  Satzpunkte in allen sechs Feldern; weiterhin aktuelle Auswahl und Wirkung;
  erneuter Originalmaßstab-Review und bestätigter Abschluss möglich. Die ursprüngliche
  und die spätere Kriterienfassung bleiben über Snapshot und Historie unterscheidbar.
- Acht materielle Gegenproben trotz Angabe „Schreibkorrektur“: geänderte Zielzahl,
  Kriterien, Zeitraum, Population, Vergleichsverfahren, Negation, offene Messangaben
  und zwei statt einem Satzpunkt. Auswahl und Review werden prüfbedürftig, ein
  bestätigter Abschluss wird abgelehnt. Selbst nach neuer fachlicher Annahme und
  Auswahl bleibt die historische Abweichung einzuordnen; eine ausdrücklich
  nachträgliche Bewertung erhält den ursprünglichen Maßstab unverändert.

Gezielte Bestandsregressionen: #146 (Outcome-Vertrag und Legacy), #186
(Aktualität und PostgreSQL-Schreibkonflikte), #189 (Messplan, historische Kriterien,
Delivery/Pilot/Abschluss) sowie #199 (Bindungsvoraussetzungen und Vorbereitung).
Konkrete Testergebnisse und vollständige CI werden im zugehörigen PR ausgewiesen.
Die CI umfasst PostgreSQL-Gesamtsuite, Architecture-Real-DEMO-E2E, Lint/Format,
System-/Migrationsprüfungen, Security/Abhängigkeiten, Compose und Docker-Builds.

## Branchbereinigung und Aussagegrenzen

#199 wurde durch PR #204 am 26.10.2026 gemergt. Der Remote-Branch war bereits
gelöscht. Der lokale Branch `fix/199-binding-prerequisites` wurde nach leerem
Inhaltsvergleich mit aktuellem `main` entfernt (Squash-Merge, daher keine direkte
Commit-Abstammung). Vorhandene unversionierte Betriebsdateien bleiben unberührt.

Alle Fälle verwenden synthetische Daten ohne echte Modellaufrufe. Sie belegen die
technische Materialitätskonsistenz; keine reale Geschäftswirkung, kausale Attribution
oder menschliche Gebrauchstauglichkeit. Übergreifende Abnahme #202 und Menschentest
#161 werden damit nicht für abgeschlossen erklärt. Historische Auditberichte bleiben
unverändert.
