# KI-Ideenwerkstatt Design System

Dieses Dokument ist die verbindliche UI-Zwangsjacke für neue oder geänderte Oberflächen.
Es beschreibt Produktqualität, nicht eine austauschbare Landingpage-Ästhetik.

## Zielbild

- Ruhige, hochwertige B2B-Arbeitsoberfläche mit klarer Informationshierarchie.
- Neutraler Graphit-/Schwarzraum mit kühlem Eisblau und Silber als Akzent.
- Sichtbare räumliche Tiefe und Atmosphäre, ohne Effekthascherei.
- Daten bleiben schneller erfassbar als die visuelle Inszenierung.
- Dunkel ist der einzige aktive Modus; Tokens müssen einen späteren Hellmodus erlauben.

## Gestaltungsprinzipien

1. Erst Aufgabe und Informationshierarchie, dann Oberfläche.
2. Flächen durch Abstand, Linien und Tonwert trennen; nicht alles in Karten setzen.
3. Primäraktionen deutlich, Nebenaktionen ruhig und reversibel gestalten.
4. Status immer zusätzlich durch Text vermitteln, nie ausschließlich durch Farbe.
5. Dichte an Scan-Aufgabe und Datenmenge ausrichten, nicht an Showcase-Screenshots.

## Tokens

- Farben ausschließlich über semantische CSS Custom Properties definieren.
- Keine beliebigen Hex-, RGB- oder OKLCH-Werte direkt in Komponenten ergänzen.
- Surface-Stufen: `surface-0` Hintergrund, `surface-1` Shell, `surface-2` Kontrolle,
  `surface-3` aktiver oder angehobener Zustand.
- Linien: `line-soft`, `line`, `line-strong`.
- Text: `ink`, `muted`; Akzente: `ice`, `ice-strong`, `silver`.
- Semantik: `success`, `warning`, `danger`.
- Radien: klein 7 px, mittel 11 px, groß 16 px.
- Schatten: Stufe 1 Kante, Stufe 2 Bedienfläche, Stufe 3 Hauptoberfläche.

## Typografie

- Bestehenden System-Font-Stack beibehalten.
- Überschriften mit enger Laufweite und klarer Gewichtung, nicht ultrafett.
- Fließtext kompakt und gut lesbar; keine dekorativen Versalien.
- Versalien nur für kurze Kicker, Labels und Tabellenköpfe einsetzen.
- Zahlen und Termine tabellarisch setzen, wenn sie untereinander verglichen werden.
- Inter, Poppins oder eine neue Webfont nicht ohne eigene Designentscheidung einführen.

## Layout

- Der Seitenrahmen trägt die Atmosphäre; Inhalte benötigen nicht jeweils eine Karte.
- Seitentitel, Zweck und Aktionen bilden eine klare Kopfzone.
- Filter bleiben sichtbar und stehen direkt vor der Ergebnisliste.
- Desktop nutzt Breite für eine Filterzeile; Tablet darf kontrolliert umbrechen.
- Mobile stapelt Bedienelemente und erlaubt horizontales Scrollen großer Datentabellen.
- Inhaltsbreite und Abstände müssen auch bei 5 und bei 60 Zeilen funktionieren.

### Arbeits- und Formularflächen

- Scan-/Listenseiten bleiben möglichst flach. Tabellen, Kennzahlen und Register werden primär über Abstand, Linien und Tonwert gegliedert.
- Arbeits- und Formularseiten dürfen zusammengehörige Eingaben, Entscheidungen oder Bewertungsblöcke als gemeinsame funktionale Surface gruppieren.
- Eine solche Surface ist keine dekorative Karte: Sie muss eine fachliche Einheit sichtbar machen, z. B. Eingabeblock, Gate, Entscheidung oder Bewertungsdimension.
- Funktionale Arbeitsflächen verwenden bevorzugt `surface-1` oder `surface-2`, `line` bzw. `line-strong` und höchstens `shadow-1`.
- Eingabefelder müssen sich im Ruhezustand klar von ihrer umgebenden Arbeitsfläche unterscheiden. Der Defaultzustand darf nicht erst durch Hover oder Fokus erkennbar werden.
- Verschachtelte Kartenhierarchien bleiben verboten. Innerhalb einer Arbeitsfläche werden Untergruppen nur dann erneut eingefasst, wenn die Gruppierung eine eigene fachliche Bedeutung besitzt.

## Lifecycle und Prozesskontext

- Eine Journey/Datenquelle darf pro Arbeitsobjekt nur eine primäre Lifecycle-Darstellung besitzen. Ein echter Subworkflow ist nur zulässig, wenn er semantisch eine andere Granularität besitzt, ausdrücklich bezeichnet und visuell untergeordnet ist.
- Migrierte Arbeitsobjekte besitzen ihren Lifecycle lokal im fachlichen Workspace; ein globaler Kontextbereich darf dieselbe Journey dort nicht erneut rendern.
- Der primäre Lifecycle steht in der oberen Orientierungshierarchie des Workspaces vor Seitentitel, Next Action und Arbeitsinhalt. Er darf nicht als nachgelagerter Inhaltsblock zwischen Arbeitskarten erscheinen.
- `Wirkung & Betrieb` ist ein eigener Arbeitsraum. Seine Stufen `Übergabe → Pilot → Wirkung → Ergebnisentscheidung → Betrieb → Abschluss` werden lokal als ausdrücklich untergeordneter Ablauf dargestellt und nicht zusätzlich in der globalen Sidebar wiederholt.
- Querschnitts- und Listenseiten erhalten keinen pseudo-linearen Lifecycle.
- Die kanonische Next Action erscheint pro Arbeitsobjekt genau einmal dominant. Weitere Aktionen dürfen nur als fachlich eigenständige Sekundäraktionen erscheinen.
- In einem lokalen Arbeitsobjekt ist ein Lifecycle-Schritt nur dann ein echter Link, wenn ein konkretes Objekt oder eine konkrete ausführbare Aktion existiert. Zukünftige, optionale oder lediglich global auflösbare Schritte bleiben Statusanzeigen; globale Listen-Fallbacks gehören nicht in den lokalen Lifecycle.
- Eine ausdrücklich als Teilprozess ausgewiesene Ansichtsfolge innerhalb desselben Arbeitsraums darf ihre lokalen Stufen als View-Wechsel verlinken. Aktueller Schritt bzw. aktuelle Ansicht werden mit `aria-current` gekennzeichnet und besitzen sichtbaren Tastaturfokus.
- Eine untergeordnete Analyseschritt-Navigation besitzt auf Desktop genau einen persistenten Owner. Eine zusätzliche Vor-/Zurück-Leiste ist dort auszublenden und bleibt nur erhalten, wenn die persistente Navigation auf kleinen Viewports entfällt.
- Desktop-Lifecycle darf bei normalen Viewports keine horizontale Scrollfläche erzeugen. Tablet und Mobile verwenden eine kompakte, umbrechende Darstellung.
- Phasen-, Reife- und Blockerzustände verwenden ausschließlich die bestehenden semantischen Tokens und Statusfarben.

## Progressive Disclosure

- Der verbindliche Progressive-Disclosure-Primitive ist natives `<details>` mit einem direkten `<summary>`. Für normales Ein-/Ausblenden wird kein JavaScript-, Bootstrap-Collapse- oder eigenes ARIA-State-System ergänzt.
- Disclosure ist nur für sekundäre oder ergänzende Information zulässig, die ohne Verlust der aktuellen Arbeitsfähigkeit zunächst verborgen sein darf.
- Aktuelle Entscheidung, Blocker, kanonische Next Action, Hard-Gate-Begründung, Fehler sowie unmittelbar erforderliche Eingaben oder Aktionen dürfen nicht hinter Disclosure verschwinden.
- Tabs sind ausschließlich für echte gleichrangige Ansichten bzw. Peer-Sichten vorgesehen; sie sind kein generischer Ersatz für `<details>/<summary>`.
- Der `<summary>`-Text benennt konkret, welche Information geöffnet wird. Zusätzliche Links, Buttons oder andere interaktive Controls gehören nicht in `<summary>`, sondern in den aufgeklappten Inhalt.
- Kontextklassen wie `.architecture-disclosure`, `.artifact-disclosure`, `.source-disclosure` oder `.portfolio-secondary-view` dürfen Darstellung und Dichte variieren, bleiben aber visuelle Varianten desselben nativen Primitives und führen keine eigene Interaktionslogik ein.
- Der gemeinsame Interaktionssockel liegt in `ui-vnext`: mindestens `--touch-target-min` als Klick-/Touch-Höhe, sichtbarer `:focus-visible`-Zustand und umbrechende Summary-Texte ohne unnötigen horizontalen Scroll.
- Der Offen-/Geschlossen-Zustand muss semantisch bzw. zusätzlich zur Farbe erkennbar bleiben. Native Marker dürfen genutzt werden; ein visueller Variantenmarker darf sie ersetzen, wenn beide Zustände eindeutig unterscheidbar bleiben.
- Disclosure entfernt auf Tablet oder Mobile keine Information. Inhalte bleiben vollständig erreichbar; echte Links bleiben echte Links und funktionieren unabhängig vom Toggle ohne skriptbasierte Navigation.
- Für den Primitive ist keine Animation erforderlich. Ergänzt eine visuelle Variante Bewegung, gilt zwingend die globale `prefers-reduced-motion`-Regel.
- #363, #364, #365 und zukünftige UI-Arbeiten verwenden diesen Primitive statt eines weiteren konkurrierenden Collapse-/Accordion-Systems.

## Datenlisten

- Tabellen bleiben Tabellen, wenn zeilenweises Überfliegen die Hauptaufgabe ist.
- Tabellenkopf bleibt beim vertikalen Scrollen sichtbar.
- Zeilen sind mittel-kompakt; Hover darf keine Lageverschiebung verursachen.
- Ist eine Zeile anklickbar, bleibt ein echter Link als Fallback vorhanden.
- Anklickbare Zeilen müssen Fokus, Enter und Leertaste unterstützen.
- Primärinformation beginnt jede Zeile; Metadaten sind sichtbar zurückgenommen.
- Spalten ohne unmittelbaren Scan-Wert gehören nicht in die Übersicht.

## Filter

- Fachdomäne und Status sind primäre Filter und visuell leicht hervorgehoben.
- Suche, Review und Geschäftswert bleiben dauerhaft sichtbar.
- Filterung wird explizit ausgelöst; keine versteckten automatischen Server-Requests.
- Zurücksetzen ist eine ruhige Textaktion, keine konkurrierende Hauptschaltfläche.
- Labels bleiben sichtbar; Placeholder ersetzen keine Feldbezeichnung.

## Status und Badges

- Badge-Flächen sind kompakt, leicht eckig und semantisch getönt.
- Keine leuchtenden Pillen und keine frei erfundenen Statusfarben.
- Phase nutzt Eisblau, bereit nutzt Grün, Prüfung nutzt Amber, blockiert nutzt Rot.
- Domänen bleiben neutral, damit Status in der Zeile priorisiert bleibt.

## Effektbudget

- Maximal drei Elevation-Stufen pro Ansicht.
- Erlaubt: statisches atmosphärisches Licht, feine Kanten, innere Highlights,
  kurze Hover-, Fokus-, Auswahl- und Statusübergänge.
- Animationen bevorzugen `opacity` und `transform`; Layout darf nicht springen.
- Keine dauerlaufenden Animationen, Partikelfelder, Canvas- oder WebGL-Effekte.
- Kein Effekt darf Textkontrast, Scangeschwindigkeit oder Klickziel verschlechtern.
- `prefers-reduced-motion` ist verpflichtend.

## Harte Verbote

- Kein zentrierter Hero aus Überschrift, Unterzeile und CTA.
- Kein Raster aus drei identischen Feature-Karten.
- Kein lila-blauer Verlauf als Markenabkürzung für „KI“.
- Keine gläsernen Karten auf jeder Ebene.
- Keine willkürlichen Farben, Schatten, Radien oder Icon-Stile.
- Keine neuen Bedienelemente als Attrappe für spätere Features.
- Kein Austausch funktionaler Links durch rein skriptbasierte Navigation.

## Accessibility und Stabilität

- Sichtbarer Fokus für alle interaktiven Elemente.
- Semantische Überschriften, Labels, Tabellenköpfe und Zeitangaben verwenden.
- Kontrast mindestens WCAG AA für normalen Text.
- Touch-Ziele in mobilen Ansichten mindestens etwa 42 px hoch.
- Inhalte ohne JavaScript weiterhin über echte Links erreichbar halten.
- Bestehende URLs, Berechtigungen und Serverlogik bei rein visuellen Arbeiten bewahren.

## Abnahme

- Wirkt die Ansicht klar hochwertiger und weniger generisch?
- Findet man Fachdomäne, Status, Reife und nächste Entscheidung beim Überfliegen?
- Funktionieren Filter, Zeilenklick, Tastatur und echter Link?
- Bleiben Effekte stabil und verdecken keine Information?
- Ist der Seitenrahmen in sich konsistent?
- Funktioniert die Ansicht auf Desktop, Tablet und Mobile?
- Sind bestehende fachliche Funktionen vollständig erhalten?

## Arbeitsregel für UI-Änderungen

Für KI-Ideenwerkstatt gibt es keine branch-spezifische UI-Regel. Änderungen erfolgen
im aktuellen Arbeitskontext des Repositories. Das Design-System bleibt für produktive
Oberflächen verbindlich; eine bewusste Änderung dieser Regeln im Rahmen von GitHub
Issue #1 „10x: Autonomes Evidence-to-Decision-System“ muss explizit, nachvollziehbar
und konsistent erfolgen statt sie stillschweigend zu umgehen.

## Abgeschlossene UI-Migration

- `ui-vnext` bleibt das globale Grundsystem für Tokens, Shell, Fokus und reduzierte Bewegung.
- `ui-control-room` ist der Normalzustand der Anwendung und wird zentral am `body` gesetzt; Seitenklassen beschreiben nur noch den jeweiligen Archetyp.
- Es gibt keinen parallelen Legacy-Stepper mehr. `lifecycle_rail.html` ist die einzige lokale primäre Lifecycle-Darstellung; echte Wizard- und Sektionsabläufe bleiben ausdrücklich untergeordnet.
- Neue produktive Seiten müssen die gemeinsame Shell verwenden. Eine zweite CSS- oder Template-Welt benötigt eine ausdrückliche Designentscheidung.
