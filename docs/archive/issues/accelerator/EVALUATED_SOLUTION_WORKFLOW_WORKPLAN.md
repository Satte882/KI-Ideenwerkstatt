# Evaluated Solution Workflow – verbindlicher Workplan

Issue: #212  
Parent: #210  
Stand: 2026-08-09  
Startbasis `main`: `662ef50d098b510ac80da9764d346d2e2b92d347`

## Ziel und Grenze

Der bestehende Block-7-Lösungsvergleich wird um einen kleinen, kontrollierten Quality-Control-Pfad erweitert:

`Generate -> deterministic Validate -> Critic -> optional exactly one Repair -> deterministic Validate -> final Critic -> Human Review`

Der vorhandene Block-7-Generierungs-, Validierungs-, Preview-, Human-Edit- und Übernahmepfad bleibt maßgeblich. Es entsteht kein zweiter Lösungsvergleich, keine Workflow-Engine, keine Critic-Plattform, kein Agent und kein neues fachliches Gate.

Critic und Repair dürfen niemals automatisch Bewertung, Rangfolge, Präferenz, Governance, Delivery oder Lifecycle verändern. Der letzte deterministisch valide Preview-Zustand bleibt bei jedem nachgelagerten Provider-, Critic- oder Repair-Fehler erhalten.

#210 bleibt unverändert. Die breitere Real-DEMO-/adversariale Gesamt-Abnahme bleibt Aufgabe von #213.

## Gap-Analyse gegen den tatsächlichen Startstand

Die Gap-Analyse wurde gegen `main` `662ef50d098b510ac80da9764d346d2e2b92d347` durchgeführt.

### Bestehender Block-7-Preview-/Provenance-Vertrag

- `SolutionGenerationRun` ist der bestehende Lauf für die drei Block-7-Lösungsrichtungen und speichert Prozessversion, Source Hash, Provider, Modell, Prompt-Version, Schema-Version, Laufzeit, Fehler-, Token- und Kostenmetadaten sowie `preview_payload`.
- Die Originaloptionen bleiben in `preview_payload["options"]` erhalten.
- Quellenkontext und Source IDs werden in der Preview mitgeführt und durch den bestehenden Contract validiert.
- Eine erfolgreiche Block-7-Preview ist bereits ein eigener, vor Domain Writes geschützter Zwischenzustand.

### Vorhandene deterministische Validierung

- `validate_solution_generation_payload(...)` ist die autoritative Block-7-Validierung für Schema, erlaubte Lanes/Felder, Source IDs, Provenance, numerische Claims und deterministisch erkennbare Struktur-/Duplikatfehler.
- Ein ungültiger Generator-Output wird fail-closed verworfen; danach darf kein Critic laufen.
- Vor der Übernahme werden Original und Human Edits erneut zu einem effektiven Payload zusammengesetzt und erneut mit demselben Validator geprüft.
- #212 baut keinen parallelen Validator. Critic, Repair und Adoption müssen denselben kanonischen Effective-Preview-Contract verwenden.

### Human-Edit-Semantik

- Human Edits überschreiben die Originalausgabe nicht, sondern liegen als separates Overlay unter `preview_payload["edits"]`.
- Die Originalausgabe bleibt damit nachvollziehbar.
- Für #212 wird dieses Overlay-Prinzip beibehalten: maschineller Repair wird ebenfalls separat gespeichert und überschreibt weder Original noch kollidierende Human Edits.
- Die effektive Reihenfolge lautet: Original -> erfolgreicher Machine-Repair -> Human Edits.

### Quoten, Provider und Kosten

Die bestehenden Accelerator-Grenzen bleiben unverändert und werden wiederverwendet:

- `ACCELERATOR_SOLUTION_GENERATION_MAX_CALLS_PER_CONTEXT=10`
- `ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY=20`
- `ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY=100`
- bestehender Timeout sowie Input-/Output-Limits

Der vollständige #212-Pfad benötigt maximal vier Modellaufrufe inklusive Generate und liegt damit unter der bestehenden Block-7-Kontextgrenze von zehn Aufrufen. Es wird keine Quote erhöht.

Der automatische Initial Critic erhöht die normale Aufrufzahl einer erfolgreichen Generierung von eins auf zwei. Das wird bewusst akzeptiert, weil der Critic Bestandteil des verbindlichen erweiterten Pfads ist und #212 nur für Repair ausdrücklich eine zusätzliche Nutzeraktion verlangt. Nutzer- und globale Tagesquoten bleiben harte Obergrenzen. Ist nach erfolgreicher Generierung keine Quote für den Initial Critic verfügbar oder schlägt der Provider fehl, bleibt die deterministisch valide Preview erhalten und geht ohne maschinelle Qualitätsprüfung in Human Review. Damit führt Quota-Druck nicht zum Verlust der bereits erzeugten Preview.

### Persistenzlücke

`SolutionGenerationRun` bildet einen Generatorlauf ab und ist nicht geeignet, zusätzlich Initial Critic, Repair und Final Critic jeweils mit eigener Lauf-, Fehler-, Provider-, Prompt-, Schema-, Token- und Kostenprovenance abzubilden.

V1 erhält deshalb genau eine kleine Child-Entität, bevorzugt `SolutionQualityRun`, bezogen auf `SolutionGenerationRun`. Sie ist keine generische Workflow-Engine und kennt ausschließlich die drei fixen Step Types:

- `initial_critic`
- `repair`
- `final_critic`

Jeder Step Type darf pro `SolutionGenerationRun` höchstens einmal reserviert werden.

## Kanonischer Effective-Preview-Contract

Vor Critic, Repair und Adoption wird dieselbe öffentliche Serverfunktion verwendet, um den aktuell effektiven Preview-Zustand aufzubauen und vollständig deterministisch zu validieren.

Sie berücksichtigt:

- unveränderte Originaloptionen;
- einen gegebenenfalls erfolgreich aktivierten Machine-Repair;
- Human Edits als höchstprioritäres Overlay;
- Source Context, Source Hash und Process Version;
- den bestehenden Block-7-Contract.

Damit gibt es nur eine Definition dessen, was eine aktuell sichtbare, übernehmbare und für #212 prüfbare Preview ist.

## Quality-Snapshot und CAS-Vertrag

Der Initial Critic bewertet einen eingefrorenen, kanonisch gehashten Quality-Snapshot.

Der Snapshot bindet mindestens:

- den vollständig deterministisch validierten effektiven Preview-Payload;
- Source Hash;
- Process Version;
- Generation Prompt-/Schema-Version;
- Critic Prompt-Version;
- Critic Output-Schema-Version;
- Repair Prompt-Version;
- Repair Output-Schema-Version;
- eine feste V1-Quality-Contract-Version.

Damit wird ein Repair nicht nur bei geändertem Preview-Inhalt, sondern auch bei geändertem Critic-/Repair-Vertrag nach einem Deployment als stale abgelehnt.

Das konkrete Modell ist Audit-Provenance, aber kein Teil des CAS-Vertrags. Ein Modellwechsel bei unverändertem versioniertem Prompt-/Schema-Contract ändert nicht die fachliche Semantik der erlaubten Findings oder Patches; er wird pro Step separat gespeichert. Dadurch entstehen keine unnötigen Stale-Zustände allein durch einen Provider-/Model-Rollout.

### Repair-CAS

Vor einem Repair wird der aktuelle Quality-Snapshot unter der dann aktiven Contract-Version erneut berechnet.

Nur wenn er exakt dem Snapshot des Initial Critic entspricht, darf der Repair starten.

Bei Abweichung:

- kein Provider-Aufruf;
- kein Repair;
- Human Review;
- sichtbarer UI-Hinweis: „Vorschau wurde seit der Prüfung bearbeitet, Reparatur nicht mehr möglich.“

V1 verwendet bewusst Whole-Preview-CAS statt semantischem Feld-Merge. Ein Finding kann optionenübergreifend sein; auch Änderungen außerhalb eines einzelnen Feldes können seine Bedeutung verändern. Whole-Preview-CAS ist daher konservativer, deterministisch und leichter reproduzierbar.

## Provider-Reservierung und Race-Schutz

Der Unique Constraint allein reicht nicht als Kosten-/Race-Schutz.

Für jeden Quality Step wird deshalb vor dem externen Provider-Aufruf in einer kurzen Transaktion eine persistierte `running`-Reservierung angelegt. Die Eindeutigkeit `(solution_generation_run, step_type)` wird auf Datenbankebene erzwungen.

Erst nach erfolgreichem Commit dieser Reservierung darf der Provider aufgerufen werden. Ein paralleler oder wiederholter Request findet den bereits reservierten Step und endet ohne weiteren Provider-Aufruf.

Es wird ausdrücklich keine Datenbanktransaktion und kein Row Lock über den Netzwerkaufruf gehalten. Der Schutz besteht aus kurzer atomarer Reservierung vor dem Call und terminaler Aktualisierung derselben Step-Zeile danach.

Ein fehlgeschlagener oder zeitlich abgelaufener Step bleibt als verbrauchter Versuch nachvollziehbar und wird innerhalb derselben Generation nicht erneut gestartet. Dadurch kann ein Queue-/Request-Retry nicht unbemerkt einen zweiten kostenpflichtigen Modellaufruf auslösen.

## Critic-Contract V1

Die Kriterien sind fest und nicht konfigurierbar:

1. `distinctiveness`
2. `bottleneck_fit`
3. `grounding_consistency`
4. `evidence_discipline`
5. `complexity_proportionality`

Der Critic bewertet ausschließlich semantische Qualitätsaspekte. Alles deterministisch Prüfbare bleibt Aufgabe des bestehenden Validators.

### Finding-Struktur

Jedes Finding enthält mindestens:

- `criterion`;
- primär betroffene Option/Lane;
- optional primär betroffenes Feld;
- Finding-Text;
- referenzierte Source IDs soweit vorhanden;
- `repairable`.

Der Server ergänzt eine stabile Finding-ID.

Für optionenübergreifende Findings darf der strukturierte Contract zusätzlich explizite `related_targets` mit weiteren `(Option, Feld)`-Paaren enthalten. Der primär betroffene Zielbezug bleibt erhalten; die Erweiterung dient ausschließlich dazu, Cross-Option-Probleme wie fehlende Distinctiveness reproduzierbar zu lokalisieren.

### Repairability

`repairable=true` ist nur zulässig, wenn mindestens ein konkretes erlaubtes Zielfeld benannt ist. Rein globale oder nicht lokalisierbare Findings bleiben `repairable=false` und gehen in Human Review.

Keine Severity, kein Score, kein Confidence Score, kein Pass/Fail-Gesamturteil, keine Rangfolge und keine bevorzugte Lösung werden eingeführt.

Ein leeres Findings-Array bedeutet: keine Repair-Aktion anzeigen und direkt Human Review.

Findings ohne reparierbare Ziele bedeuten ebenfalls: keine Repair-Aktion anzeigen und Human Review.

## Critic-Prompt und Rubber-Stamping-Schutz

Generator und Critic verwenden getrennte versionierte System-Prompts.

Der Critic-Prompt ist adversarial formuliert und verlangt insbesondere:

- aktiv nach den fünf definierten Qualitätsproblemen zu suchen;
- Findings konkret auf Option/Feld/Evidenz zu beziehen;
- keine Probleme zu erfinden;
- ein leeres Findings-Array ausdrücklich zuzulassen;
- keine Bewertung, Rangfolge oder Lösungsempfehlung zu erzeugen;
- keine Governance-Aussage oder Domain-Entscheidung zu erzeugen;
- keine mechanisch prüfbaren Schema-/Contract-Aufgaben des Validators zu duplizieren.

Critic-Prompt-Version, Critic-Schema-Version und verwendetes Modell werden pro Step auditierbar gespeichert.

## Initial Critic

Nach erfolgreichem Generate und vollständiger deterministischer Validierung wird die valide Preview zuerst persistent als erfolgreicher Block-7-Zustand gesichert.

Erst danach wird der `initial_critic`-Step reserviert und aufgerufen.

Dadurch kann ein Critic-/Quota-/Providerfehler die bereits valide Preview nicht zurückrollen oder zerstören.

Der Initial Critic läuft automatisch nach erfolgreicher Generierung. Ein zusätzlicher Benutzerbutton nur zum Starten des Critic wird nicht eingeführt.

## Repair-Scope und One-Shot-Regel

Repair erfolgt ausschließlich nach expliziter Nutzeraktion.

Ein erlaubter Repair-Versuch behandelt atomar alle zu diesem Zeitpunkt vorhandenen `repairable=true` Findings des aktuellen Initial-Critic-Snapshots. V1 bietet keine Auswahl einzelner Findings für getrennte Repair-Aufrufe.

Begründung: „maximal genau ein Repair-Versuch“ bleibt damit fachlich und technisch eindeutig. Selektive Einzelaufrufe würden aus einem One-Shot-Contract implizit mehrere mögliche Repair-Entscheidungen machen.

### Cross-Option-Repair

Ein einzelner Repair-Aufruf darf mehrere `(Option, Feld)`-Paare verändern, wenn diese Targets durch die reparierbaren Findings explizit freigegeben wurden. Das ist insbesondere für Cross-Option-Findings wie fehlende Distinctiveness erforderlich.

Der Repair darf jedoch keine zusätzlichen Ziele wählen und keine komplette Option oder den gesamten Bundle frei neu generieren.

### Repair-Output

Der Repair liefert ausschließlich strukturierte Patch-Operationen mit:

- referenzierter Finding-ID;
- erlaubtem Option-/Feld-Target;
- vollständigem Ersatz des bestehenden provenance-reichen Statements für dieses Feld.

Das Statement umfasst weiterhin Text, Source IDs, Annahmen, offene Evidenz und Unsicherheit, soweit der bestehende Block-7-Contract dies verlangt.

Damit kann beispielsweise ein Evidence-Discipline-Finding korrekt von einer Tatsachenbehauptung zu Annahme/offener Evidenz überführt werden, ohne den übrigen Lösungsentwurf neu zu generieren.

## Atomare Repair-Anwendung und Revalidierung

Ein Repair-Payload wird niemals direkt aktiv.

Serverseitige Reihenfolge:

1. Repair-Schema deterministisch validieren.
2. Finding-IDs und erlaubte Targets gegen den eingefrorenen Initial-Critic-Snapshot prüfen.
3. sicherstellen, dass ausschließlich freigegebene Targets verändert werden.
4. alle Patches atomar auf eine Kopie des effektiven Preview-Payloads anwenden.
5. den gesamten resultierenden Payload erneut durch `validate_solution_generation_payload(...)` schicken.
6. nur bei vollständigem Erfolg den Machine-Repair als aktiv markieren.

Scheitert eine Teilprüfung oder der vollständige Block-7-Contract, wird der gesamte Repair verworfen. Es gibt keine partielle Übernahme.

Original, Initial-Critic-Findings, Repair-Versuch, Repair-Patches und Ergebnis bleiben nachvollziehbar.

## Final Critic und zwingendes Ende

Nur nach einem erfolgreichen, vollständig deterministisch validierten Repair wird genau ein `final_critic` automatisch reserviert und ausgeführt.

Danach endet der maschinelle Pfad immer in Human Review:

- keine Findings -> Human Review;
- verbleibende Findings -> Human Review;
- Final-Critic-Ausfall -> Human Review mit der deterministisch validen reparierten Preview.

Ein weiterer Repair ist serverseitig unmöglich.

`Human Review` ist ein abgeleiteter UI-/Workflow-Endzustand von #212 und kein neues fachliches Governance-, Bewertungs- oder Auswahl-Gate.

## Maximale Modellaufrufe

Pro `SolutionGenerationRun` sind maximal möglich:

1. Generate über den bestehenden `SolutionGenerationRun`;
2. einmal `initial_critic`;
3. optional einmal `repair`;
4. nach erfolgreichem Repair optional einmal `final_critic`.

Die drei Quality Steps werden über fixe Step Types und Eindeutigkeitsregeln begrenzt. Die maximale Aufrufzahl wird nicht durch eine erhöhte Quote simuliert.

Es gibt keine automatische Retry-Schleife für Critic, Repair oder Final Critic.

## Fehlervertrag

| Fehlerfall | Ergebnis |
|---|---|
| Generate fehlerhaft | keine Preview |
| erste deterministische Validierung fehlerhaft | keine Preview, kein Critic |
| Initial-Critic-Quota/Provider/Contract fehlerhaft | valide Original-Preview bleibt, Human Review |
| Preview-/Prompt-/Schema-Contract seit Initial Critic verändert | kein Repair-Provider-Call, stale-Hinweis, Human Review |
| Repair-Provider fehlerhaft | letzter valider Preview-Zustand bleibt |
| Repair-Patch adressiert unzulässiges Target | vollständigen Repair verwerfen |
| Repair-Patch verletzt deterministischen Block-7-Contract | vollständigen Repair verwerfen |
| Final Critic fehlerhaft | deterministisch valide reparierte Preview bleibt, Human Review |
| Final Critic findet weitere Probleme | Human Review |
| zweiter Versuch desselben Quality Step | serverseitig ohne Provider-Aufruf ablehnen |

## Domain-/Gate-Invarianz

Critic und Repair dürfen insbesondere niemals automatisch verändern:

- `feasibility`;
- `integration_effort`;
- `evaluation_status`;
- `recommendation` oder bevorzugte Option;
- Process Validation;
- Solution Selection Decision;
- Use Case;
- Governance Assessment / Review;
- Delivery;
- Lifecycle.

Der bestehende Adoption-Pfad bleibt der einzige Weg, Preview-Inhalte als reguläre `SolutionOption` zu übernehmen.

Critic-Findings blockieren diese Übernahme technisch nicht. Der Critic ist Quality Control, kein Gate.

## UI-Ziel

#212 wird ausschließlich in die bestehende Block-7-Preview integriert. Es entsteht keine neue Hauptnavigation und keine neue Lösungsvergleichsseite.

Der kompakte Bereich „KI-Qualitätsprüfung“ zeigt:

- Findings gruppiert nach Option/Kriterium;
- optional betroffenes Feld;
- Finding-Begründung;
- referenzierte Sources;
- Kennzeichnung maschinell reparierbar / manuell prüfen;
- Hinweis: „Qualitätsprüfung – keine Bewertung oder Lösungsempfehlung.“

Nur wenn mindestens ein aktuelles reparierbares Finding vorhanden ist und der CAS-Vertrag unverändert ist, erscheint die einmalige Aktion „Reparierbare Findings einmalig korrigieren“.

Nach Verbrauch des Repair-Versuchs wird diese Aktion dauerhaft nicht mehr angeboten.

Wenn der CAS-Check beim Klick scheitert, zeigt die UI explizit: „Vorschau wurde seit der Prüfung bearbeitet, Reparatur nicht mehr möglich.“

Leeres Findings-Array oder ausschließlich nicht reparierbare Findings -> kein Repair-Button, direkt Human Review.

Bestehende Human-Edit- und Übernahmeaktionen bleiben verwendbar; Findings oder Critic-Ausfall erzeugen kein neues Gate.

## Arbeitspakete

### AP1 – Gap-Analyse und verbindlicher Workplan

- aktuellen `main`-Stand gegen #212 erneut verifizieren;
- Block-7-Preview-, Validator-, Human-Edit-, Provider-, Quota- und Persistenzverträge dokumentieren;
- Quality-Snapshot, Race-Schutz, Repair-Scope, Cross-Option-Semantik, Fehlervertrag und Nicht-Ziele verbindlich fixieren;
- dieses Dokument als ersten eigenständigen PR mergen;
- identische AP-Checkliste in #212 anlegen.

### AP2 – Effective-Preview-Contract, Quality-Snapshot und Version Freeze

- bisherige Effective-Payload-Logik aus dem Adoption-Pfad als gemeinsamen, serverseitigen Contract generalisieren;
- Adoption auf denselben Contract umstellen, ohne Verhalten zu ändern;
- kanonischen Quality-Snapshot und Hash implementieren;
- Generation-/Critic-/Repair-Prompt- und Schema-Versionen sowie V1-Quality-Contract-Version in den Snapshot binden;
- Snapshot-/Drift-Tests ergänzen.

### AP3 – Quality-Run-Persistenz, Reservierung und One-Shot-Zustandsmaschine

- kleine Child-Persistenz für `initial_critic`, `repair`, `final_critic` ergänzen;
- Status, Actor, Provider, Modell, Prompt-/Schema-Version, Input-Hash, Laufzeit, Fehler, Token/Kosten und strukturiertes Ergebnis auditierbar speichern;
- Eindeutigkeit `(solution_generation_run, step_type)` erzwingen;
- kurze atomare `running`-Reservierung vor jedem Provider-Aufruf implementieren;
- parallele Requests/Request-Retries ohne zweiten Provider-Call testen;
- fehlgeschlagene Steps als terminal verbrauchten Versuch behandeln.

### AP4 – Critic-Contract, Kriterien, Structured Output und adversarial Prompt

- exakt fünf feste Kriterien als Contract definieren;
- strukturiertes Finding-Schema einschließlich primärem Target und optionalen `related_targets` festlegen;
- serverseitige stabile Finding-IDs erzeugen;
- `repairable` nur für konkrete erlaubte Targets zulassen;
- separaten versionierten adversarial Critic-System-Prompt implementieren;
- leeres Findings-Array als gültigen positiven Ausgang zulassen;
- Scores, Ranking, Pass/Fail und Governance-/Auswahlwirkung explizit ausschließen.

### AP5 – Initial Critic, Quoten-/Provider-Integration und Failure Preservation

- Initial Critic ausschließlich auf vollständig deterministisch valider und bereits persistierter Block-7-Preview ausführen;
- bestehenden Provider-, Timeout-, Input-/Output-, User-/Global- und Kontextquota-Pfad wiederverwenden;
- keine Quoten erhöhen;
- Critic-/Quota-/Provider-/Output-Fehler so behandeln, dass die valide Preview unverändert nutzbar bleibt;
- maximal einen Initial-Critic-Aufruf pro Generation erzwingen;
- ersten Zwischenstatus liefern und `EVALUATED_SOLUTION_WORKFLOW_UI_PLAYBOOK.md` mit den zu diesem Stand manuell prüfbaren Preview-/Failure-Preservation-Schritten anlegen; Finding-Darstellung und Repair bleiben darin transparent als erst ab AP9 prüfbar markiert.

### AP6 – Repair-Contract, CAS-Staleness und Human-Edit-Schutz

- genau einen expliziten Repair-Versuch definieren, der alle aktuellen reparierbaren Findings gemeinsam verarbeitet;
- Whole-Preview-CAS gegen den eingefrorenen Initial-Critic-Snapshot implementieren;
- geänderte Preview-, Critic-, Repair-, Prompt- oder Schema-Verträge vor Provider-Aufruf als stale ablehnen;
- expliziten stale-Reason für die spätere UI bereitstellen;
- keine Überschreibung kollidierender Human Edits zulassen;
- Cross-Option-Findings auf explizit freigegebene Target-Paare begrenzen.

### AP7 – Atomarer Targeted Repair und deterministische Revalidierung

- separaten versionierten Repair-System-Prompt und striktes Patch-Schema implementieren;
- alle reparierbaren Findings in genau einem Repair-Provider-Aufruf verarbeiten;
- mehrere explizit freigegebene `(Option, Feld)`-Targets in einem atomaren Patch zulassen;
- keine freie Neugenerierung und keine unfreigegebenen Ziele zulassen;
- Patch nur auf Kopie anwenden und gesamten resultierenden Payload mit dem bestehenden Block-7-Validator erneut prüfen;
- bei jeder Teilverletzung vollständigen Repair verwerfen;
- erfolgreichen Repair separat vom Original und von Human Edits nachvollziehbar speichern.

### AP8 – Final Critic, Workflow-Ende und Call-Cap

- nach erfolgreichem validem Repair genau einen Final Critic automatisch ausführen;
- denselben Critic-Contract mit eigener Run-Provenance verwenden;
- verbleibende Findings oder Final-Critic-Ausfall ausschließlich zu Human Review führen lassen;
- jeden weiteren Repair serverseitig verhindern;
- maximale Modellaufrufzahl von vier inklusive Generate regressionsfest nachweisen;
- keine Retry-Schleifen zulassen.

### AP9 – Preview-UI, Findings, Repair-Aktion und Human Review

- vor UI-Änderungen `DESIGN.md` vollständig gegen den aktuellen `main` lesen;
- Quality-Control-Bereich in die bestehende Block-7-Preview integrieren;
- Findings, Kriterien, Option/Feld, Sources und Reparierbarkeit verständlich anzeigen;
- keine Bewertung oder Lösungsempfehlung suggerieren;
- einmalige Repair-Aktion ausschließlich bei aktuellem reparierbarem Finding anbieten;
- bei CAS-Stale expliziten Hinweis „Vorschau wurde seit der Prüfung bearbeitet, Reparatur nicht mehr möglich.“ anzeigen;
- bei leerem Findings-Array oder nur nicht reparierbaren Findings keinen Repair-Button anzeigen;
- bestehende Human-Edit-/Adoption-Pfade weiterhin nutzbar lassen;
- zweiten Zwischenstatus liefern und UI-Playbook um den vollständigen Critic-/Repair-/Human-Review-Klickpfad ergänzen.

### AP10 – Security-/Failure-/Gate-Regression und Abschluss

- vollständige #212-Regression konsolidieren;
- nachweisen: deterministische Validierung vor Critic, fünf feste Kriterien, strukturierte Findings, keine Scores/Rangfolge/Governance-Writes;
- Initial-Critic-Ausfall, Quota-Ausfall, Repair-Ausfall, stale CAS, Human-Edit-Konflikt und ungültigen Repair als verlustfreie Negativfälle testen;
- exakt einen Repair, atomaren Cross-Option-Patch, vollständige Revalidierung, genau einen Final Critic und zwingendes Ende nachweisen;
- maximale vier Modellaufrufe nachweisen;
- bestehende Block-7-Gates, Adoption und Domain-Felder als unverändert regressionsfest prüfen;
- bekannte Grenzen dokumentieren;
- vollständige Repository-CI grün nachweisen;
- #212-Checkliste vollständig abhaken und Issue schließen.

Die umfassende Real-DEMO-/adversariale End-to-End-Abnahme zusammen mit #211 bleibt #213 vorbehalten.

## Arbeitsweise

- Jedes AP wird einzeln und sequenziell umgesetzt.
- Jedes AP erhält einen eigenen Entwicklungs-Commit und einen eigenen Pull Request; kein Sammel-PR am Ende.
- Das nächste AP beginnt erst nach Merge des vorherigen APs und vollständig abgeschlossener Repository-CI.
- Die AP-Titel in #212 müssen exakt den Überschriften dieses Dokuments entsprechen.
- Ein AP wird in #212 erst nach erfolgreichem Merge und vollständig grüner CI abgehakt.
- #210 wird nicht verändert.

### Verbindliche CI-Regel

Bei fehlgeschlagenem CI-Lauf nicht sofort einen Fix pushen. Immer zuerst den kompletten Lauf abwarten, alle Fehler aus allen Jobs sammeln, keine Vermutungen anstellen sondern nur die Log-Hinweise nutzen, dann alle Fehler in einem Commit beheben und erst danach einen neuen Lauf starten. Ausnahme nur, wenn ein Fehler alle Folge-Jobs blockiert und deren Fehler verdeckt.

Diese Regel gilt für den eigenen Entwicklungs-/Commit-/PR-Workflow aller APs und gehört nicht in das UI-Playbook.

## Zwischenstatus und UI-Playbook

Es gibt zwei geplante Zwischenstatus:

1. nach AP5: erster vollständiger erweiterter Pfad ohne Repair; das Playbook prüft die bereits bestehende Generierungs-/Preview-Oberfläche und insbesondere, dass Critic-/Quota-/Provider-Ausfall eine valide Preview nicht zerstört. Finding-Darstellung ist zu diesem Zeitpunkt noch nicht UI-integriert und wird ausdrücklich als nicht klickbar markiert;
2. nach AP9: vollständiger Critic-/Repair-/Human-Review-Pfad in der bestehenden Preview klickbar.

Das UI-Playbook enthält ausschließlich manuelle Klick- und Prüfschritte, keine CI-Anweisungen.

## Bewusste V1-Entscheidungen

- Initial Critic läuft automatisch nach erfolgreicher Generierung und deterministischer Validierung; keine zusätzliche Critic-Aktion.
- Bestehende Quoten werden nicht erhöht. Quota-Ausfall des Critic ist verlustfrei.
- Genau ein Repair-Call verarbeitet alle aktuellen reparierbaren Findings atomar; keine Einzelfinding-Auswahl.
- Ein Repair darf mehrere explizit freigegebene Option-/Feld-Targets ändern, wenn Cross-Option-Findings dies erfordern.
- Whole-Preview-CAS statt Feld-Merge.
- Prompt-/Schema-/Quality-Contract-Versionen sind Teil der Staleness-Prüfung; Modellname ist Audit-Provenance, nicht CAS-Semantik.
- Quality-Step-Reservierung wird vor Provider-Aufruf persistiert; keine DB-Transaktion über Netzwerkaufrufe.
- Fehlgeschlagene Quality Steps werden nicht automatisch oder manuell innerhalb derselben Generation erneut gestartet.
- Leeres Findings-Array oder keine reparierbaren Findings führt ohne Repair-Button direkt zu Human Review.
- Findings blockieren die reguläre Adoption nicht.

## Nicht-Ziele von #212

- Änderung von #210;
- zweiter Lösungsvergleich;
- Agent oder Multi-Agent-System;
- autonome Recherche oder Websuche;
- zweiter Provider als Pflicht;
- Quality Score, Severity-Scoring oder gewichtetes Gesamturteil;
- automatische Rangfolge, Präferenz oder Lösungsauswahl;
- Governance-, Delivery- oder Lifecycle-Wirkung;
- generische Workflow-, Critic-, Rules- oder Policy-Engine;
- selbstoptimierende oder wiederholte Critic-/Repair-Loops;
- semantisches Merge konkurrierender Human-/Machine-Edits;
- Vorwegnahme der breiten Real-DEMO-/Regression-Abnahme aus #213.
