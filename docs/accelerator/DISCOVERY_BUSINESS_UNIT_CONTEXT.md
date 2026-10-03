# Organisationseinheit der Business Discovery

## Entscheidung

Auf Nutzerauftrag wird der bisherige Organisationsvertrag aus #124 bewusst ersetzt:
Eine abweichende oder fehlende persoenliche Organisationseinheit blockiert die
Discovery nicht mehr. Die bestehenden rollen- und eigentuemerbasierten
Berechtigungen bleiben unveraendert. Eine zusaetzliche Abweichungsbestaetigung
wird nicht eingefuehrt.

| Zuordnung | Bedeutung |
| --- | --- |
| `User.business_unit` | Persoenlicher Kontext, nur Vorbelegung |
| `IdeaCandidate.business_unit` | Ursprungsidee, bevorzugte Vorbelegung |
| `CaptureSession.answers.business_unit` | Eingefrorener Untersuchungskontext (`id`, `name`) |
| `ValueStream.business_unit` | Dauerhafte Ergebniszuordnung nach Human Review |

Keine neue Modellrelation oder Datenbankmigration. Eine Untersuchung aendert weder
die Organisationseinheit noch den State der Idee. `promoted` bedeutet weiterhin
ausschliesslich tatsaechliche Use-Case-Uebernahme.

## Einstieg und Review

Das Startformular zeigt die Ideen-Zuordnung und die persoenliche Zuordnung,
einschliesslich fehlender oder inaktiver Zustaende. Die sichtbare Auswahl
**Organisationseinheit der Untersuchung** enthaelt nur aktive Einheiten.

- Aktive Ideen-Einheit: bevorzugte Vorbelegung.
- Idee ohne Einheit / generischer Einstieg: aktive persoenliche Einheit als Default.
- Inaktive Ideen-Einheit: keine stille Ersetzung durch das Profil, Auswahl bleibt leer.
- Kein aktiver Default: Auswahl direkt im Formular, kein Account-Blocker.
- Keine aktive Einheit im System: sichtbarer Hinweis; fuer Staff direkter Zugang
  zur bestehenden Administration, sonst Hinweis auf die Administration.

Beim Start wird die Auswahl in der Capture-Session eingefroren. LLM-Input,
Review-Anzeige und Materialisierung verwenden denselben Kontext. Profil- und
Ideen-Aenderungen beeinflussen diesen Lauf nicht. Auch der bei Start festgehaltene
Name bleibt im Analysekontext erhalten; die dauerhafte Relation verwendet die ID.

Direkt vor **Scope & Fokus uebernehmen** erscheint **Wird angelegt in: ...**.
Ein Organisationswechsel nach Analysebeginn erfordert Verwerfen und Neustart.
Auch generische Discoveries besitzen den bestehenden Verwerfen-Pfad und danach
einen direkten Neustart-Link. Der verworfene Lauf wird nicht geloescht.

Die ausgewaehlte Einheit wird serverseitig beim Start, beim erneuten Analysieren
und bei der Materialisierung auf Existenz und Aktivitaet geprueft. Eine inzwischen
deaktivierte oder geloeschte Einheit wird nicht still durch die Profil-Einheit
ersetzt. Im Review bleiben Entwurf, Verwerfen und Navigation zugaenglich;
eine unzulaessige Ergebnisuebernahme wird verhindert.

## Bestehende Laeufe

Sessions ohne eingefrorenen Organisationskontext behalten ihren bisherigen Default:
die persoenliche Zuordnung des Session-Owners. Der Review zeigt diese Legacy-Regel
ausdruecklich an. Beim naechsten Analysestart oder bei der Uebernahme wird sie unter
Session-Lock eingefroren. Ein Review-GET schreibt keine Daten. Ein fehlender oder
inaktiver Legacy-Kontext wird nicht automatisch ersetzt; Verwerfen und neuer Start
mit expliziter Auswahl bleiben verfuegbar. Fruehere Profilzuordnungen lassen sich
aus diesen Alt-Sessions nicht rekonstruieren; kein rueckwirkender Kontext-Freeze.

## Verifikation

- Gezielte Regression: 90 Tests bestanden mit SQLite.
- Ruff, Django-Systemcheck und Migrationsdrift-Pruefung bestanden; keine neue Migration.
- Desktop-Browsertest mit echter Chromium-Oberflaeche bestanden: Owner ohne
  persoenliche Einheit, abweichende Zielauswahl, Start ohne Zusatzdatei, Human
  Review und Uebernahme, inaktive Ideen-Einheit, Verwerfen und Neustart sowie
  generische Discovery ohne persoenliche Einheit.
- Bestehende Ideen-, Korrektur-, Investigation-, Prozess- und Direct-Intake-Flows
  inklusive Vorwaerts-/Rueckwaertsnavigation erneut durchlaufen.
- Kein horizontaler Seitenueberlauf und keine Browserfehler. Sidebar-Position sichtbar.
  Desktop 1440x1000, Review zusaetzlich 1280x900 und 1920x1080;
  Mobile/Tablet auf Nutzerwunsch nicht getestet.
- Deterministische Provider-Fixtures, isolierte temporaere Datenbank und Quellen;
  keine produktiven Daten und keine Live-Providerkosten im Browsertest.

Reproduktion:

```powershell
$env:IDEA_UI_OUTPUT='artifacts/discovery-business-unit-ui-verification'
uv run --with playwright python scripts/idea_discovery_ui_verification.py
```

Screenshots und Bericht: `artifacts/discovery-business-unit-ui-verification/`.
Die neuen Start- und Review-Screenshots wurden auch visuell geprueft.

Tests pruefen unveraenderte Rollen-/Owner-Grenzen, Ablehnung manipulierter oder
inaktiver Ziele, erhaltene Formulareingaben, Profil- und Namensaenderungen zwischen
Start und Human Review, unveraenderte Ideenherkunft, Legacy-Kompatibilitaet und
fehlenden stillen Fallback. Vollstaendige PostgreSQL-Regression und CI werden im PR
nachgewiesen.
