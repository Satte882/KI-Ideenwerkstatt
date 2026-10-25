"""Bounded human intake context; never a discovery or evidence decision."""

from django.core.exceptions import ValidationError

SCHEMA = "topic-intake-v1"
OCCASIONS = {
    "problem": (
        "Etwas läuft nicht rund",
        "Was läuft nicht rund?",
        "Zum Beispiel: Kunden warten lange auf eine Antwort.",
    ),
    "goal": (
        "Ich habe ein Ziel",
        "Was möchtest du erreichen?",
        "Zum Beispiel: Mehr Kunden für eine Vertragsverlängerung gewinnen.",
    ),
    "explore": (
        "Ich suche Potenziale",
        "Welchen Bereich möchtest du untersuchen?",
        "Zum Beispiel: Die Zusammenarbeit mit unseren Partnern im Einkauf.",
    ),
}
PERSPECTIVES = (
    ("staff", "Mitarbeitende"),
    ("leadership", "Führung"),
    ("customers", "Kunden"),
    ("partners", "Partner"),
)


def validate_intake_context(value):
    if value == {}:
        return
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "occasion", "perspectives", "original_text"}
        or value.get("schema_version") != SCHEMA
        or not isinstance(value.get("occasion"), str)
        or value["occasion"] not in OCCASIONS
        or not isinstance(value.get("original_text"), str)
        or not value["original_text"].strip()
        or len(value["original_text"]) > 4000
        or not isinstance(value.get("perspectives"), list)
        or len(value["perspectives"]) > len(PERSPECTIVES)
        or any(not isinstance(x, str) or x not in dict(PERSPECTIVES) for x in value["perspectives"])
        or len(value["perspectives"]) != len(set(value["perspectives"]))
    ):
        raise ValidationError("Ungültiger ursprünglicher Erfassungskontext.")


def display_context(context):
    if not context:
        return None
    validate_intake_context(context)
    return {
        "occasion": OCCASIONS[context["occasion"]][0],
        "perspectives": [label for key, label in PERSPECTIVES if key in context["perspectives"]],
        "original_text": context["original_text"],
    }
