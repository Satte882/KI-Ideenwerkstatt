# Block 2 – Abschlussnachweis

## Gegenstand

Block 2 stellt einen deterministischen, LLM-freien und repo-spezifischen Pfad bereit, der den versionierten `[Real-DEMO]`-Blueprint als konsistenten Entwurfsgraph prüft und atomar erzeugt.

## Referenzartefakte

- Blueprint: `ki_radar/core/scenario_blueprints/real_demo.v1.json`
- Festgeschriebene kanonische SHA-256-Prüfsumme: `a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5`
- Prüfsummendatei: `ki_radar/core/scenario_blueprints/real_demo.v1.sha256`
- Technischer Einstiegspunkt: `python manage.py apply_scenario_blueprint`
- Standardmodus: schreibfreier Dry Run
- Schreibmodus: ausschließlich mit `--apply`

## Reproduzierbarkeitsgrenze

Der Blueprint erzeugt keine Benutzer, Gruppen oder Organisationseinheiten. Die benannten Referenzobjekte müssen vorab über den bestehenden `seed_demo_data`-Pfad oder gleichwertig vorhanden sein. Fehlende oder mehrdeutige Referenzen werden vor jedem Schreibzugriff abgelehnt.

## Konflikt- und Transaktionsregel

- `CREATE`: Der vollständige Graph ist neu und kann atomar erzeugt werden.
- `NO_CHANGE`: Der vollständige Graph entspricht bereits dem Blueprint; es wird nichts geschrieben.
- `CONFLICT`: Mindestens ein Objekt oder Feld weicht ab; der gesamte Graph-Apply wird abgebrochen.
- Teilanwendung, Merge, Update und Replace sind nicht vorgesehen.
- Jeder Validierungs-, Form-, Integritäts- oder Post-Apply-Fehler verwirft die gesamte Transaktion.

## Sichere Entwurfsgrenze

Der Referenzgraph setzt ausschließlich Entwurfszustände. Insbesondere werden keine Fokusentscheidung, Prozessvalidierung, bevorzugte Lösungsoption, Governance-Freigabe, Delivery-Bestätigung, Übergabe, Pilotfreigabe, Go-live- oder Abschlussentscheidung erzeugt.

## Prüfsummen-Governance

Die Regressionserwartung basiert auf kanonischem JSON mit sortierten Objektschlüsseln, erhaltener Array-Reihenfolge und normalisierten Dezimalzahlen. Eine Änderung der Referenzdatei oder ihrer Prüfsumme benötigt einen eigenen begründeten PR, eine bewusste Prüfung der fachlichen Auswirkungen und die gemeinsame Aktualisierung von JSON-Datei, Prüfsummendatei und Regressionstest.

## Regressionen

`tests/test_real_demo_blueprint.py` prüft:

1. die Repository-Datei gegen die festgeschriebene kanonische Prüfsumme,
2. Erkennung einer manipulierten Blueprint-Nutzlast,
3. schreibfreien Dry Run auf vorbereiteter Umgebung,
4. vollständige atomare Erzeugung des erwarteten Graphen,
5. ausschließlich sichere Entwurfszustände,
6. gespeicherte Herkunft einschließlich Blueprint-Version und Prüfsumme,
7. wiederholten Apply als `NO_CHANGE` ohne Duplikate,
8. Dry Run nach Apply als `NO_CHANGE`,
9. vollständigen Rollback bei einem erzwungenen Fehler während der Grapherzeugung.

## Abnahmekriterien aus Issue #118

| Abnahmekriterium | Nachweis |
|---|---|
| Gap-Analyse dokumentiert | `docs/accelerator/BLOCK_2_GAP_ANALYSIS.md` |
| Versioniertes Blueprint-Schema vorhanden | `docs/accelerator/SCENARIO_BLUEPRINT_V1.md` und `scenario_blueprint_contract.py` |
| Dry Run und verständlicher Diff vorhanden | `scenario_blueprint_diff.py` und Management Command |
| Entwurfserzeugung atomar und reproduzierbar | `scenario_blueprint_apply.py` und Rollback-/E2E-Regression |
| Wiederholte Ausführung definiert und getestet | `CREATE`, `NO_CHANGE`, graphweites `CONFLICT`; Regressionstest |
| Keine roten Gate-, Entscheidungs- oder Bestätigungszustände | Positivlistenvertrag, Referenz-Blueprint und Zustandsassertionen |
| `[Real-DEMO]` als Test- und Benchmark-Szenario | versioniertes JSON, Prüfsumme und vollständiger Regressionstest |
| Lösung bleibt klein und repo-spezifisch | ein JSON-Vertrag, vorhandene Forms/Services, ein Management Command; keine Importplattform |
