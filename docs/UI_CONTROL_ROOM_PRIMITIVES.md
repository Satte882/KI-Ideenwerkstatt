# UI Control-Room Primitives

Status: AP3 nach bestandenem Gate A aus #281.

## Extraktionsregel

Nur Muster, die im Portfolio visuell abgenommen wurden und für die im bestehenden Produkt bereits ein zweiter realistischer Verbraucher vorhanden ist, werden extrahiert. Die Extraktion bleibt reine Präsentationslogik: keine View-Logik, keine fachlichen Entscheidungen und keine Template-Parameter-API.

## Validierte Querschnittsmuster

| Primitive | Gate-A-Referenz | Zweiter realistischer Verbraucher | Grenze |
| --- | --- | --- | --- |
| `cr-page-header` | Portfolio-Kopf | `templates/reporting/dashboard.html` und `templates/reporting/outcome_workspace.html` besitzen dieselbe Titel-/Kontext-/Aktionshierarchie | keine Breadcrumb-/Journey-Logik |
| `cr-section` / `cr-section-heading` | Portfolio-Abschnitte | Arbeitsvorrat und Outcome Workspace strukturieren ebenfalls Überschrift, Kontext und Inhalt | keine fachliche Abschnittssemantik |
| `cr-stat-strip` / `cr-stat` | Portfolio-Statusleiste | Arbeitsvorrat und Outcome Workspace zeigen kompakte Mengen-/Statusgruppen | nur Darstellung, keine Berechnung |
| `cr-filter-*` | Portfolio-Filter | `templates/use_cases/list.html` hat fünf Filterfelder plus explizite Aktion und Reset | keine Query-/Filterlogik |
| `cr-inline-note` / `cr-empty-state` | ausgeblendete/nicht vorhandene Portfolio-Daten | Arbeitsvorrat, Use-Case-Liste und Outcome Workspace haben Warning-/Empty-Situationen | Status muss bereits serverseitig feststehen |

Die zweiten Verbraucher werden in AP3 bewusst **nicht** optisch migriert. Sie belegen die reale Wiederverwendbarkeit; ihre Adoption erfolgt in den dafür vorgesehenen späteren Arbeitspaketen.

## Technischer Vertrag

- CSS ist vollständig unter `.ui-control-room` gescoped.
- Farben, Flächen, Linien, Radien und Schatten verwenden die semantischen UI-vNext-Tokens.
- Portfolio lädt zuerst `ui-control-room-primitives.css` und danach seine seitenbezogenen Regeln.
- Portfolio-spezifische Matrix-, Domänen-, Landscape- und Tabellenlogik bleibt im Portfolio-Stylesheet.
- Es gibt keine neuen Template-Partials und damit keine Parameter-API oder fachliche Logik in Includes.
- Die bei Gate A validierten Layoutwerte wurden bei der Extraktion unverändert übernommen.

## Bewusst nicht extrahiert

`LifecycleRail` und `DecisionState` werden vor der Validierung an einem konkreten Use-Case-Arbeitsobjekt nicht generalisiert. Das ist Gegenstand des nächsten Referenz-Slices, nicht von AP3.
