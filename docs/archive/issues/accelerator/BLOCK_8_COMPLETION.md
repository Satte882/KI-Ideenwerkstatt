# Block 8 – Abschlussnachweis

Issue: #124 · Gesamtplan: #116 · Workplan: `docs/accelerator/BLOCK_8_WORKPLAN.md`

## Ergebnis

Block 8 ergänzt den bestehenden Delivery-Pfad um einen kontrolliert aktivierbaren deterministischen Evidence-to-Delivery Mapper. Der bestehende Standardpfad bleibt unverändert; die Aktivierung erfolgt über `DELIVERY_EVIDENCE_MAPPER_ENABLED` beziehungsweise den expliziten Service-Parameter. Ein Default-on wurde in AP 10 mit der vollständigen Repository-Regression geprüft und verworfen, weil bestehende Prefill-, Readiness- und fokussierte Section-Save-Verträge dadurch verändert würden.

Der Mapper unterstützt 17 priorisierte V1-Zielfelder. Direkte Übernahmen und strukturierte Mehrquellen-Komposition funktionieren ohne Provider. Fehlende Evidence bleibt Gap; manuell abweichende Inhalte werden nicht überschrieben. Bestehende Packages ohne Block-8-Nachweis bleiben Legacy, bis ein Nutzer einen expliziten Refresh ausführt.

## AP 1–10

1. V1-Feldkatalog und statischer Mapping-Vertrag.
2. Kanonischer Evidence-Snapshot, Source-Hierarchie und Evidence-Hash.
3. Direkte deterministische Feldübernahme.
4. Deterministische Mehrquellen-Komposition.
5. Gap-, Placeholder- und Drei-Zustands-Konfliktmodell.
6. Kontrollierte Integration in die bestehende Delivery-Erzeugung und expliziter Refresh.
7. Provenance, Hash-Staleness, Legacy-Verhalten und Review-Reset.
8. Mapping-Status auf der bestehenden Delivery-Detailseite.
9. Optionale, gecachte LLM-Sprachverdichtung ausschließlich für freigegebene Resttextfelder.
10. Real-DEMO, semantischer Drift-Schutz, Gate-Regression und verifizierte kontrollierte Aktivierungsstrategie.

## Real-DEMO

`tests/test_block8_completion.py` baut den Golden Path aus realen Domänenobjekten auf:

`ValueStream → ValueStreamStage → ProcessAnalysis → SolutionOption → SolutionSelectionDecision → UseCase → ApprovalDecision → DeliveryPackage`

Der Real-DEMO aktiviert den Block-8-Mapper explizit über den bestehenden Service-Parameter. Damit wird der neue Pfad vollständig geprüft, ohne bestehende Delivery-Aufrufer implizit umzuschalten.

Nachgewiesen werden in einem reproduzierbaren Szenario:

- direkte Übernahme von Problem und Ziel,
- strukturierte Komposition von Messplan, Akzeptanzkriterien und Systemlandschaft,
- sichtbares Gap für fehlende Betriebsverantwortung,
- sichere Erstübernahme, sobald diese Evidence später vorliegt,
- Staleness durch geänderten Evidence-Hash,
- Konflikt bei manueller Delivery-Abweichung plus neuer Source-Evidence ohne Overwrite,
- Provider-Ausfall ohne Verlust des deterministischen Ergebnisses,
- LLM-Cache: gleicher Evidence-/Prompt-/Schema-Zustand erzeugt keinen zweiten Providercall,
- keine automatische Readiness, Section-Bestätigung oder Übergabe,
- unveränderliches `handed_over` Package.

## Aktivierungsstrategie

Die in AP 6 eingeführte Branch-by-Abstraction-Seam bleibt die finale Integrationsgrenze von Block 8:

- ohne Konfiguration bleibt der bestehende Delivery-Standardpfad aktiv,
- `DELIVERY_EVIDENCE_MAPPER_ENABLED` kann den Mapper gezielt aktivieren,
- einzelne Service-Aufrufer können `use_evidence_mapper=True` explizit setzen,
- `use_evidence_mapper=False` hält den bisherigen Pfad explizit verfügbar.

AP 10 hat einen Default-on gegen die vollständige Repository-Regression geprüft. Dabei wurden bestehende Verträge für Messplan-Prefill, Readiness-Klassifikation und fokussiertes Section-Save verändert. Der Default-on wurde deshalb verworfen und nicht in den Abschlussstand übernommen. Damit bleibt der Golden Path deploybar, während der Block-8-Pfad kontrolliert nutzbar ist.

## Drift-Schutz

Die fachliche Referenz liegt unter:

- `tests/fixtures/accelerator/block8_real_demo.v1.json`
- `tests/fixtures/accelerator/block8_real_demo.v1.sha256`

SHA-256 der kanonischen Referenz:

`01d9d50d7513e469345128ed5f1cf79180c94e303efb8850cab78e5b190209f3`

Die Referenz enthält bewusst keine UUIDs, Datenbank-IDs, `created_at`, `updated_at`, `finalized_at`, Provider-Latenzen oder andere volatile Metadaten. Der Test vergleicht sowohl den semantischen Zustand als auch dessen kanonischen SHA-256-Hash.

## Gate-Invarianz

Block 8 setzt keine fachlichen Gates automatisch:

- keine Sektionsbestätigung,
- kein `ready`,
- keine Approval-Entscheidung,
- keine Übergabe,
- kein Lifecycle-Fortschritt.

Ein echter Mapper-Write setzt weiterhin nur die betroffene bestehende Section Review zurück. Ein No-op setzt nichts zurück. Ein bereits übergebenes Package kann weder deterministisch refreshed noch über den LLM-Resttext verändert werden.

## LLM-Grenze

Der deterministische Nutzen ist providerunabhängig. LLM-Sprachverdichtung bleibt optional und ist ausschließlich für die im Mapping-Vertrag markierten Felder `system_landscape` und `acceptance_criteria` zulässig.

Der Resttextpfad verwendet:

- den bestehenden OpenRouter-Transport,
- die bestehende Accelerator-LLM-Policy,
- die bestehenden Context-/User-/Global-Quoten,
- vorhandene Token-/Kostenfelder aus der Provider-Usage,
- Evidence-Hash + Prompt-Version + Schema-Version als Cache-Schlüssel.

Gap, Konflikt, stale Source, Legacy-Package oder manuelle Divergenz verhindern den Provideraufruf. Es gibt keinen automatischen Retry und kein zusätzliches Billing-/LLM-Run-System.

## Abnahmekriterien aus #124

| Kriterium | Nachweis |
| --- | --- |
| Gap-Analyse dokumentiert | Workplan Abschnitt 2 |
| Explizite Quellen-/Transformationsregeln | `evidence_mapping_contract.py` |
| Deterministisches Mapping ohne LLM | AP 2–6 und Real-DEMO |
| Lücken und Konflikte sichtbar | AP 5 und AP 8 |
| LLM nur für freigegebene Freitextfelder | AP 9 + Contract-Whitelist |
| Provider-Ausfall blockiert deterministisches Ergebnis nicht | AP 9 + Real-DEMO |
| Manifest, Staleness, Readiness und Reviews bleiben wirksam | AP 5–8 + Gate-Regression |
| Keine automatische Bestätigung/Freigabe | AP 7 + Real-DEMO |
| Priorisierte V1-Feldmenge | 17 statisch definierte Zielwerte |

## Abschlussbedingung

Block 8 gilt erst als abgeschlossen, wenn der AP-10-PR mit der unveränderten vollständigen Repository-CI grün ist, gemergt wurde und die AP-10-Checkliste in #124 danach abgehakt ist. Issue #116 bleibt unverändert.
