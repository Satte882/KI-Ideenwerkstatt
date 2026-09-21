# UI Control Room – Migrationsvertrag

Status: AP 8 / Hardening abgeschlossen, Final Gate ausstehend
Parent: #279
Arbeitsauftrag: #280

## Zweck

Die bestehende UI-vNext-Schicht wird schrittweise zu einer auf Business Architecture, Decision Governance und nächste Entscheidungen ausgerichteten Control-Room-Oberfläche weiterentwickelt. `DESIGN.md` bleibt die autoritative Gestaltungsleitlinie.

Die Migration ist rein präsentationsseitig. Bestehende URLs, Views, Querysets, Formulare, POST-Aktionen, Rollen, Berechtigungen, Datenmodelle und serverseitige Gates bleiben unverändert.

## Referenz-Audit

### Globale Shell (Ausgangslage)

- `templates/base.html` lädt Bootstrap sowie die bestehenden `ui-vnext-*`-Styles global und stellt mit `{% block body_class %}` bereits einen seitenweisen CSS-Opt-in bereit.
- `templates/includes/context_topbar.html` kombiniert derzeit Kontext, permanenten End-to-End-Fortschritt und teilweise die nächste Aktion. Auf Querschnittsseiten entsteht dadurch fachliche Redundanz.
- `templates/includes/next_action.html` erzeugt auf dem Use-Case-Detail zusätzlich eine dominante Next-Action-Fläche.
- `templates/includes/journey_stepper.html` bildete einen weiteren Journey-Kontext ab und wurde nach vollständiger Ablösung entfernt.
- `static/css/ui-vnext-tokens.css`, `ui-vnext-shell.css`, `ui-vnext-components.css` und `ui-vnext-pages.css` bilden bereits eine vNext-Styling-Schicht; die Template-Komponentisierung ist dagegen bewusst dünn.

### Referenzseite 1 – Portfolio

`templates/reporting/portfolio.html` ist der erste Vertical Slice. Die Seite enthält aktuell Header, Filter-Card, vier Metric-Cards, Fachdomänen-Card, Entscheidungs-Matrix, Tabellenalternative, Portfolio-Landkarte und Nicht-einordenbar-Liste. Sie eignet sich deshalb als Referenz für Querschnitts-, Filter-, Statistik- und Datenvergleichsmuster.

Der Portfolio-Umbau erfolgt in #281 direkt und pragmatisch. Wiederverwendbare Querschnitts-Primitives werden erst nach bestandenem Screenshot-Gate A in #282 extrahiert.

### Referenzseite 2 – Use-Case-Detail

`templates/use_cases/detail.html` ist der zweite Vertical Slice. Aktuell konkurrieren Header-Badges, globale Topbar, `next_action.html`, Journey-Stepper, Decision-Panel und Blocker-Flächen um Priorität. Die Referenzseite wird deshalb in #283 als Decision Workspace neu hierarchisiert.

Der erste AP7-Work-Object-Rollout überträgt diese Hierarchie auf Prozessanalyse, Delivery Package, Governance-Screening und -Fachprüfung sowie Bewertung und Freigabeentscheidung. Diese Seiten besitzen jeweils genau eine lokale Lifecycle-Leiste; Prozessanalyse und Delivery zeigen zusätzlich genau eine kanonische Next Action. Echte, untergeordnete Teilworkflows wie die Delivery-Sektionsprüfung bleiben erhalten.

Der zweite AP7-Rollout schließt die übrigen Detail-, Prüf- und Formularseiten an dieselben scoped Primitives an. Lösungsvergleich, Accelerator-Prüfräume, Zweitprüfung, Architektur- und Delivery-Formulare, Review- und Nachweisformulare sowie die methodische Referenz teilen damit Header-, Dichte-, Fokus- und Responsive-Regeln. Intake- und Capture-Wizard behalten ihren eigenen Schrittfortschritt als echten, untergeordneten Mikro-Workflow; sie erzeugen keine zweite End-to-End-Lifecycle-Darstellung.

Decision-State- und Lifecycle-Primitives werden erst nach bestandenem Screenshot-Gate B in #284 abstrahiert.

## Abgeschlossene Normalisierung

Die temporäre Koexistenz ist beendet. Control Room ist der Normalzustand der Anwendung und wird in `base.html` zentral gesetzt:

```django
<body class="ui-vnext ui-control-room {% block body_class %}{% endblock %}">
```

`ui-vnext` bleibt das gemeinsame Grundsystem für Tokens, Shell, Fokus und reduzierte Bewegung. `ui-control-room` bezeichnet die verbindliche Informationshierarchie und die gemeinsamen Arbeitsflächen. Der `body_class`-Block enthält nur noch seiten- beziehungsweise archetypspezifische Klassen; die frühere redundante Migrationsklasse ist aus allen Seitentemplates entfernt.

Verbindliche Regeln:

1. Neue Control-Room-Regeln bleiben unter `.ui-control-room` gescoped.
2. Alle produktiven Seiten verwenden die gemeinsame Shell; es gibt keinen seitenweisen Opt-in mehr.
3. Neue Seiten erhalten nur ihren Archetyp beziehungsweise ihre Seitenklasse.
4. Es gibt keine Runtime-Feature-Flags, keine zweite View, keine duplizierten Querysets und keine doppelte Backend-Logik.
5. Bestehende echte Links, Formulare, Berechtigungen, POST-Aktionen und serverseitige Gates bleiben erhalten.
6. Der ungenutzte Legacy-Stepper und seine ausschließlich dafür vorhandenen Use-Case-Regeln sind entfernt.
7. Die Template-Tag-Bibliothek `workflow_tags` existiert nur einmal zentral in `ki_radar.core`; die frühere doppelte Registrierung und Django-Warnung sind entfernt.

## UI-Archetypen und Rollout

`Q` = Querschnitt, `L` = Liste, `O` = Arbeitsobjekt/Detail, `F` = Formular/Wizard, `S` = Sonder-/Referenzseite.

Includes und Partials sind keine eigenständigen Migrationsseiten; sie werden mit ihrem jeweiligen Verbraucher migriert.

| Template | Archetyp | Geplante Migration |
| --- | --- | --- |
| `templates/reporting/portfolio.html` | Q | Referenz 1 / #281 |
| `templates/use_cases/detail.html` | O | Referenz 2 / #283 |
| `templates/reporting/dashboard.html` | Q/L | #285 |
| `templates/use_cases/list.html` | L | #285 |
| `templates/architecture/value_stream_list.html` | L | #285 |
| `templates/delivery/package_list.html` | L | #285 |
| `templates/accelerator/capture_list.html` | L | #285 |
| `templates/reporting/outcome_workspace.html` | O | #286 |
| `templates/architecture/value_stream_detail.html` | O | #286 |
| `templates/architecture/process_analysis_detail.html` | O | #286 |
| `templates/architecture/solution_option_compare.html` | O | #286 |
| `templates/delivery/package_detail.html` | O | #286 |
| `templates/accelerator/analysis_detail.html` | O | #286 |
| `templates/accelerator/capture_review.html` | O | #286 |
| `templates/accelerator/solution_generation_preview.html` | O | #286 |
| `templates/accelerator/structured_review.html` | O | #286 |
| `templates/use_cases/second_approval_review.html` | O | #286 |
| `templates/reviews/monthly.html` | Q/L | #285 |
| `templates/use_cases/assessment_form.html` | F | #286 |
| `templates/use_cases/decision_form.html` | F | #286 |
| `templates/use_cases/form.html` | F | #286 |
| `templates/use_cases/intake_wizard.html` | F | #286 |
| `templates/architecture/process_analysis_form.html` | F | #286 |
| `templates/architecture/process_validation_form.html` | F | #286 |
| `templates/architecture/solution_option_form.html` | F | #286 |
| `templates/architecture/stage_focus_form.html` | F | #286 |
| `templates/architecture/stage_form.html` | F | #286 |
| `templates/architecture/value_stream_form.html` | F | #286 |
| `templates/delivery/package_form.html` | F | #286 |
| `templates/governance/form.html` | F | #286 |
| `templates/governance/review_form.html` | F | #286 |
| `templates/reviews/form.html` | F | #286 |
| `templates/notifications/evidence_form.html` | F | #286 |
| `templates/accelerator/capture_start.html` | F | #286 |
| `templates/accelerator/capture_wizard.html` | F | #286 |
| `templates/accounts/login.html` | S | #287 / Hardening |
| `templates/delivery/methodology_reference.html` | S | #286 |
| `templates/reviews/section.html` | O/S | #286 |

## Abnahme-Gates

- **Gate A nach #281:** Portfolio-Screenshot-Review auf Desktop breit/normal, Tablet und Mobile sowie mit relevanten Datenzuständen. Kein #282 vor Freigabe.
- **Gate B nach #283:** Use-Case-Screenshot-Review auf Desktop/Tablet/Mobile sowie Normal-, Blocker-, Zweitprüfungs-, Freigabe- und Read-only-Zustand. Kein #284 vor Freigabe.
- **Final Gate nach #287:** vollständige fachliche, visuelle, responsive und Accessibility-Abnahme des Integrationsbranches. Kein Merge auf `main` vor expliziter Freigabe.

## AP6 – migrierte Querschnitts- und Listenseiten

Nach der Dashboard-Referenz verwenden die verbleibenden produktiven Listen aus
#285 dieselbe Control-Room-Hierarchie:

- Use-Case-Liste mit gemeinsamem Header, Filterdeck, Datentabelle und Empty State,
- Value-Stream-Liste als scanbares Link-Grid ohne pseudo-linearen Lifecycle,
- Delivery-Liste und persönliche Erfassungen mit gemeinsamer Tabellenstruktur,
- Monatsreview als priorisierte Arbeitsliste ohne Card-Wall.

Die Migration ändert keine Query-Parameter, Links, Form-Aktionen, Rollen oder
serverseitigen Gates. Datentabellen dürfen innerhalb ihres eigenen Containers
horizontal scrollen; die Seite selbst bleibt auf Desktop und Mobile überlauffrei.

## CI-Regel

Bei einem fehlgeschlagenen CI-Lauf wird der komplette Lauf abgewartet. Danach werden alle fehlgeschlagenen Jobs und deren Logs vollständig geprüft und ausschließlich auf Basis der vorliegenden Log-Hinweise gesammelt. Alle identifizierten Fehler werden in einem Sammel-Fix-Commit behoben; erst danach wird ein neuer Lauf ausgelöst.

Ein vorgezogener Fix ist nur zulässig, wenn ein Fehler nachweislich Folge-Jobs blockiert und deren mögliche Fehler verdeckt.

## Exit-Kriterium

Die Migration ist erst abgeschlossen, wenn alle produktiven Seiten migriert, die temporäre Koexistenz beendet, ungenutzte Legacy-Regeln entfernt, die vollständige CI grün und das Final Gate bestanden ist.
