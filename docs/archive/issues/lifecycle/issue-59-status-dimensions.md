# Statusdimensionen für Use Cases

Die Oberfläche trennt fünf fachlich unterschiedliche Zustände:

1. **Arbeitsphase** – aktuell priorisierter Pflichtschritt der Journey.
2. **Assessment** – Intake-bedingte Bewertungsreife und vorhandene Bewertungsversion.
3. **Freigabe** – Freigabereife, Blocker, Zweitfreigabe oder finale Entscheidung.
4. **Messung** – Definition und Ergebnis der primären Erfolgsmetrik.
5. **Lifecycle** – Idee, Prüfung, Pilot, Betrieb oder Beendet.

`Entscheidungsbereit` wird nur ausgegeben, wenn eine Bewertung vorhanden ist und die Voraussetzungen des konkreten Freigabe-Gates erfüllt sind. Vor dem Assessment lautet der Zustand `Bewertungsbereit`. Nach einer finalen positiven Freigabe wechselt die primäre Prüfung erst dann zum Pilot- beziehungsweise Lifecycle-Gate.
