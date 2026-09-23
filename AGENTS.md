# Repository-Arbeitsregeln

## Aktueller verbindlicher Produktauftrag

Der aktuelle verbindliche Produktauftrag ist GitHub Issue
[#1 „10x: Autonomes Evidence-to-Decision-System“](https://github.com/Satte882/KI-Ideenwerkstatt/issues/1).

Bis zum Abschluss dieses Auftrags bestimmt Issue #1 Produktziel, Scope und Priorisierung.
Frühere Roadmap-Prioritäten, Execution-Pläne und die historische Basisspezifikation sind
Ausgangslage und Referenz, begrenzen Issue #1 aber nicht.

**Satte882/KI-UseCase-Radar ist der eingefrorene Referenzstand und darf weder lokal noch
remote verändert werden. Alle Arbeiten erfolgen ausschließlich in Satte882/KI-Ideenwerkstatt.**

Vor fachlichen Produktänderungen müssen mindestens gelesen werden:

1. GitHub Issue #1;
2. [`docs/ROADMAP.md`](docs/ROADMAP.md);
3. relevante Architecture Decision Records unter [`docs/adr/`](docs/adr/);
4. die zum aktuellen Arbeitspaket gehörenden Anforderungen und Akzeptanzkriterien.

Vor Änderungen an Benutzeroberflächen muss zusätzlich [`DESIGN.md`](DESIGN.md)
vollständig gelesen werden.

## Fachliche Invarianten

Diese Grenzen dürfen durch die 10x-Transformation nicht stillschweigend aufgehoben werden:

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

## Arbeitsweise für Issue #1

- Vorhandene Domain-Objekte und Provenance als Arbeitsgedächtnis und Source of Truth
  weiterverwenden; keinen parallelen zweiten Workflow bauen.
- Bestehende Methodik und Abläufe kritisch prüfen. Regeln, die nur aus früheren
  Modell-/Agentenlimits entstanden sind und das 10x-Ziel behindern, dürfen vereinfacht
  oder ersetzt werden, sofern die oben genannten Invarianten erhalten bleiben.
- In wenigen großen, output-orientierten Arbeitspaketen arbeiten. Ein künstliches
  „kleine PRs um jeden Preis“-Gebot gilt für Issue #1 nicht.
- Reversible technische Entscheidungen selbständig treffen; nur irreversible
  fachliche Entscheidungen oder echte Produkt-Trade-offs eskalieren.
- Keine neuen Agenten, Formulare, Scores, Statusmodelle, Prompts oder Dokumentation
  ohne messbaren Beitrag zu weniger Human Work, kürzerer Time-to-Decision oder besserer
  Outputqualität.
- Funktionsfähigkeit und fachliche Ergebnisqualität des autonomen Consultants vor
  Token- oder Kostenoptimierung priorisieren. Harte Budgets, persistente Abrechnung
  und Safety-Grenzen bleiben verbindlich.
- `docs/ROADMAP.md` aktualisieren, wenn sich Produktziel, erreichte Capability oder
  Priorisierung tatsächlich ändert.
- `OPEN_QUESTIONS.md` enthält Betriebs- und Konfigurationsfragen; es steuert nicht die
  Produktpriorität.

## Verbindliche UI-Regeln

- Das Design-System aus `DESIGN.md` ist für produktive UI-Änderungen verbindlich.
- Ausschließlich die dort definierten semantischen Tokens verwenden.
- Berechtigungen und serverseitige fachliche Regeln bei visuellen Änderungen erhalten.
- Neue oder geänderte Oberflächen gegen die Abnahmekriterien in `DESIGN.md` prüfen.
- Harte Verbote aus `DESIGN.md` nicht stillschweigend umgehen. Wenn Issue #1 eine
  bewusste Änderung des Design-Systems erfordert, diese Änderung explizit und
  nachvollziehbar im selben Arbeitskontext vornehmen.
