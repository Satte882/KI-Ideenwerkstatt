# Architecture Advisor & Evaluated Solution Workflow – Manual Sanity Check

Datum: 2026-08-10
Basis: main @ 920aa8ad40188b67a5dec31b4dd90b8f737d82f5
Scope: #210, #211, #212, #213, #274

> Persönliche UI-Sichtung aus Nutzersicht. Kein formaler Abnahmenachweis.
> Beobachtungen in dieser Datei öffnen die abgeschlossenen Issues nicht automatisch wieder.

## 1. Lokale Basis

- Commit: `920aa8ad40188b67a5dec31b4dd90b8f737d82f5`
- Browser: Codex In-app Browser (Chromium)
- verwendetes OpenRouter-Modell: `openai/gpt-5-mini`
- Besonderheiten: Bestehender lokaler PostgreSQL-Datenbestand wurde ohne Reset weiterverwendet. Der im Arbeitsauftrag genannte Management-Befehl `create_bootstrap_data` existiert auf diesem Stand nicht; der lokale Compose-Start legt die Rollen bereits automatisch an.

## 2. Architecture Advisor

| Fall | Q1/Q2/Q3/Q4 | Angezeigtes Ergebnis | Warum | Warum kein Agent | Für mich plausibel? | Beobachtung / Frage |
| --- | --- | --- | --- | --- | --- | --- |
| A | Ja / Nein / Nein / Nein | `No LLM required` | Eine zuverlässige einfachere Lösung durch Prozessgestaltung, Standardsoftware oder Regeln reicht aus. | Nicht eingeblendet. | Ja | Fachlich klar; Mode-Bezeichnung bleibt trotz deutscher UI englisch. |
| B | Nein / Ja / Nein / Nein | `Controlled LLM` | Semantische Verarbeitung ist erforderlich; ein klar begrenzter LLM-Schritt reicht aus. | Keine dynamische Orchestrierung erforderlich. | Ja | Die Abgrenzung zum Agenten ist verständlich. |
| C | Nein / Ja / Ja / Nein | `LLM Workflow` | Mehrere getrennte KI-Schritte sind erforderlich, ihre Reihenfolge steht vollständig fest. | Schritte und Reihenfolge sind vorab bekannt. | Ja | Der wichtige Grenzfall „mehrere Schritte ≠ Agent“ wird klar erklärt. |
| D | Nein / Ja / Nein / Ja | `Bounded Agent` | Nächster freigegebener Schritt oder benötigtes Tool wird abhängig vom Zwischenzustand gewählt. | Nicht eingeblendet. | Ja | Dynamische Auswahl wird als entscheidendes Merkmal genannt. |
| E | Nein / Ja / Unklar / Nein | `Assessment open` | Keine eindeutige Zuordnung zu einer minimal hinreichenden Architekturklasse. | Nicht eingeblendet. | Ja | Offener Punkt: Eine unklare Antwort kann den Architecture Mode verändern. Sinnvoller Sicherheitsausgang. |
| F | Ja / Ja / Nein / Nein | `Assessment open` | Keine eindeutige Zuordnung zu einer minimal hinreichenden Architekturklasse. | Nicht eingeblendet. | Ja | Widersprüchliche Anforderungen werden ausdrücklich benannt; Fail-Closed-Verhalten verständlich. |
| G | Nein / Nein / Nein / Nein | `Assessment open` | Keine eindeutige Zuordnung zu einer minimal hinreichenden Architekturklasse. | Nicht eingeblendet. | Ja | Die Grenze der V1-LLM-Taxonomie wird konkret erklärt. |

## 3. Evaluated Solution Workflow

### 3.1 Generate

Beobachtungen:

- Drei klar unterscheidbare Entwürfe wurden erzeugt: organisatorische Änderung, regelbasierte Automatisierung und KI-/Assistenzlösung.
- Die Entwürfe beziehen sich auf Bottleneck, Übergaben, Rollen, Systeme, Geschäftsregeln und Leitplanken des Referenzprozesses.
- Quellen, Annahmen, offene Evidenz und Unsicherheit werden pro Feld sichtbar ausgewiesen.
- Quantitative Wirkungsbehauptungen werden überwiegend als noch zu erhebende Evidenz markiert; der Entwurf erfindet keine neue formale Baseline.
- Die technische Regelautomatisierung ist erkennbar komplexer als die organisatorische Alternative; diese Komplexität wird als Unsicherheit beziehungsweise Critic-Finding sichtbar.
- Die Oberfläche weist ausdrücklich darauf hin, dass weder Machbarkeit noch Integrationsaufwand bewertet und keine bevorzugte Option ausgewählt wurden.

### 3.2 Initial Critic

Beobachtungen:

- Findings vor Repair: organisatorisch 4, regelbasiert 4, Assistenz 3.
- Die Findings decken Abgrenzung, Bottleneck Fit, Quellenkonsistenz, Evidenzdisziplin und Komplexitätsproportionalität ab.
- Drei Findings waren als einmalig maschinell reparierbar markiert: Bottleneck-Abdeckung der organisatorischen und regelbasierten Option sowie erwarteter Beitrag der Assistenzoption.
- Findings nennen Option, betroffenes Feld, Begründung und gebundene Quellen. Aus Nutzersicht ist damit konkret erkennbar, was und warum problematisch ist.

### 3.3 Repair

Vorher:

- Organisatorische Bottleneck-Abdeckung behauptete allgemein eine Verringerung der manuellen Übertragung durch direkte Abstimmung.
- Regelbasierte Bottleneck-Abdeckung behauptete, viele Prüfungen könnten vorab ausgeführt werden, ohne die verbleibenden Entscheidungsübergaben konkret einzugrenzen.
- Der Assistenznutzen behauptete bessere Nachvollziehbarkeit und weniger manuelle Übertragungen ohne definierte Messgrößen.

Nachher:

- Die gespeicherten Repair-Patches grenzen Annahmen, verbleibende Übergaben, Unsicherheit und offene Evidenz deutlich genauer ein.
- Der Assistenznutzen wird ausdrücklich als qualitativ erwartet markiert; fehlende Metriken und Benchmarks werden benannt.

Beobachtungen:

- Es wurde genau ein Repair ausgeführt; ein zweiter Repair ist anschließend nicht verfügbar.
- Die drei gespeicherten Patches betreffen ausschließlich die drei adressierten Felder.
- Keine bevorzugte Option und keine Recommendation wurden erzeugt.
- Zum Zeitpunkt der Sichtung enthielt die Persistenz die reparierten Texte und der Final Critic bewertete diese, während die bearbeitbaren Vorschaufelder noch die ursprünglichen Texte zeigten. `TECH-001` wurde anschließend mit [PR #277](https://github.com/Satte882/KI-UseCase-Radar/pull/277) behoben.

### 3.4 Final Critic

Beobachtungen:

- Findings nach Repair: organisatorisch 2, regelbasiert 3, Assistenz 3.
- Mehrere ursprüngliche Findings verschwinden oder werden präziser neu eingeordnet. Die regelbasierte Bottleneck-Abdeckung wird nicht erneut beanstandet.
- Bei organisatorischer Bottleneck-Abdeckung und Assistenznutzen bleiben trotz präziserer Formulierungen nachvollziehbare Evidenzlücken offen.
- Der Status wechselt anschließend ausdrücklich zu `Human Review`; der maschinelle Pfad endet.

### 3.5 Human Review

Beobachtungen:

- Der erwartete Beitrag der organisatorischen Option wurde manuell um die Notwendigkeit einer Pilotmessung ergänzt.
- Die manuelle Änderung blieb nach Speichern und erneutem Öffnen erhalten.
- Die Oberfläche bleibt in `Human Review`; es wird keine Freigabe oder Auswahlentscheidung abgeleitet.
- KI-Entwurf, Repair-Metadaten und menschliche Bearbeitung bleiben als getrennte Zustände erhalten. Seit [PR #277](https://github.com/Satte882/KI-UseCase-Radar/pull/277) rendert die Preview daraus den effektiven Stand in der Reihenfolge Generator, Machine Repair und Human Edit.

## 4. Gate-Invarianten

| Zustand | Vorher | Nachher | Erwartung erfüllt? | Beobachtung |
| --- | --- | --- | --- | --- |
| Process Validation | Entwurf, 0 Validierungen | Entwurf, 0 Validierungen | Ja | Keine automatische Validierung. |
| Solution Selection | 0 Entscheidungen | 0 Entscheidungen | Ja | Keine automatische Auswahlentscheidung. |
| Recommendation | Referenzoption: Kandidat; keine bevorzugte Option | Referenzoption: Kandidat; keine bevorzugte Option | Ja | Advisor und Quality-Pfad ändern die Recommendation nicht. |
| Use Case | Nicht vorhanden | Nicht vorhanden | Ja | Keine automatische Ableitung. |
| Governance | Nicht vorhanden | Nicht vorhanden | Ja | Ohne Use Case kein Assessment/Review erzeugt. |
| Delivery Package | Nicht vorhanden | Nicht vorhanden | Ja | Keine automatische Erzeugung oder Freigabe. |
| Lifecycle Review | Nicht vorhanden | Nicht vorhanden | Ja | Keine Veränderung. |

Zusätzliche Invarianz der manuellen Referenzoption:

- `feasibility`: vorher `medium`, nachher `medium`
- `integration_effort`: vorher `high`, nachher `high`
- `evaluation_status`: vorher `assessed`, nachher `assessed`
- `recommendation`: vorher `candidate`, nachher `candidate`

## 5. UX-/Verständnisfragen

- [ ] UX-001: Architecture-Mode-Bezeichnungen (`No LLM required`, `Controlled LLM`, `LLM Workflow`, `Bounded Agent`, `Assessment open`) bleiben in einer sonst deutschen Oberfläche englisch.
- [ ] UX-002: Nach einem langen Generate-/Critic-Lauf wäre eine dauerhaft sichtbare Fortschrittsanzeige hilfreich; die Ergebnisse werden nach Abschluss auf der Preview-Seite nachvollziehbar dargestellt.

## 6. Fachliche Fragen

- [ ] FACH-001: Soll ein nach Repair weiterhin als „maschinell reparierbar“ markiertes Final-Critic-Finding visuell deutlicher erklären, dass trotzdem bewusst kein zweiter Repair angeboten wird?
- [ ] FACH-002: Welche minimale Evidenz reicht aus, damit qualitative Nutzenformulierungen nach Repair nicht erneut als fehlende Evidenz beanstandet werden?

## 7. Technische Auffälligkeiten

- [x] TECH-001: Erledigt mit [PR #277](https://github.com/Satte882/KI-UseCase-Radar/pull/277). Die Preview rendert den validierten effektiven Stand nach Machine Repair und optionalen Human Edits; die strukturierte Finding-Bindung an Option, Feld und Quelle ist durch Regressionstests abgesichert.
- [ ] TECH-002: Der im Arbeitsauftrag genannte Befehl `python manage.py create_bootstrap_data` ist auf `main` nicht vorhanden. Der dokumentierte lokale Compose-Start führt stattdessen Migrationen, `seed_roles` und `collectstatic` automatisch aus.

## 8. Mögliche Follow-ups

| ID | Beobachtung | Auswirkung | Erste Einordnung | Entscheidung |
| --- | --- | --- | --- | --- |
| TECH-001 | Reparierte Werte wurden nicht in den bearbeitbaren Preview-Feldern angezeigt. | Human Review konnte unbeabsichtigt auf veraltetem Text aufsetzen; das Repair-Ergebnis war in der UI nicht zuverlässig prüfbar. | Behobener Defekt | Erledigt mit [PR #277](https://github.com/Satte882/KI-UseCase-Radar/pull/277); effektiver Stand und Finding-Bindung sind regressionsgetestet. |
| UX-001 | Englische Mode-Bezeichnungen in deutscher Oberfläche. | Kleine Verständlichkeits- und Konsistenzhürde. | UX/Dokumentation | Produktentscheidung zur Lokalisierung treffen. |
| FACH-001 | Final Findings tragen teils weiter „Maschinell reparierbar“, obwohl der One-Shot verbraucht ist. | Kann die Erwartung eines zweiten Repairs wecken. | Fachlich/UX | Begriff oder erläuternden Hinweis prüfen. |

## 9. Gesamtfazit

### Was für mich stimmig funktioniert

- Advisor-Abstufung A–G ist fachlich plausibel, fail-closed und ohne Gate-Seiteneffekte.
- Generate, Initial Critic, genau ein Repair, Final Critic und Human Review werden in der vorgesehenen Reihenfolge ausgeführt.
- Findings sind optionen-, feld- und quellbezogen und damit aus Nutzersicht handlungsfähig.
- Manuelle Human-Review-Änderungen bleiben stabil erhalten.
- Alle geprüften Gate-Invarianten bleiben unverändert.

### Was mir noch unklar ist

- Ob verbleibende Final-Critic-Findings weiterhin als „maschinell reparierbar“ bezeichnet werden sollen, obwohl kein weiterer Repair zulässig ist.

### Was ich vor weiterer Nutzung ändern würde

- Keine weitere Änderung aus `TECH-001` erforderlich; die Abweichung zwischen sichtbarem Text und dem vom Final Critic bewerteten Repair-Stand ist mit [PR #277](https://github.com/Satte882/KI-UseCase-Radar/pull/277) behoben.
