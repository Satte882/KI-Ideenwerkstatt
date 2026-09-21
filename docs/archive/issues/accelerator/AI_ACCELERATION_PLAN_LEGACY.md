# Finaler Plan: Baseline-Abschluss und KI-beschleunigte Delivery

**Version:** 1.0  
**Status:** Umsetzungsplan  
**Empfohlener Speicherort:** `docs/AI_ACCELERATION_PLAN.md`

## 1. Ziel

Der bestehende manuelle End-to-End-Prozess wird zunächst als funktionale Baseline abgeschlossen und stabilisiert.

Anschließend wird ein **Evidence-to-Framework Copilot** entwickelt, der bestätigte fachliche Evidenz in ein strukturiertes Delivery Package überführt.

Das Ziel ist nicht, generische Texte zu erzeugen, sondern:

```text
Bestätigte Quellen
→ frameworkkonforme Zuordnung
→ nachvollziehbare Feldvorschläge
→ Lücken und Widersprüche
→ menschliche Prüfung
→ versionierte Übernahme
```

Die KI darf keine verbindlichen Inhalte selbst freigeben.

---

## 2. Dokumentierter Ausgangspunkt

Der Referenzdurchlauf `KI-0154` wurde vollständig durchgeführt:

```text
Value Stream
→ Fokus und Priorisierung
→ Prozessanalyse
→ Lösungsoption
→ Use-Case-Intake
→ Bewertung
→ Governance
→ Freigabe
→ Delivery Package
→ verbindliche Übergabe
→ Pilotstart
```

### Gemessener Aufwand

**Circa sechs Stunden aktive Bearbeitungszeit.**

Der Wert wird ausdrücklich als **beobachteter Referenzdurchlauf** dokumentiert:

- ein einzelner Use Case,
- bekanntes und vorbereitetes Beispiel,
- direkte Unterstützung durch einen KI-Assistenten,
- inklusive Fehlersuche, Rollenwechsel und Workarounds,
- inklusive mehrerer während des Durchlaufs behobener Routing- und Workflowfehler.

Der Wert ist damit keine statistische Durchschnittszeit. Er zeigt aber belastbar:

- die Größenordnung des aktuellen Bedienaufwands,
- die wesentlichen Zeitfresser,
- die Reibung durch Wiederholungen und unklare Übergänge,
- den möglichen Automatisierungshebel.

Aussagen wie „viermal schneller“ oder „sechsmal schneller“ werden später nur anhand vergleichbarer Kontroll- und KI-Durchläufe getroffen.

---

## 3. Baseline-Abschluss

### 3.1 Mängel konsolidieren

Alle Beobachtungen aus dem Referenzdurchlauf werden als GitHub Issues erfasst und einer der folgenden Klassen zugeordnet.

| Klasse | Definition |
|---|---|
| **P0** | Datenverlust, falscher Statusübergang, fehlerhafte Berechtigung, fehlende Auditierbarkeit oder nicht abschließbarer Golden Path |
| **P1-A: KI-blockierend** | Fehler verfälscht Quellen, Rollen, Zustände, Messzeiten oder die spätere Bewertung des KI-Copiloten |
| **P1-B: nicht KI-blockierend** | Relevantes UX-Problem, das den KI-Versuch aber nicht fachlich oder messtechnisch ungültig macht |
| **P2** | Kosmetik, Komfort oder spätere Optimierung |

### 3.2 Regel für „KI-blockierend“

Ein Problem ist **P1-A**, sobald mindestens eine der folgenden Aussagen zutrifft:

- Die KI erhält falsche, veraltete oder nicht eindeutig zuordenbare Quellen.
- Die bestätigende Rolle oder Person ist nicht zuverlässig nachvollziehbar.
- Eingaben oder Review-Begründungen können verloren gehen.
- Der aktuelle Lifecycle- oder Readiness-Status wird falsch dargestellt.
- Der Nutzer wird zur falschen Aktion oder zum falschen Gate geführt.
- Manuelle und KI-unterstützte Durchläufe wären nicht fair vergleichbar.
- Herkunft, Änderung oder Bestätigung eines KI-Vorschlags könnte nicht revisionsfähig gespeichert werden.

Vor dem KI-MVP werden nur **P0 und P1-A** verbindlich behoben. P1-B und P2 dürfen parallel im Backlog bleiben.

### 3.3 Baseline einfrieren

Nach Behebung von P0 und P1-A:

- Golden Path technisch erneut prüfen,
- keine Datenbankmanipulation,
- keine manuellen URL-Aufrufe,
- keine Rollen-Workarounds,
- Tests für alle gefundenen Routing- und Berechtigungsfehler,
- Git-Tag setzen, beispielsweise:

```text
baseline-manual-v1
```

Der Sechs-Stunden-Durchlauf bleibt als historische Referenz erhalten. Ein kontrollierter manueller Vergleichsdurchlauf erfolgt später auf diesem eingefrorenen Stand.

---

## 4. Scope des ersten KI-MVP

### Einziger Zielbereich

**Delivery Package**

Nicht Bestandteil des ersten MVP:

- automatische Erstellung des gesamten Use-Case-Intakes,
- freie Chatbot-Unterhaltung,
- PDF- oder Office-Dateiimport,
- Confluence-, SharePoint- oder Jira-Connectoren,
- automatische Freigaben,
- automatische Lifecycle-Entscheidungen,
- direkte Änderung bestätigter Inhalte.

### Einzige Eingangsquelle

Der erste MVP verwendet ausschließlich bereits im System vorhandene und bestätigte Artefakte:

- Value Stream und Fokus,
- Prozessanalyse,
- bevorzugte Lösungsoption,
- Use-Case-Stammdaten,
- strukturierte Bewertung,
- Governance-Screening,
- Freigabeentscheidung,
- Auflagen,
- Rollen und Verantwortlichkeiten.

Damit wird zunächst ausschließlich die fachliche Kernfrage getestet:

> Kann die KI vorhandene Evidenz korrekt, nachvollziehbar und frameworkkonform in ein Delivery Package überführen?

Dateiextraktion und externe Systeme würden diesen Test unnötig mit weiteren Fehlerquellen vermischen.

---

## 5. Frameworkgebundene Generierung

Die KI erhält kein allgemeines Schreibkommando. Für jedes Delivery-Feld werden definiert:

- fachlicher Zweck,
- erforderliche Eingangsevidenz,
- zulässige Quellen,
- erwartete Struktur,
- Mindestinhalt,
- unzulässige generische Formulierungen,
- erforderliche Verknüpfungen zu anderen Feldern,
- Prüfkriterien,
- Beispiele für zulässige und unzulässige Ergebnisse.

Die Ausgabe erfolgt als strukturiertes Schema, nicht als unkontrollierter Fließtext.

Beispiel:

```json
{
  "field": "human_oversight",
  "suggested_value": "...",
  "origin": "mixed",
  "source_references": ["approval.conditions.2", "governance.human_oversight"],
  "open_questions": [],
  "conflicts": [],
  "evidence_confidence": "high"
}
```

### Anti-Generik-Regeln

Ein Vorschlag darf nicht übernommen werden, wenn er:

- keinen Quellenbezug besitzt,
- lediglich das Feldlabel umformuliert,
- abstrakte Platzhalter wie „konkretisieren“ enthält,
- neue Tatsachen ohne Kennzeichnung erfindet,
- bestehende Auflagen abschwächt,
- Scope oder Autonomiegrenzen erweitert,
- Risiken ohne passende Kontrollmaßnahme ausblendet.

Fehlende Informationen führen zu einer offenen Frage, nicht zu erfundenem Text.

---

## 6. Integration in das bestehende Nachweismodell

Es wird kein paralleles KI-Auditmodell aufgebaut.

### Bestehende Struktur bleibt führend

- `content_origin`
- `review_status`
- `source_manifest`
- fachliche Bestätigung
- technische Bestätigung
- Reviewer, Zeitstempel und Review-Notiz

### Erweiterung des `source_manifest`

Das Manifest wird um feldbezogene Einträge ergänzt:

```text
Feld
Vorschlagswert
Herkunftsart
Quellenreferenzen
Quellenausschnitte
Evidenz-Confidence
Konflikte
Offene Fragen
Modell und Modellversion
Prompt-/Framework-Version
Erzeugungszeitpunkt
Übernommen, geändert oder verworfen
Bestätigende Person und Zeitpunkt
```

Die Sektion behält ihren aggregierten Status:

```text
needs_review
confirmed
blocked
not_applicable
```

Ein Feldvorschlag darf den Sektionsstatus nicht selbst auf `confirmed` setzen.

### Herkunft

Die vorhandenen Kategorien werden weiterverwendet:

| Herkunft | Bedeutung |
|---|---|
| `inherited` | vollständig aus bestehenden bestätigten Quellen übernommen |
| `mixed` | aus Quellen übernommen und für Delivery ergänzt |
| `new` | neuer Delivery-spezifischer Vorschlag |
| `not_applicable` | begründet nicht anwendbar |

---

## 7. Evidenz-Confidence

Es wird keine subjektive Selbsteinschätzung des Sprachmodells verwendet.

Die Confidence wird aus vier nachvollziehbaren Kriterien abgeleitet:

| Kriterium | Frage |
|---|---|
| **Direktheit** | Steht die Aussage ausdrücklich in einer Quelle oder wurde sie nur abgeleitet? |
| **Abdeckung** | Sind alle wesentlichen Bestandteile des Feldes belegt? |
| **Konsistenz** | Stimmen die verwendeten Quellen überein? |
| **Quellenstatus** | Stammt die Information aus einem bestätigten Artefakt? |

### Einstufung

**Hoch**

- Aussage ist explizit belegt,
- relevante Bestandteile sind vollständig abgedeckt,
- keine widersprechende Quelle,
- Quelle ist bestätigt.

**Mittel**

- Aussage ist überwiegend belegt,
- einzelne Bestandteile wurden nachvollziehbar abgeleitet,
- keine wesentlichen Widersprüche,
- Ergänzung muss geprüft werden.

**Niedrig**

- Aussage basiert auf Annahmen,
- Quelle ist unvollständig oder mehrdeutig,
- Quellen widersprechen sich,
- wesentliche Bestandteile fehlen.

### Kombinationsregel

Jedes der vier Kriterien wird zunächst einzeln als **hoch**, **mittel** oder **niedrig** eingestuft. Die Gesamteinstufung wird konservativ abgeleitet:

- **Hoch:** alle vier Einzelkriterien sind hoch.
- **Mittel:** kein Einzelkriterium ist niedrig und mindestens ein Einzelkriterium ist mittel.
- **Niedrig:** mindestens ein Einzelkriterium ist niedrig.

Ein vorhandener Quellenkonflikt setzt das Kriterium Konsistenz auf **niedrig** und führt damit immer zu einer niedrigen Gesamteinstufung, unabhängig von der Modellbewertung.

Zusätzlich zum Gesamtlabel werden die vier Einzelbewertungen und ihre Gründe gespeichert.

---

## 8. Schutz vor Automation Bias

### Verbindliche Regeln

1. KI-Vorschläge werden niemals automatisch bestätigt.
2. Jeder Vorschlag zeigt seine Quelle direkt neben dem Feld.
3. Änderungen zwischen Quelle, KI-Vorschlag und bestätigter Fassung bleiben als Diff sichtbar.
4. Neue Annahmen müssen ausdrücklich als Annahme markiert sein.
5. Vorschläge mit niedriger Confidence können nicht unverändert gesammelt bestätigt werden.
6. Konflikte müssen vor der Sektionsbestätigung aufgelöst oder begründet akzeptiert werden.
7. Eine Sektionsbestätigung bleibt eine bewusste Aktion der zuständigen Rolle.
8. Modell-, Prompt- und Framework-Version werden protokolliert.

### Prüflogik

| Confidence | Erforderliche Aktion |
|---|---|
| Hoch | prüfen, übernehmen, ändern oder verwerfen |
| Mittel | Quelle prüfen und Vorschlag explizit bestätigen oder ändern |
| Niedrig | manuell überarbeiten oder begründete Ausnahme dokumentieren |
| Konflikt | Bestätigung blockiert, bis der Konflikt aufgelöst oder begründet entschieden wurde |

### Stichprobenkontrolle

Während des KI-Piloten werden zusätzlich geprüft:

- mindestens 20 Prozent der übernommenen Vorschläge,
- mindestens drei Vorschläge je Delivery Package,
- bevorzugt Vorschläge, die unverändert übernommen wurden,
- Prüfung durch eine zweite fachlich oder technisch geeignete Person.

Die stichprobenprüfende Person darf nicht mit einer Person identisch sein, die die jeweilige Sektion ursprünglich fachlich oder technisch bestätigt hat. Ein Rollenkollaps, beispielsweise Business Owner und Technical Owner in einer Person, hebt diese Unabhängigkeitsanforderung nicht auf.

Bei kleinen Teams wird eine unbeteiligte fachlich oder technisch geeignete Person aus einem anderen Use Case, Team oder einer unabhängigen Koordinationsrolle eingesetzt. Steht keine solche Person zur Verfügung, wird die Stichprobe als **nicht unabhängig geprüft** gekennzeichnet, zählt nicht zum verbindlichen Mindestumfang und muss nachgeholt werden. Eine Selbstprüfung oder reine Rollenumschaltung gilt nicht als unabhängige Stichprobenkontrolle.

Erfasst werden:

- übersehene Fehler,
- unbelegte Aussagen,
- falsch zugeordnete Quellen,
- unbemerkte Bedeutungsänderungen,
- zu hoch eingestufte Confidence.

---

## 9. Nutzerführung des KI-MVP

Der Copilot arbeitet nicht als freier Chat, sondern als geführter Arbeitsbereich.

### Ablauf

```text
1. Quellenbestand anzeigen
2. Delivery-Vorschläge erzeugen
3. Vorschläge pro Sektion prüfen
4. Quellen und Confidence anzeigen
5. Konflikte und Lücken bearbeiten
6. Vorschläge übernehmen, ändern oder verwerfen
7. Sektion durch zuständige Rolle bestätigen
8. Bestehende Readiness-Prüfung ausführen
```

### Pro Feld sichtbar

- aktueller Wert,
- KI-Vorschlag,
- Quelle und Fundstelle,
- Herkunft,
- Confidence und Begründung,
- Konflikte,
- offene Fragen,
- Aktionen: Übernehmen, Bearbeiten, Verwerfen.

### Primäre Next Action

Je Seite wird weiterhin nur eine primäre Aktion gezeigt, beispielsweise:

```text
Nächsten offenen Delivery-Vorschlag prüfen
```

Nicht gleichzeitig:

- generieren,
- bestätigen,
- exportieren,
- Übergabe durchführen,
- weitere Optionen öffnen.

---

## 10. Mess- und Evaluationsdesign

### Zeitmessung

Gemessen wird **aktive Bearbeitungszeit**, nicht die organisatorische Kalendertage-Dauer.

Getrennt erfasst werden:

- fachliche Bearbeitungszeit,
- technische Bearbeitungszeit,
- Review-Zeit,
- Fehlersuche,
- Rollenwechsel,
- Systemwartezeit,
- nachträgliche Korrekturen.

### Qualitätsmetriken

- Anteil der KI-Vorschläge, die unverändert übernommen werden,
- Anteil der bearbeiteten Vorschläge,
- Anteil der verworfenen Vorschläge,
- Anzahl unbelegter Aussagen,
- Anzahl falsch zugeordneter Quellen,
- Anzahl erkannter Quellenkonflikte,
- Anzahl übersehener Quellenkonflikte,
- Anzahl später korrigierter bestätigter Inhalte,
- Vollständigkeit des Delivery Packages,
- Anzahl verbleibender Readiness-Blocker,
- Zeit bis „Bereit zur Übergabe“.

### Vergleichsszenarien

#### Szenario A: bekannter Referenzfall

Der Lieferantenauswahl-Use-Case wird auf dem eingefrorenen Baseline-Stand erneut durchgeführt:

- einmal manuell,
- einmal KI-unterstützt,
- gleiche Ausgangsdaten,
- gleiche Zielqualität.

#### Szenario B: unbekannte Use Cases

Mindestens drei zuvor nicht ausgearbeitete Use Cases mit unterschiedlicher fachlicher und technischer Komplexität werden durchgeführt:

- jeweils manuell oder mit minimaler Unterstützung,
- anschließend jeweils KI-unterstützt,
- fachliche Qualitätsprüfung jeweils durch eine zweite Person.

Damit wird verhindert, dass der bekannte Lieferantenfall oder ein einzelner unbekannter Testfall allein die Ergebnisse bestimmt.

### Zielhypothese

Die sechs Stunden bleiben der dokumentierte Referenzwert.

Für den ersten KI-MVP gilt:

| Ziel | Schwelle |
|---|---:|
| Mindesthypothese | mindestens Faktor 3 |
| Zielwert | höchstens zwei Stunden aktive Bearbeitungszeit |
| Stretch-Ziel | Faktor 4 beziehungsweise höchstens 90 Minuten |

Ein Beschleunigungsfaktor wird nur gemeinsam mit den Qualitätswerten veröffentlicht.

---

## 11. Abnahmekriterien des KI-MVP

Der MVP ist fachlich erfolgreich, wenn:

- alle Delivery-Sektionen unterstützt werden,
- jeder erzeugte Vorschlag eine Quelle oder eine explizite Kennzeichnung als neue Annahme besitzt,
- fehlende Evidenz zu Fragen statt erfundenen Angaben führt,
- Quellenkonflikte sichtbar werden,
- keine KI-Aktion eine menschliche Bestätigung ersetzt,
- das bestehende Readiness-Gate unverändert wirksam bleibt,
- P0- und P1-A-Fehler nicht auftreten,
- der vollständige Golden Path weiterhin funktioniert,
- der Zeitaufwand mindestens um Faktor 3 sinkt,
- in der Auditstichprobe keine stillen unbelegten Tatsachen bestätigt wurden.

---

## 12. Ausbau weiterer Eingangskanäle

Erst nach erfolgreicher Validierung des Delivery-MVP werden weitere Quellenadapter ergänzt.

### Ausbaureihenfolge

1. **Bestehende interne Artefakte**  
   Bereits Bestandteil des ersten MVP.

2. **Eingefügter Text**  
   Workshop-Notizen, Interviewprotokolle, E-Mails, vorhandene Beschreibungen.

3. **Dateiupload**  
   Word, PDF, Excel, PowerPoint, Markdown und Textdateien.

4. **Arbeitsplattformen**  
   Confluence, SharePoint, Jira, Azure DevOps und ähnliche Systeme.

5. **Geführtes KI-Interview**  
   Dynamische Fragen nur zu tatsächlich fehlenden oder widersprüchlichen Informationen.

Jeder Adapter überführt Inhalte in dieselbe Quellen- und Manifeststruktur. Es entstehen keine getrennten Workflows für PDF, Chat, Jira oder Confluence.

---

## 13. Arbeitspakete

| Paket | Inhalt | Exit-Kriterium |
|---|---|---|
| **AP0** | Referenzdurchlauf und Mängel dokumentieren | Sechs-Stunden-Durchlauf und Ursachen festgehalten |
| **AP1** | P0 und P1-A beheben | Golden Path ohne Workaround |
| **AP2** | Baseline taggen | `baseline-manual-v1` reproduzierbar |
| **AP3** | `source_manifest` feldbezogen erweitern | Quellen und Vorschläge revisionsfähig speicherbar |
| **AP4** | Framework-Schemata für Delivery-Felder definieren | jedes Feld besitzt Evidenz- und Qualitätsregeln |
| **AP5** | KI-Generierung aus internen Artefakten | strukturierte Vorschläge für alle Sektionen |
| **AP6** | Review-Oberfläche und Automation-Bias-Schutz | Übernahme, Diff, Konfliktprüfung und Bestätigung |
| **AP7** | Kontroll- und KI-Durchläufe messen | Zeit- und Qualitätsvergleich dokumentiert |
| **AP8** | Entscheidung über weitere Eingangskanäle | MVP fortführen, überarbeiten oder stoppen |

---

## 14. Unmittelbar nächster Umsetzungsschritt

Der nächste Entwicklungsumfang sollte ausschließlich enthalten:

```text
1. Referenzdurchlauf dokumentieren
2. Mängelliste konsolidieren
3. P0 und P1-A klassifizieren
4. P0 und P1-A beheben
5. manuellen Baseline-Stand taggen
```

Noch nicht Bestandteil dieses Inkrements:

- LLM-Anbindung,
- Promptentwicklung,
- Uploadfunktion,
- Chatoberfläche,
- Connectoren,
- automatische Delivery-Generierung.

Damit wird erst die manuelle Grundlage sauber abgeschlossen. Danach beginnt der klar abgegrenzte KI-MVP für das Delivery Package.
