# Evaluated Solution Workflow – UI-Playbook

Stand: AP10 – Abschluss von #212

## Zweck

Dieses Playbook prüft den nutzersichtbaren Quality-Control-Pfad in der bestehenden Block-7-Preview:

`Generate -> deterministic Validate -> Initial Critic -> optional exactly one Repair -> deterministic Validate -> Final Critic -> Human Review`

Es entsteht keine neue Hauptnavigation, keine neue Lösungsvergleichsseite und kein zusätzliches Governance- oder Auswahl-Gate. Die bestehenden Human-Edit- und Adoption-Aktionen bleiben verwendbar.

## Voraussetzungen

- lokaler Stack läuft auf dem aktuellen `main`;
- eine Prozessanalyse erfüllt die bestehende Block-7-Readiness;
- OpenRouter ist für Generation, Critic und optional Repair konfiguriert;
- die testende Person besitzt die bestehenden Bearbeitungsrechte für den Value Stream.

## Playbook A – Initial Critic ohne reparierbare Findings

1. Eine für Block 7 bereite Prozessanalyse öffnen.
2. „3 Lösungsentwürfe mit KI erstellen“ starten.
3. Nach erfolgreicher Generierung die bestehende Preview öffnen.
4. Im Bereich „KI-Qualitätsprüfung“ prüfen, dass Findings nach Lösungsrichtung und Kriterium dargestellt werden.
5. Pro Finding Option, optional betroffenes Feld, Begründung, referenzierte Sources und „Manuell prüfen“ kontrollieren.
6. Prüfen, dass kein Repair-Button angeboten wird.
7. Prüfen, dass „Human Review“ sichtbar ist.
8. Bestehende manuelle Bearbeitung und Übernahme weiterhin verwenden können.

Erwartung: Nicht reparierbare Findings führen direkt zu Human Review. Sie blockieren weder Human Edits noch den bestehenden Adoption-Pfad.

## Playbook B – genau ein gezielter Repair

1. Einen Generation-Run mit mindestens einem aktuellen reparierbaren Initial-Critic-Finding öffnen.
2. Prüfen, dass das Finding als „Maschinell reparierbar“ gekennzeichnet ist.
3. Prüfen, dass genau eine Aktion „Reparierbare Findings einmalig korrigieren“ angeboten wird.
4. Die Aktion einmal auslösen.
5. Nach erfolgreichem Repair die Preview erneut prüfen.
6. Kontrollieren, dass der Repair-Button nicht erneut angeboten wird.
7. Falls der Final Critic noch läuft, den Status „Final Critic ausstehend“ prüfen.
8. Nach terminalem Final Critic prüfen, dass der maschinelle Pfad in „Human Review“ endet – unabhängig davon, ob finale Findings verbleiben.
9. Prüfen, dass manuelle Bearbeitung und bestehende Übernahme weiterhin verfügbar bleiben, solange der bestehende Block-7-Preview-Zustand dies erlaubt.

Erwartung: Alle aktuellen reparierbaren Findings werden in einem einzigen, serverseitig gebundenen Repair-Versuch verarbeitet. Ein zweiter Repair ist nicht möglich.

## Playbook C – CAS-Stale nach Human Edit

1. Einen Generation-Run mit erfolgreichem Initial Critic und reparierbarem Finding öffnen.
2. Vor dem Repair mindestens ein Preview-Feld manuell verändern und speichern.
3. Die Preview erneut öffnen.
4. Prüfen, dass die Findings weiterhin sichtbar sind.
5. Prüfen, dass der Repair-Button nicht mehr angeboten wird.
6. Den expliziten Hinweis prüfen: „Vorschau wurde seit der Prüfung bearbeitet, Reparatur nicht mehr möglich.“
7. Die fachliche Prüfung manuell fortsetzen.

Erwartung: Der Whole-Preview-CAS verhindert einen Repair auf verändertem Quality-Snapshot. Beim Anzeigen der stale Preview entsteht kein Provider-Aufruf.

## Playbook D – Quellstand nach Critic verändert

1. Einen Generation-Run mit bereits erfolgtem Initial Critic öffnen.
2. Die zugrunde liegenden Prozessdaten nachträglich fachlich ändern.
3. Die alte Preview erneut öffnen.
4. Den bestehenden Hinweis „Veralteter Quellstand“ prüfen.
5. Prüfen, dass Bearbeitung und Übernahme wie bereits in Block 7 gesperrt sind.
6. Prüfen, dass kein Repair-Button angeboten wird.
7. Neu generieren, statt den alten Quality-Snapshot weiterzuverwenden.

Erwartung: Der bestehende Block-7-Stale-Vertrag bleibt führend. Das reine Öffnen der Preview löst weder Critic noch Repair aus.

## Playbook E – Critic-/Repair-/Final-Critic-Ausfall

Für jeden der drei Quality Steps separat einen terminalen Provider-/Quota-/Contract-Fehler erzeugen:

1. Die Preview nach dem Fehler öffnen.
2. Prüfen, dass der letzte deterministisch valide Preview-Zustand vollständig erhalten ist.
3. Prüfen, dass kein automatischer Retry angeboten oder ausgelöst wird.
4. Bei Initial-Critic-Ausfall direkt Human Review prüfen.
5. Bei Repair-Ausfall prüfen, dass der einmalige Versuch verbraucht ist und Human Review erfolgt.
6. Bei Final-Critic-Ausfall prüfen, dass die deterministisch valide reparierte Preview erhalten bleibt und Human Review erfolgt.

Erwartung: Quality-Control-Fehler zerstören keine valide Preview und erzeugen weder Bewertung, Empfehlung noch Domain-/Governance-Writes.

## Playbook F – Berechtigungsgrenze

1. Eine valide Preview mit reparierbarem Finding als berechtigte Person öffnen.
2. Den Repair-Endpunkt mit einem Benutzer ohne Bearbeitungsrecht am Value Stream aufrufen.
3. Prüfen, dass der Request abgewiesen wird.
4. Als berechtigte Person die Preview erneut öffnen und den unveränderten Zustand prüfen.

Erwartung: Der Quality-Control-Pfad erweitert die bestehenden Block-7-Berechtigungen nicht.

## Bekannte V1-Grenzen

- Ein persistierter Quality-Step ist one-shot. Ein Prozessabbruch nach Reservierung und vor terminaler Statusspeicherung kann einen Step im Zustand `running` hinterlassen; #212 enthält bewusst keinen Recovery-Worker oder automatischen Retry.
- Ein fehlgeschlagener Critic-, Repair- oder Final-Critic-Step wird innerhalb derselben Generation nicht erneut ausgeführt. Die valide Preview bleibt für Human Review erhalten.
- Semantische Zusammenführung konkurrierender Human-/Machine-Edits ist kein V1-Ziel; Whole-Preview-CAS lehnt den Repair stattdessen als stale ab.
- Die gemeinsame Real-DEMO-/adversariale End-to-End-Abnahme von Architecture Advisor und Evaluated Solution Workflow bleibt #213 vorbehalten.

## Abgrenzung

Der Bereich „KI-Qualitätsprüfung“ ist ausschließlich Quality Control. Er bewertet weder Machbarkeit noch Integrationsaufwand, erzeugt kein Ranking, wählt keine bevorzugte Lösung und ersetzt keine fachliche Entscheidung.
