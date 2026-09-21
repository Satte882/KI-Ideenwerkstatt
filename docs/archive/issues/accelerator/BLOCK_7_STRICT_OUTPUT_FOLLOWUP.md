# Block 7 Nachtrag – Strict Output, Auswahl und Retire

## Provider-Strict-Mode

Der Block-7-Providerpfad fordert weiterhin `response_format.type=json_schema`, `strict=true` und
`provider.require_parameters=true` an. Diese Parameter bleiben sinnvoll, werden aber nicht mehr
als alleinige Garantie für Schema-Adhärenz betrachtet.

Die aktuelle OpenRouter-Dokumentation weist darauf hin, dass native JSON-Schema-Ausgabe nur dort
funktioniert, wo das jeweilige Modell beziehungsweise der jeweilige Provider die Methode
unterstützt. `require_parameters=true` verhindert Routing zu Providern, die die gesendeten
Parameter nicht unterstützen; daraus folgt jedoch keine Garantie, dass ein Modell bei komplexen
verschachtelten Schemas jeden Pflichtschlüssel zuverlässig erzeugt.

OpenRouter dokumentiert außerdem ausdrücklich, dass Response Healing nur beschädigtes JSON
repariert und keine Schema-Adhärenz sicherstellt. Fehlende Required-Properties, falsche Typen oder
falsche Feldnamen bleiben damit eine Anwendungspflicht. Der serverseitige Block-7-Validator ist
deshalb die autoritative Sicherheitsgrenze und kein optionales Backup.

Quellen, geprüft am 07.08.2026:

- https://openrouter.ai/blog/tutorials/langchain-chatopenrouter-setup/
- https://openrouter.ai/announcements/response-healing-reduce-json-defects-by-80percent
- https://openrouter.ai/provider/deepseek

## Konsequenz für Block 7

Prompt-Version 1.2 verschärft nicht die Validierung, sondern den Erzeugungsvertrag:

- Jedes der zehn Felder jeder der drei Optionen muss als vollständiges Statement-Objekt vorliegen.
- `text`, `source_ids`, `assumptions`, `open_evidence` und `uncertainty` sind immer vorhanden.
- Leere Listen werden explizit als `[]` ausgegeben und nie weggelassen oder durch `null` ersetzt.
- Der Providerinput enthält zusätzlich eine kanonische `statement_shape`-Vorlage.
- Das JSON-Schema beschreibt die verschachtelten Pflichtfelder explizit.
- Es gibt weiterhin keinen automatischen zweiten LLM-Aufruf und keine serverseitige Erfindung
  fehlender Provenienzfelder.

Der konfigurierte Runtime-Modellname bleibt über
`python manage.py show_accelerator_llm_policy` sichtbar. Ein Modellwechsel erfolgt nicht still im
Code. Wenn ein konkretes Runtime-Modell wiederholt strukturell scheitert, ist die nächste Maßnahme
ein bewusst konfiguriertes Modell beziehungsweise Provider-Routing mit dokumentierter
Structured-Output-Unterstützung, nicht das Lockern des Validators.

## Breitere Strukturregression

Die Regression prüft nicht nur den zuletzt beobachteten Einzelfall. Eine parametrisierte
Fehlermatrix verwirft unter anderem:

- fehlende Statement-Pflichtfelder,
- falsche Listentypen,
- ausgelassene leere Arrays,
- zusätzliche unbekannte Felder,
- gemischte Fehler in `source_ids` und `uncertainty`.

Ein vollständig korrektes Statement-Schema bleibt der positive Kontrollfall.

## Explizite Einzelauswahl in der Preview

Die zuvor visuell versteckte Bootstrap-`btn-check`-Steuerung wurde durch eine sichtbare Checkbox
pro KI-Vorschlag ersetzt. Alle drei Vorschläge sind nur als Ausgangszustand vorausgewählt; der
Nutzer bestätigt jeden Vorschlag einzeln. Die Hauptaktion zeigt dynamisch die Anzahl der aktuell
ausgewählten Optionen. `Vorschlag verwerfen` entfernt einen Preview-Entwurf ausschließlich aus
der geplanten Übernahme; der generierte Ursprungsinhalt bleibt aus Provenienzgründen erhalten und
kann mit `Wieder aufnehmen` erneut gewählt werden.

## Nicht weiterverfolgte gespeicherte Lösungsoptionen

Gespeicherte `SolutionOption`-Objekte werden nicht physisch gelöscht. Eine separate
`SolutionOptionRetirement`-Entität hält Option, Zeitpunkt und handelnde Person fest. Retirierte
Optionen bleiben im Auditbestand erhalten, werden als verworfen markiert und aus dem aktiven
Vergleich sowie aus der bevorzugten Auswahl ausgeschlossen.

Die Retire-Aktion verwendet dieselbe Value-Stream-Bearbeitungsberechtigung wie das Bearbeiten der
Option. Server-seitig ausdrücklich gesperrt sind:

- bevorzugte Optionen,
- Optionen, die bereits Gegenstand einer `SolutionSelectionDecision` waren,
- Optionen mit verknüpftem `UseCaseOrigin`.

Damit kann eine bereits getroffene Auswahl oder eine bestehende Use-Case-Herkunft nicht durch
einen nachträglichen Retire-Schritt entwertet werden.
