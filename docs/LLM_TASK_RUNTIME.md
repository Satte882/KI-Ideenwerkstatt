# First-Wave LLM Task Runtime

**Scope:** technische Basis für #349 und die beiden First-Wave-Tasks aus #328.

## Zielbild

Die neuen KI-Aufgaben verwenden weiterhin `ki_radar/core/openrouter.py` als einzigen Provider-Transport. Darauf liegt ein kleiner Task-Runtime-Layer in `ki_radar/core/llm_tasks.py`.

Unterstützte Tasks:

- `delivery_field_draft`
- `origin_consistency_review`

Nicht Teil dieses Layers sind fachliche Context Builder, Prompts, JSON-Schemas, Source-Allowlisten, Output-Validatoren oder Adoption-/Speicherlogik. Diese bleiben in `delivery` beziehungsweise `use_cases`.

## Provider- und Datenschutzregeln

Jeder neue First-Wave-Aufruf setzt verbindlich:

- `provider.zdr=true`
- `provider.data_collection="deny"`
- `provider.require_parameters=true`
- keine automatische Lockerung der Regeln
- keine automatische Retry-Schleife

Der OpenRouter-Transport unterstützt zusätzlich einen expliziten Reasoning-Aufwand pro Task. `OPENROUTER_REASONING_EXCLUDE=true` verhindert weiterhin, dass Reasoning-Inhalte in der Antwort zurückgegeben werden; dies ist unabhängig von `reasoning.effort`.

## Startgrenzen

| Parameter | `delivery_field_draft` | `origin_consistency_review` |
|---|---:|---:|
| max. Input | 12.000 Zeichen | 16.000 Zeichen |
| technisches Outputbudget | 16.384 Tokens | 4.096 Tokens |
| Reasoning-Aufwand | `low` | `medium` |
| Temperatur | 0.1 | 0.1 |
| Timeout | 60 s | 60 s |
| Context-Aufrufe | 3/Tag | 3/Tag |
| User-Grenze | 20/Tag gemeinsam | 20/Tag gemeinsam |
| globale Grenze | 100/Tag gemeinsam | 100/Tag gemeinsam |
| technische Run-Retention | 90 Tage | 90 Tage |

Die sichtbare Textlänge wird nicht durch das technische Tokenlimit erzwungen. Sie gehört in den jeweiligen fachlichen Prompt-Vertrag.

Die Werte können über die in `.env.example` dokumentierten `LLM_TASK_*`, `LLM_DELIVERY_FIELD_DRAFT_*` und `LLM_ORIGIN_CONSISTENCY_REVIEW_*` Variablen angepasst werden. Ungültige oder inkonsistente Grenzen führen fail-closed zu `invalid_configuration`.

## Run-Metadaten

`LLMTaskRun` speichert nur technische Nachvollziehbarkeit:

- Task- und interner Objektbezug,
- optionaler Feldschlüssel,
- Benutzerbezug,
- `source_hash`, Prompt-/Schema-Version,
- Provider/Modell,
- Start/Ende/Laufzeit,
- Status/Fehlercode,
- Input-/Output-Zeichenanzahl,
- Token und Kosten, soweit Providerdaten vorhanden,
- Ablaufzeitpunkt.

Nicht gespeichert werden vollständige Prompts, Domain-Quelltexte, Provider-Rohantworten, Delivery-Draft-Inhalte oder Konsistenz-Finding-Texte.

Abgelaufene Run-Metadaten werden mit folgendem Command entfernt:

```bash
python manage.py cleanup_expired_llm_task_runs
```

Die First-Wave-Standardretention beträgt 90 Tage. Domain-spezifische Preview-/Output-Retention wird in #350 beziehungsweise #351 umgesetzt und ist nicht Bestandteil des Core-Runtime-Modells.

## Quoten

`LLMTaskQuota` zählt neue First-Wave-Aufrufe getrennt von `AcceleratorLLMQuota`:

- Context: `task_type + object_type + object_id + optional field_key + date`
- User: gemeinsames Tageslimit über beide neuen Tasks
- Global: gemeinsames Tageslimit über beide neuen Tasks

Run-Erstellung und alle drei Quotenreservierungen erfolgen in einer Datenbanktransaktion. Wird ein Limit überschritten, wird die gesamte Reservierung zurückgerollt, bevor ein Provideraufruf stattfinden kann.

## Domain-Sicherheitsvertrag

Die späteren Domain-Tasks müssen zusätzlich selbst durchsetzen:

- explizite Context-Allowlist,
- stabile Source-IDs und `source_hash` aus exakt dem Providerpayload,
- Domain-Inhalte als `untrusted source data`,
- strict JSON-Schema,
- fail-closed bei unbekannten Source-IDs,
- deterministische Grounding-/Staleness-/Konfliktprüfungen,
- keine automatische Speicherung, Blockerbeseitigung oder fachliche Entscheidung.

Der Core-Layer darf diese fachliche Verantwortung nicht übernehmen.
