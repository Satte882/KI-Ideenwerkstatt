# Repository-Arbeitsregeln

## Geltungsbereich

**Satte882/KI-UseCase-Radar ist der eingefrorene Referenzstand und darf weder lokal noch
remote verändert werden. Alle Arbeiten erfolgen ausschließlich in Satte882/KI-Ideenwerkstatt.**

Vor einer Änderung ist das jeweils beauftragte GitHub-Issue vollständig zu lesen. Gibt es
kein Issue, ist die konkrete Benutzeranforderung der Arbeitsauftrag. Issue-spezifische
Reihenfolgen, Experimente und Gates gehören in das jeweilige Issue und nicht dauerhaft in
diese Datei.

Zusätzlich sind je nach Änderung zu lesen:

- relevante Architecture Decision Records unter `docs/adr/`;
- `docs/ROADMAP.md`, wenn Produktziel, Capability oder Priorisierung betroffen sind;
- `DESIGN.md` vollständig vor produktiven UI-Änderungen.

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
- Vorhandene Domain-Objekte, Provenance und server-owned State bleiben Source of Truth;
  keinen parallelen zweiten Workflow oder redundante Fachlogik aufbauen.

## Arbeitsweise

- Änderungen eng am beauftragten Problem halten; keine vorsorglichen Features,
  Framework-Wechsel oder Refactorings ohne konkreten Nutzen.
- Bestehende Service- und Domainlogik wiederverwenden statt UI-, API- oder Agentenpfade
  mit eigener Geschäftslogik zu duplizieren.
- Bei Änderungen an Contracts, Prompts, Schemas, Routing oder Runtime bestehende
  gespeicherte Zustände, Replay/Recovery und Rückwärtsverträglichkeit berücksichtigen.
- Reversible technische Entscheidungen innerhalb des Auftrags können selbständig
  umgesetzt werden. Irreversible fachliche Trade-offs oder Scope-Erweiterungen müssen
  explizit entschieden werden.
- Änderungen mit passenden zielgerichteten Tests absichern; bestehende CI-, Security-
  und Migrationsprüfungen nicht umgehen.
- `docs/ROADMAP.md` nur aktualisieren, wenn sich Produktziel, erreichte Capability oder
  Priorisierung tatsächlich ändert.
- `OPEN_QUESTIONS.md` enthält Betriebs- und Konfigurationsfragen; es steuert nicht die
  Produktpriorität.

## Verbindliche UI-Regeln

- Das Design-System aus `DESIGN.md` ist für produktive UI-Änderungen verbindlich.
- Ausschließlich die dort definierten semantischen Tokens verwenden.
- Berechtigungen und serverseitige fachliche Regeln bei visuellen Änderungen erhalten.
- Neue oder geänderte Oberflächen gegen die Abnahmekriterien in `DESIGN.md` prüfen.
- Harte Verbote aus `DESIGN.md` nicht stillschweigend umgehen.
