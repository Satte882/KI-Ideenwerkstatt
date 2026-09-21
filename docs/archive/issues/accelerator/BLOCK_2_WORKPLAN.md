# Block 2: Deterministisches Scenario-Blueprint – Arbeitsplan

**Issue:** #118  
**Abhängigkeit:** Block 1 / #117  
**Ausgangspunkt:** `main` auf `8f3863aab1e7c4516522c86d130c03bd9995e157`  
**Zielzustand:** Ein bekanntes `[Real-DEMO]`-Szenario kann LLM-frei, reproduzierbar und atomar als konsistenter Entwurfsgraph erzeugt werden.

## Verbindliche Umsetzungsregeln

- Dieser Workplan wird vor der technischen Umsetzung über einen eigenen Pull Request nach `main` übernommen.
- Danach wird im Issue #118 eine Checkliste mit exakt den unten stehenden AP-Titeln angelegt.
- Jedes Arbeitspaket wird auf einem eigenen Branch mit eigenem Commit und eigenem Pull Request umgesetzt und erst nach erfolgreicher Prüfung gemergt.
- Die Reihenfolge der Arbeitspakete ist verbindlich.
- Jeder Apply-Vorgang ist graphweit atomar: Bereits ein einzelnes `CONFLICT`-Objekt verhindert jede Teilanwendung.
- Version 1 unterstützt ausschließlich `CREATE`, `NO_CHANGE` und `CONFLICT`; es gibt kein automatisches Update, Merge oder Replace.
- Prüfsummen werden ausschließlich aus kanonisch serialisiertem JSON berechnet: UTF-8, sortierte Objektschlüssel, feste kompakte Separatoren, unveränderte Array-Reihenfolge und normalisierte Zahlenrepräsentation.
- Die Anwendung setzt vorhandene, gültige Referenzobjekte für Benutzer und Organisationseinheiten voraus. Diese werden nicht durch den Blueprint erzeugt. Für Demo-Umgebungen wird die notwendige Vorbedingung über den bestehenden Demo-Identitäts-/Seed-Pfad dokumentiert und getestet.
- Keine Fokusentscheidung, Prozessvalidierung, bevorzugte Lösungsoption, Governance-Entscheidung, Freigabe, Delivery-Bestätigung, Übergabe, Pilot- oder Go-live-Aktion darf automatisch gesetzt werden.
- Die erwartete Prüfsumme des Referenz-Blueprints darf nur in einem eigenen, nachvollziehbar begründeten Pull Request geändert werden, wenn die Blueprint-Version erhöht oder eine fachlich bestätigte Korrektur des Referenzszenarios dokumentiert wurde. Eine Änderung nur zur Anpassung an einen fehlgeschlagenen Test ist unzulässig.

## AP 1: Gap-Analyse und Referenzstand einschließlich Issue #106 verifizieren

- Bestehende Demo-Seeds, Management Commands, Forms, Domain Services, Signale, Audit- und Herkunftsmechanismen prüfen.
- Direkt gesetzte Status-, Review-, Fokus-, Entscheidungs-, Governance- und Delivery-Zustände inventarisieren.
- Den aktuellen `[Real-DEMO]`-Stand mit dem Korrekturauftrag und den Schutzmechanismen aus Issue #106 abgleichen.
- Bestehende stabile Schlüssel, Referenzobjekte und Wiederverwendungsgrenzen dokumentieren.
- Nicht belegte Annahmen, insbesondere zum vollständigen `[Real-DEMO]`-Graphen, ausdrücklich kennzeichnen.

**Ergebnis:** `docs/accelerator/BLOCK_2_GAP_ANALYSIS.md` mit Repo-Evidenz, minimalem Zuschnitt und Abnahmemapping.

## AP 2: Versionierten Blueprint-Vertrag und erlaubte Entwurfszustände festlegen

- Schlankes JSON-Format Version 1 für Value Stream, Phasen, Prozessanalyse, Lösungsoptionen, Use-Case-Stammdaten, Metrik, Rollenreferenzen und Herkunftsbeziehungen definieren.
- Positive Feldlisten, Pflichtfelder, Typen, Referenzen und erlaubte Enum-Werte festlegen.
- Rote Gate-, Entscheidungs- und Bestätigungsfelder technisch ausschließen.
- Voraussetzungen für vorbestehende Benutzer und Organisationseinheiten dokumentieren.
- Keine generische DSL oder Importplattform einführen.

**Ergebnis:** Formatdokumentation und maschinenlesbares, repo-spezifisches Schema.

## AP 3: Kanonische Serialisierung, Prüfsumme und Änderungsgovernance implementieren

- Kanonische JSON-Serialisierung mit sortierten Schlüsseln, festen Separatoren, stabiler Array-Reihenfolge und normalisierter Zahlenrepräsentation implementieren.
- SHA-256-Prüfsumme ausschließlich über diese kanonische Darstellung bilden.
- Rohformatierung, Einrückung und Schlüsselreihenfolge dürfen die Prüfsumme nicht verändern.
- Die Regel für zulässige Änderungen der erwarteten Referenz-Prüfsumme dokumentieren.

**Ergebnis:** Kleiner, isoliert testbarer Prüfsummenbaustein ohne neue externe Abhängigkeit.

## AP 4: Vollständige Vorabvalidierung und Referenzauflösung implementieren

- Schema-, Typ-, Pflichtfeld-, Enum- und interne Referenzvalidierung vor jeder Datenbankänderung durchführen.
- Benutzer über eindeutige Benutzernamen und Organisationseinheiten über eindeutig geprüfte Namen auflösen.
- Fehlende, mehrdeutige, inaktive, anonymisierte oder fachlich unzulässige Referenzen ablehnen.
- Bestehende Django-Forms beziehungsweise maßgebliche Domain Services als fachliche Validierungsgrenze wiederverwenden.
- Alle Fehler sammeln und verständlich strukturiert ausgeben, bevor eine Apply-Phase beginnt.

**Ergebnis:** Vollständig validierter, aufgelöster In-Memory-Entwurfsplan ohne Schreibzugriff.

## AP 5: Deterministischen Dry Run und graphweiten Diff implementieren

- Für jedes Objekt `CREATE`, `NO_CHANGE` oder `CONFLICT` bestimmen.
- Bei `CONFLICT` betroffene Felder mit aktuellem und erwartetem Wert ausweisen.
- Szenario, Schema-Version, kanonische Prüfsumme, Referenzauflösung und erwartete Objektanzahlen ausgeben.
- Explizit bestätigen, dass ein Dry Run keine Daten verändert.
- Klarstellen und technisch erzwingen, dass bereits ein einzelner Konflikt den gesamten späteren Apply verhindert.

**Ergebnis:** Verständlicher, stabil sortierter Erzeugungs- beziehungsweise Vorher-/Nachher-Diff.

## AP 6: Atomaren Apply-Service über bestehende fachliche Schreibpfade implementieren

- Vorbedingungen unmittelbar vor dem Schreiben erneut prüfen.
- Entwurfsobjekte innerhalb einer einzigen `transaction.atomic()`-Grenze erzeugen.
- Validierte Forms oder bestehende Domain Services verwenden; technische Schlüssel und Herkunft nur kontrolliert ergänzen.
- Reihenfolge der Objekterzeugung und Herkunftsverknüpfung deterministisch halten.
- Bei Validierungsfehler, Konflikt oder technischem Fehler vollständigen Rollback garantieren.
- Keine Teilanwendung und keine automatische Aktualisierung bestehender Szenarien zulassen.

**Ergebnis:** Reproduzierbare graphweite Erzeugung mit strikt definiertem Wiederholungsverhalten.

## AP 7: Herkunftsbeziehungen und technisches Ausführungsprotokoll ergänzen

- Vorhandene Herkunftsstrukturen für die fachliche Graphbeziehung wiederverwenden.
- Schema-Version, Szenarioschlüssel, Blueprint-Prüfsumme und lokale Blueprint-Schlüssel nachvollziehbar zuordnen.
- Vorhandenes technisches Job-Protokoll für Modus, Ergebnis, Dauer, Objektanzahlen und bereinigte Fehler nutzen.
- Keine vollständigen Blueprint-Inhalte oder unnötigen personenbezogenen Daten in Logs duplizieren.

**Ergebnis:** Nachvollziehbarer Audit-Trail ohne neues generisches Audit- oder Observability-System.

## AP 8: `[Real-DEMO]` als Referenz-Blueprint Version 1 bereitstellen

- Den fachlich belegten `[Real-DEMO]`-Entwurfsgraphen als versioniertes Repository-Artefakt abbilden.
- Den Korrekturstand aus Issue #106 ausdrücklich erhalten.
- Alle roten Zustände entfernen oder auf zulässige Entwurfsdefaults zurücksetzen.
- Voraussetzungen für Demo-Benutzer und Demo-Organisationseinheit dokumentieren.
- Erwartete kanonische Prüfsumme als Regressionserwartung festhalten.

**Ergebnis:** `real_demo.v1.json` als erster Referenzdatensatz und Benchmark, ohne fortgeschrittene Workflowzustände.

## AP 9: Schlankes Management Command für Dry Run und Apply bereitstellen

- Standardmäßig Dry Run ausführen; Apply nur über explizite Option.
- Bekannten Szenarioschlüssel oder expliziten Blueprint-Pfad unterstützen, ohne beliebige Fremdformate einzuführen.
- Menschenlesbare und maschinenlesbare Ausgabe sowie eindeutige Exitcodes bereitstellen.
- Fehlende Referenzvoraussetzungen verständlich melden.
- Keine Endnutzeroberfläche oder Blueprint-Verwaltung bauen.

**Ergebnis:** Technischer Einstiegspunkt für reproduzierbare Blueprint-Prüfung und -Erzeugung.

## AP 10: Regression, Drift-Schutz, Atomarität und Abschlussnachweis absichern

Mindestens testen:

- gültiges Schema und unbekannte Version,
- unbekannte Felder, ungültige Typen und fehlende Pflichtfelder,
- fehlende oder unzulässige Referenzobjekte,
- ungültige Metrikwerte und rote Zustände,
- formatierungsunabhängige kanonische Prüfsumme,
- manipulierte oder abweichende `real_demo.v1.json` gegen die festgelegte erwartete Prüfsumme,
- Dry Run ohne Datenänderung,
- vollständige Erzeugung,
- identische Wiederholung als `NO_CHANGE`,
- partielle oder fachlich abweichende Bestände als graphweiter `CONFLICT`,
- künstlicher Teilfehler mit vollständigem Rollback,
- Erhalt des Korrekturstands aus Issue #106,
- keine automatisch gesetzten Fokus-, Validierungs-, Präferenz-, Governance-, Freigabe-, Delivery-, Pilot- oder Go-live-Zustände,
- vollständige bestehende CI.

**Ergebnis:** Test- und Dokumentationsnachweis zu sämtlichen Abnahmekriterien aus Issue #118.

## Zuordnung zu den Abnahmekriterien aus Issue #118

| Abnahmekriterium | Arbeitspakete |
|---|---|
| Gap-Analyse dokumentiert | AP 1 |
| Versioniertes Blueprint-Schema vorhanden | AP 2, AP 3 |
| Dry Run und verständlicher Diff vorhanden | AP 5, AP 9 |
| Entwurfserzeugung atomar und reproduzierbar | AP 3, AP 6, AP 10 |
| Wiederholte Ausführung definiert und getestet | AP 5, AP 6, AP 10 |
| Keine roten Zustände automatisch gesetzt | AP 2, AP 4, AP 6, AP 8, AP 10 |
| `[Real-DEMO]` als Test- und Benchmark-Szenario | AP 1, AP 8, AP 10 |
| Lösung bleibt klein und repo-spezifisch | AP 2, AP 7, AP 9 |
