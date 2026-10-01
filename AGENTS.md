# Repository-Arbeitsregeln

## Aktueller verbindlicher Produktauftrag

Der aktuelle verbindliche Produktauftrag ist GitHub Issue
[#106 „Performance nach AI Business Architect: Adaptive Investigation Latency reduzieren“](https://github.com/Satte882/KI-Ideenwerkstatt/issues/106).

Issue #1 „10x: Autonomes Evidence-to-Decision-System“ ist technisch abgeschlossen und bildet
mit AP1–AP4 die funktionale Produktbaseline. Für #106 werden Performance-Änderungen erst nach
Mess- und Qualitätsvertrag, aktueller Baseline und dokumentiertem Entscheidungsgate ausgewählt.

Aktuell freigegebenes Arbeitspaket ist
[#110 „AP0 – Mess-, Qualitäts- und Experimentvertrag“](https://github.com/Satte882/KI-Ideenwerkstatt/issues/110).
AP0 darf **keine Performance-Optimierung** implementieren.

**Satte882/KI-UseCase-Radar ist der eingefrorene Referenzstand und darf weder lokal noch
remote verändert werden. Alle Arbeiten erfolgen ausschließlich in Satte882/KI-Ideenwerkstatt.**

Vor fachlichen Produkt- oder Runtime-Änderungen müssen mindestens gelesen werden:

1. GitHub Issue #106;
2. das aktuell freigegebene #106-Sub-Issue;
3. `docs/planning/ISSUE_106_PERFORMANCE_CONTRACT.md`;
4. relevante Architecture Decision Records unter `docs/adr/` sowie bei Bedarf `docs/ROADMAP.md`.

Vor Änderungen an Benutzeroberflächen muss zusätzlich `DESIGN.md` vollständig gelesen werden.

## Fachliche Invarianten

- Menschen bleiben Source of Authority für verbindlichen Scope, Risikoakzeptanz,
  Freigaben, Pilotstart und Go-live.
- Fehlende Fakten, Messwerte oder Evidenz werden nicht erfunden; Unbekanntes bleibt
  explizit als unbekannt oder als Hypothese gekennzeichnet.
- Relevante Aussagen und Ableitungen bleiben auf Quellen, Evidenz oder explizite
  Annahmen zurückführbar.
- Lösungsoffenheit bleibt erhalten: organisatorische Änderungen, Standardsoftware,
  regelbasierte oder klassische Automatisierung sowie KI sind echte Alternativen.
- Berechtigungen, fachlich notwendige Hard Gates und unveränderliche
  Entscheidungs-/Quell-Snapshots dürfen nicht umgangen oder stillschweigend entwertet werden.

## Arbeitsweise für Issue #106

- #106 bleibt Parent-Issue und verbindliche Quelle für Plan, Gates und Abschlussstatus.
- Pflichtreihenfolge: #110 Messvertrag → #111 Baseline/A-A → #112 Kandidatenentscheidung.
  Danach werden nur tatsächlich ausgewählte Experimente als eigene Sub-Issues umgesetzt.
- Nach jedem Experiment gibt es ein neues Gate. Ein direkter Abschluss über #113 ist jederzeit
  zulässig, wenn kein weiterer Hebel genügend belegten Nutzen gegenüber Risiko und Aufwand bietet.
- Keine Performance-Änderung ohne aktuelle Messgrundlage und vorab definierte Übernahmehürde.
- Fehlgeschlagene, langsame oder abgebrochene Benchmark-Runs bleiben Evidence und dürfen nicht
  durch bessere Ersatzläufe unsichtbar gemacht werden.
- Der zu optimierende Verifier bewertet nicht allein seine eigene Qualität. Deterministische
  Checks und begrenzte menschliche Bewertung bleiben Referenz.
- Kritische Qualitätsfehler dürfen nicht durch Durchschnittsscores kompensiert werden.
- Menschliche Wartezeit bei WAITING_HUMAN wird nicht als Runtime-Latenz gewertet.
- Je Experiment möglichst genau einen technischen Hebel ändern. Batching, Model Routing,
  Synthesizer-Vertrag und Parallelisierung nicht in einen Sammel-PR mischen, wenn dadurch die
  Ursache der Wirkung nicht mehr isolierbar ist.
- Contract-, Prompt-, Schema-, Routing- oder Runtime-Änderungen müssen Versionierung,
  alte eingefrorene Runs, Replay/Recovery und Rollback explizit behandeln.
- Vorhandene Domain-Objekte, Provenance und der server-owned Investigation-State bleiben
  Source of Truth; keinen parallelen zweiten Workflow bauen.
- Reversible technische Entscheidungen innerhalb des freigegebenen Experimentvertrags können
  selbständig umgesetzt werden. Irreversible fachliche Trade-offs oder Budgeterweiterungen
  werden im Parent #106 entschieden.
- `docs/ROADMAP.md` aktualisieren, wenn sich Produktziel, erreichte Capability oder
  Priorisierung tatsächlich ändert.
- `OPEN_QUESTIONS.md` enthält Betriebs- und Konfigurationsfragen; es steuert nicht die
  Produktpriorität.

## Verbindliche UI-Regeln

- Das Design-System aus `DESIGN.md` ist für produktive UI-Änderungen verbindlich.
- Ausschließlich die dort definierten semantischen Tokens verwenden.
- Berechtigungen und serverseitige fachliche Regeln bei visuellen Änderungen erhalten.
- Neue oder geänderte Oberflächen gegen die Abnahmekriterien in `DESIGN.md` prüfen.
- Harte Verbote aus `DESIGN.md` nicht stillschweigend umgehen.
