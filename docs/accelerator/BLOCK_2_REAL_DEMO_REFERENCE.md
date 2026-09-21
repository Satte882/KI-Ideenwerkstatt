# Block 2: `[Real-DEMO]`-Referenz-Blueprint Version 1

**Issue:** #118  
**Blueprint:** `ki_radar/core/scenario_blueprints/real_demo.v1.json`  
**Schema-Version:** `1.0`  
**Kanonische SHA-256-Prüfsumme:** `a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5`

## Referenzzweck

Der Blueprint ist der erste deterministische Referenzdatensatz für Block 2. Er beschreibt den bekannten Beschaffungspfad als reinen Entwurfsgraphen:

- Value Stream `[Real-DEMO] Beschaffungsbedarf bis Bestellung`,
- drei Value-Stream-Phasen,
- eine Prozessanalyse zum Angebotsvergleich,
- drei lösungsoffene Kandidaten,
- einen Use-Case-Entwurf mit primärer Zeitmetrik,
- die Herkunftsbeziehung zur assistierten Option.

Die Referenz ist kein Export einer vollständigen lokalen Produktiv- oder Demo-Datenbank. Sie enthält ausschließlich explizit geprüfte, repo-kompatible Felder des Golden Path.

## Erhalt des Korrekturstands aus Issue #106

Der in Issue #106 korrigierte Scope-Zuschnitt wird ausdrücklich erhalten:

- `scope_in` enthält ausschließlich den eingeschlossenen Ablauf.
- `scope_out` ist ein eigenständiges Feld.
- `scope_in` enthält keinen eingebetteten Abschnitt „Nicht im Scope“.
- Es gibt keine automatische Textzerlegung oder Heuristik.

Damit friert der Referenz-Blueprint die zuvor behobene Vermischung von `scope_in` und `scope_out` nicht erneut ein.

## Zulässiger Entwurfszustand

Der Referenzgraph setzt ausschließlich:

- Value Stream `draft`,
- Fokus `not_screened`,
- Prozessanalyse `draft`,
- alle Lösungsoptionen `candidate` und `draft`,
- Use Case `idea` und `clarification`.

Die Herkunft verweist auf die assistierte Option, ohne diese als bevorzugt oder bewertet zu markieren. Es werden keine Validierungen, Entscheidungen, Governance-Ergebnisse, Freigaben, Delivery Packages, Übergaben, Pilot- oder Go-live-Zustände beschrieben.

## Referenzvoraussetzungen

Vor Dry Run oder Apply müssen die vorhandenen Demo-Referenzen angelegt sein:

- Organisationseinheit `[DEMO] Prozesse & Organisation`,
- Benutzer `demo_business_owner`,
- Benutzer `demo_ki_koordinator`,
- zugehörige aktive Gruppen- und Rollenbeziehungen.

Diese Voraussetzungen werden durch den bestehenden Demo-Seed hergestellt. Der Blueprint erzeugt keine Benutzer, Rollen, Gruppen oder Organisationseinheiten.

Auf einer fachlich leeren Datenbank ohne diese Referenzobjekte ist die Anwendung bewusst nicht möglich und liefert eine verständliche Validierungsmeldung.

## Reproduzierbarkeit und vorhandene Daten

Auf einer Datenbank mit vorhandenen Referenzobjekten, aber ohne Szenariograph, ergibt der Dry Run `CREATE` und der Apply erzeugt den vollständigen Graphen atomar.

Bei identischer Wiederholung ergibt sich `NO_CHANGE` ohne fachliche Schreiboperation.

Ein bereits vorhandener, nur teilweise passender oder manuell abweichender `[Real-DEMO]`-Graph ergibt graphweit `CONFLICT`. Version 1 aktualisiert, merged oder ersetzt solche Daten nicht.

## Prüfsumme und Governance

Die Prüfsumme wird aus der kanonisch serialisierten JSON-Struktur gebildet, nicht aus den Rohbytes der formatierten Datei. Einrückung, Schlüsselreihenfolge und äquivalente Dezimaldarstellungen ändern sie deshalb nicht.

Die festgeschriebene Prüfsumme darf nur geändert werden, wenn:

1. die Blueprint-Version bewusst erhöht wird, oder
2. eine fachlich bestätigte Korrektur des Referenzszenarios dokumentiert wird.

Die Änderung muss in einem eigenen, begründeten Pull Request erfolgen. Eine Anpassung ausschließlich zur Behebung eines Drift-Tests ist unzulässig.
