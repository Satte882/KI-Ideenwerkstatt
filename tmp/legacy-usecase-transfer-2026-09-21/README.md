# Temporary legacy use-case transfer

**Temporary only. Delete this entire folder after successful transfer to the new Render database.**

Source: suspended/resumed Render database `KIIW-db / ki_radar_8q42`.

Target: fresh `KI-Ideenwerkstatt-db`.

## Contents

- `legacy-usecases.snapshot.json` — normalized transport snapshot for exactly two legacy use cases.
- No passwords, API keys, database URLs, password hashes, or other secrets are included.
- Old database primary keys are intentionally not used as import keys. Relations are represented with stable natural references such as title, username, business-unit name, process name, and solution-option name.
- Existing JSON evidence/snapshot fields are preserved as business evidence, even if they contain historical UUID strings internally.

## Use cases

1. KI-gestützte Assistenz in der Schadenbearbeitung eines Versicherungsunternehmens
2. KI-gestützte Erstellung und Qualitätssicherung von Reiseausschreibungen

## Snapshot object counts

```json
[
  {
    "title": "KI-gestützte Assistenz in der Schadenbearbeitung eines Versicherungsunternehmens",
    "solution_options": 3,
    "decision_assessments": 2,
    "approval_decisions": 1,
    "governance_assessments": 1,
    "governance_reviews": 6,
    "reviews": 3,
    "delivery_packages": 1
  },
  {
    "title": "KI-gestützte Erstellung und Qualitätssicherung von Reiseausschreibungen",
    "solution_options": 3,
    "decision_assessments": 1,
    "approval_decisions": 0,
    "governance_assessments": 1,
    "governance_reviews": 3,
    "reviews": 0,
    "delivery_packages": 0
  }
]
```

Users are represented only by non-secret identity metadata needed to resolve ownership/reviewer references. The existing target superuser `Satinder` should be reused. Synthetic legacy users may be recreated without reusable passwords if required for referential integrity.

Do not treat this folder as application configuration or seed data. It exists only to bridge the one-time database transfer.
