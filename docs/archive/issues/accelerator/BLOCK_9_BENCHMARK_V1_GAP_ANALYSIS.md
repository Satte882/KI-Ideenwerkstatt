# Block 9 AP 7 Nachtrag: Gap-Analyse `block9-v1` → `block9-v2`

**Issue:** #125  
**Auslöser:** lokaler, nicht gewerteter Warm-up am 08.08.2026  
**Betroffener Freeze:** `ki_radar/accelerator/block9_benchmark.v1.json`  
**Nachfolger:** `ki_radar/accelerator/block9_benchmark.v2.json`

## Ergebnis

`block9-v1` wird **nicht verändert**. Der verpflichtende Warm-up hat vor dem ersten
gewerteten Lauf gezeigt, dass der eingefrorene interaktive Vertrag den realen UI-Pfad nicht
abbildet. Es wurden deshalb keine Scored Runs gestartet und keine interaktiven Rohdaten
geschrieben.

Die bereits in AP 9 gemessenen technischen Blueprint-/Delivery-Kontrollwerte bleiben
unverändert. Ihre Inputs, Prüfsummen und Messgrenzen werden durch diesen Nachtrag nicht
geändert.

## Warm-up-Befund

Der reale manuelle Sechs-Schritt-Intake konnte den in `block9-v1` geforderten Endzustand
nicht erreichen:

- `business_domain`, `business_capability` und `hosting_type` sind reale Intake-Eingaben,
  wurden von Benchmark A aber nicht als Fakten bereitgestellt.
- `summary` existiert im Intake, trägt dort jedoch die Semantik **„Heutiger Ablauf und
  Auslöser“**. Die v1-Summary war dafür nicht passend formuliert.
- `interface_description`, `benefit_category` und `human_oversight` sind keine Felder des
  Sechs-Schritt-Intakes, stehen aber im regulären Use-Case-Edit zur Verfügung.
- Der Intake setzt `decision_status` bewusst auf `ready`; `clarification` war daher eine
  falsche v1-Erwartung.
- `source_systems` und `data_sources` sind im aktuellen Code getrennte Intake-Felder und
  werden getrennt auf das UseCase-Modell geschrieben. Dafür gibt es keinen belegten
  Produktregressions-Befund.
- Die normale Text-Adoption des Accelerators deckt nicht alle 21 Scoring-Felder ab.
  Insbesondere `solution_type` ist kein Plain-Text-Adoptionsfeld; strukturierte Metriken
  laufen über den bestehenden Structured-Adoption-Pfad. Ein regulärer Use-Case-Edit bleibt
  für verbleibende Scoring-Felder zulässig und wird gemessen.

## Einordnung

### Kein Produktbug aus dem Warm-up abgeleitet

`decision_status=ready` ist im realen Intake explizites Produktverhalten. Die UI meldet nach
erfolgreichem Abschluss, dass der Use Case bereit zur Bewertung ist. Der Benchmark darf
dieses Verhalten nicht künstlich auf `clarification` zurücksetzen.

Auch eine systematische Vermischung von Quellsystemen und Datenquellen ist im aktuellen
Mapping nicht vorhanden. Beide Werte werden getrennt gespeichert.

### Tatsächlicher AP-7-Gap

Der AP-7-Freeze wurde vor dem ersten Scored Run nicht ausreichend gegen die reale
Bedienoberfläche verifiziert:

1. Die v1-Faktengrundlage enthielt nicht alle für den Manual-Pfad erforderlichen Angaben.
2. Der v1-Endzustand verlangte Felder, die der Intake selbst nicht vollständig anbietet.
3. Der v1-Lifecycle-Endzustand widersprach dem produktiven Intake.
4. Der Accelerator-Endpfad war für alle 21 Scoring-Felder zu eng als reine Candidate-Adoption
   beschrieben.
5. Benchmark B war für einen behaupteten Ein-Lücken-Fall fachlich zu unvollständig.

## Entscheidung für `block9-v2`

`block9-v2` ändert **nicht das Produkt**, sondern korrigiert den Messvertrag:

- Die 21 fachlichen Scoring-Felder bleiben erhalten.
- Der Manual-Pfad beginnt weiterhin im realen Sechs-Schritt-Intake und führt danach über den
  regulären Use-Case-Edit, um `interface_description`, `benefit_category` und
  `human_oversight` zu vervollständigen. Diese zusätzliche Navigation ist Teil der
  End-to-End-Zeit.
- Die Summary wird als heutiger Ablauf/Auslöser formuliert.
- Fachdomäne `procurement`, Capability `Source-to-Pay` und Hosting `unknown` sind als
  explizite, nicht improvisierte Pfadfakten eingefroren.
- `decision_status` ist kein Scoring-Feld mehr. Der natürliche Pfadzustand wird protokolliert,
  aber nicht für den Speed-Vergleich künstlich normalisiert.
- Der Accelerator darf Structured Adoption und den regulären Use-Case-Edit für verbleibende
  Scoring-Felder verwenden; sämtliche Bedienzeit bleibt in der Messung.
- Benchmark B enthält jetzt alle sonst notwendigen fachlichen Angaben. Offen bleibt genau
  `support_responsibility`; `metric_target` bleibt genau der definierte Quellenkonflikt.
- Für B ist die Run-ID `accelerator-B-1` festgelegt.
- Die bisherige A-Reihenfolge bleibt unverändert.

## Versions- und Datenregel

Die kanonische v1-Prüfsumme bleibt:

`e3c894f6ee2a87cc7755380fc6dc43f7352796bfaa31cddd56491997f38f7dab`

Die kanonische v2-Prüfsumme lautet:

`d4f7431ac68bb94b05885ae25f323e4147cf68fb20977ecd18c2acdeef74e6d1`

Ein neuer Warm-up muss `block9-v2` gegen beide realen interaktiven Pfade verifizieren.
Erst danach darf `manual-A-1` starten. Bereits gemessene technische AP-9-Rohdaten werden
nicht wiederholt, ersetzt oder umetikettiert.
