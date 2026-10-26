# Issue #201 – Historischen Wirkungskontext qualifiziert anzeigen und exportieren

Stand: 26.10.2026. Ausgangspunkt: `main` / `7d391e8d39536a02902d10f81578636813be8388`.
Referenzen: #201, Re-Audit #196 (F3, P5/P6), Parent #197; Integration nach #200.

## Verhalten und Grenzen

Delivery und Scale zeigen die gespeicherte Wirkungsaussage und Attribution zusammen
mit dem damaligen Prüfstatus. Ein gespeichertes „Bestätigt“ bleibt als Aussage erhalten,
auch wenn es ungeprüft oder erneut prüfbedürftig ist. Der aktuelle Vorhabenskontext wird
ausdrücklich vom historischen Übergabe- beziehungsweise Reviewstand getrennt.

Die gemeinsame Darstellung interpretiert ausschließlich die gespeicherten Metadaten:

- `review_required = false`: geprüft, auch bei bestehenden Snapshots.
- Neue Snapshots ergänzen den vorhandenen Reviewzeitpunkt `reviewed_at`. Bei
  `review_required = true` unterscheidet dieser ungeprüft von erneut prüfbedürftig.
- Bestehende Snapshots mit `review_required = true`, aber ohne Reviewzeitpunkt behalten
  ihren belegten Vorbehalt „Wirkungsprüfung offen / erneut erforderlich“; die damals
  fehlende Unterscheidung wird ausdrücklich benannt.
- Ohne gespeicherten Prüfstatus: „Historisch nicht erfasst“. Ohne historischen
  Wirkungskontext: „Historischer Wirkungskontext nicht vorhanden“, auch vor Übergabe.

Der echte Markdownexport liest für diesen Abschnitt ausschließlich
`DeliveryPackage.business_context_snapshot`: Geschäftsergebnis, Beitrag, Wirkannahme,
Kriterien, Messmethode/-zeitraum/-population/-vergleich, offene Messangaben,
Wirkungsaussage, Attribution samt Begründungen und Aussagegrenzen. Spätere Änderungen
am Vorhaben oder Wirkungsreview ersetzen den damaligen Stand nicht.

Keine Migration, Rückbefüllung, zusätzliche Outcome-Datenquelle, neue Freigabe oder
neues Gate. Rechte, Übergabe und historische Speicherung verwenden die bestehenden
Services und Regeln. Ein Prüfstatus ist kein Beweis realer Geschäftswirkung.

## Ausführbare Abnahme

`tests/test_issue_201_historical_context.py`: 13 neue PostgreSQL-Fälle.

- Echte Übergabe-, Detail- und Exportrouten für ungeprüft, geprüft und erneut
  prüfbedürftig; gespeicherte bestätigte Wirkung und Attribution bleiben qualifiziert.
- Echte Pilotfortsetzungsreviews mit Scale-Snapshot für dieselben drei Zustände sowie
  historisch fehlenden Prüfstatus; historische Oberfläche erhält den damaligen Stand.
- Vier alte Snapshotformen einschließlich fehlendem Kontext und altem Prüfvorbehalt
  bleiben ohne Ergänzung fiktiver Inhalte exportierbar und unverändert gespeichert.
- Export vor Übergabe, anonyme und archivierte Zugriffe, Leserechte, unberechtigte
  Übergabe sowie Schreib-/Wiederübergabeschutz für übergebene Packages.
- Nach Änderungen von Geschäftsziel, Messmethode und Wirkungsaussage bleibt der
  exportierte Übergabestand bytegleich; die Oberfläche zeigt separat den aktuellen Stand.

Gezielte PostgreSQL-Regressionen: 178 bestanden, einschließlich der neuen Fälle sowie
#146, #147, #186, #189, #200 und Scale-Readiness. Nach der abschließenden UI-Korrektur
wurden die 13 neuen Fälle erneut auf einer frisch aufgebauten Testdatenbank bestanden.
Ruff, Formatprüfung, Lockfile, Django-Systemprüfung, Migrationsprüfung und Bandit
bestanden. Die vollständige CI mit Gesamtsuite, Architecture-Real-DEMO-E2E,
Abhängigkeitsprüfung, Compose und Docker-Builds wird im PR ausgewiesen.

## Desktop und Branchbereinigung

Die Kontextausgabe verwendet einen flachen Abschnitt und beschriftete Datenzeilen
anstelle einer zusätzlichen dekorativen Karte. Prüfvorbehalte stehen vor den Aussagen.
Stile liegen im gemeinsamen `ui-vnext`-Komponentenbestand und verwenden semantische
Tokens; ergänzender Kontext bleibt über natives `details`/`summary` erreichbar.
Die aus echten Django-Routen gerenderten synthetischen Seiten wurden im Browser bei
1440 × 1000 geprüft. Delivery: kein horizontaler Überlauf, Summary-Klickziel 42 px,
aktueller und eingefrorener Kontext getrennt. Kein menschlicher Bedienzeitnachweis.

#200 ist über PR #205 in `main` integriert. Sein Remote-Branch war bereits entfernt.
Der lokale Branch `fix/200-historical-review-materiality` wurde erst nach leerem
Inhaltsvergleich mit aktuellem `main` gelöscht; der Squash-Merge erklärt die fehlende
direkte Commit-Abstammung. Unversionierte Laufzeitdaten unter `var/` bleiben erhalten.

Alle Nachweise sind synthetisch, ohne echte Modellaufrufe oder Produktionsdatenänderung.
Übergreifende Abnahme #202, Menschentest #161 und historische Auditberichte bleiben
unverändert. Ein Merge dieses PR benötigt die Freigabe des Auftraggebers.
