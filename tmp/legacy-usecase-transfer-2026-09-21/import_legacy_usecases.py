from __future__ import annotations

import json
from pathlib import Path

from django.db import transaction

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.stage_focus import StageFocusDecision
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.governance.models import GovernanceAssessment, GovernanceReview
from ki_radar.reviews.models import Review
from ki_radar.use_cases.classification import UseCaseClassification
from ki_radar.use_cases.models import (
    ApprovalDecision,
    DecisionAssessment,
    UseCase,
    UseCaseCounter,
)


SNAPSHOT_PATH = pathlib.Path(__file__).with_name("legacy-usecases.snapshot.json")


def _scalar_defaults(model, data: dict) -> dict:
    defaults = {}
    for field in model._meta.concrete_fields:
        if field.primary_key or field.is_relation or field.name in {"created_at", "updated_at"}:
            continue
        if field.name not in data:
            continue
        value = data[field.name]
        if value is None:
            defaults[field.name] = None
            continue
        defaults[field.name] = field.to_python(value)
    return defaults


def _restore_timestamps(obj, data: dict) -> None:
    updates = {}
    for name in ("created_at", "updated_at"):
        value = data.get(name)
        if value is None:
            continue
        field = obj._meta.get_field(name)
        updates[name] = field.to_python(value)
    if updates:
        type(obj).objects.filter(pk=obj.pk).update(**updates)


def _username(value):
    return User.objects.filter(username=value).first() if value else None


def _business_unit(value):
    return BusinessUnit.objects.filter(name=value).first() if value else None


def _upsert_business_units(snapshot: dict) -> None:
    for data in snapshot.get("business_units", []):
        defaults = _scalar_defaults(BusinessUnit, data)
        unit, _ = BusinessUnit.objects.update_or_create(name=data["name"], defaults=defaults)
        _restore_timestamps(unit, data)


def _upsert_users(snapshot: dict) -> None:
    for data in snapshot.get("users", []):
        username = data["username"]
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User(username=username)
            user.set_unusable_password()
            user.first_name = data.get("first_name", "")
            user.last_name = data.get("last_name", "")
            user.email = data.get("email", "")
            user.is_active = bool(data.get("is_active", True))
            user.is_staff = bool(data.get("is_staff", False))
            user.is_superuser = bool(data.get("is_superuser", False))
            user.business_unit = _business_unit(data.get("business_unit"))
            user.save()
        elif username != "Satinder":
            user.first_name = data.get("first_name", "")
            user.last_name = data.get("last_name", "")
            user.email = data.get("email", "")
            user.is_active = bool(data.get("is_active", True))
            user.business_unit = _business_unit(data.get("business_unit"))
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "email",
                    "is_active",
                    "business_unit",
                    "updated_at",
                ]
            )


def _advance_use_case_counter(snapshot: dict) -> None:
    targets = []
    for item in snapshot.get("use_cases", []):
        short_id = str(item.get("record", {}).get("short_id", ""))
        if short_id.startswith("KI-") and short_id[3:].isdigit():
            targets.append(int(short_id[3:]))
    if not targets:
        return
    target = max(targets)
    latest = UseCaseCounter.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
    while latest < target:
        latest = UseCaseCounter.objects.create().pk


def _upsert_use_case(record: dict) -> UseCase:
    defaults = _scalar_defaults(UseCase, record)
    defaults.update(
        {
            "business_unit": _business_unit(record.get("business_unit")),
            "business_owner": _username(record.get("business_owner")),
            "coordinator": _username(record.get("coordinator")),
            "submitter": _username(record.get("submitter")),
            "technical_owner": _username(record.get("technical_owner")),
        }
    )
    short_id = record["short_id"]
    use_case, _ = UseCase.objects.update_or_create(short_id=short_id, defaults=defaults)
    _restore_timestamps(use_case, record)
    return use_case


def _upsert_architecture(use_case: UseCase, data: dict | None) -> None:
    if not data:
        return

    vs_data = data.get("value_stream")
    stage_data = data.get("stage")
    pa_data = data.get("process_analysis")
    if not (vs_data and stage_data and pa_data):
        return

    vs_defaults = _scalar_defaults(ValueStream, vs_data)
    vs_defaults.update(
        {
            "business_unit": _business_unit(vs_data.get("business_unit")),
            "owner": _username(vs_data.get("owner")),
            "created_by": _username(vs_data.get("created_by")),
        }
    )
    value_stream, _ = ValueStream.objects.update_or_create(
        business_unit=vs_defaults["business_unit"],
        name=vs_data["name"],
        defaults=vs_defaults,
    )
    _restore_timestamps(value_stream, vs_data)

    stage_defaults = _scalar_defaults(ValueStreamStage, stage_data)
    stage, _ = ValueStreamStage.objects.update_or_create(
        value_stream=value_stream,
        sequence=stage_data["sequence"],
        defaults=stage_defaults,
    )
    _restore_timestamps(stage, stage_data)

    for focus_data in data.get("value_stream_focus", []):
        focus_defaults = _scalar_defaults(ValueStreamFocus, focus_data)
        focus_defaults["updated_by"] = _username(focus_data.get("updated_by"))
        focus, _ = ValueStreamFocus.objects.update_or_create(
            value_stream=value_stream,
            defaults=focus_defaults,
        )
        _restore_timestamps(focus, focus_data)

    for focus_data in data.get("stage_focus_decisions", []):
        criteria = focus_data.get("criteria_snapshot") or {}
        selected_payload = None
        for payload in criteria.values():
            if isinstance(payload, dict) and (
                payload.get("name") == stage.name or payload.get("sequence") == stage.sequence
            ):
                selected_payload = payload
                break
        if selected_payload is None and len(criteria) == 1:
            selected_payload = next(iter(criteria.values()))
        rewritten_criteria = (
            {str(stage.pk): selected_payload} if selected_payload is not None else {}
        )
        focus_defaults = _scalar_defaults(StageFocusDecision, focus_data)
        focus_defaults.update(
            {
                "selected_stage": stage,
                "selected_by": _username(focus_data.get("selected_by")),
                "criteria_snapshot": rewritten_criteria,
            }
        )
        decision, _ = StageFocusDecision.objects.update_or_create(
            value_stream=value_stream,
            defaults=focus_defaults,
        )
        _restore_timestamps(decision, focus_data)

    pa_defaults = _scalar_defaults(ProcessAnalysis, pa_data)
    pa_defaults["analyzed_by"] = _username(pa_data.get("analyzed_by"))
    process, _ = ProcessAnalysis.objects.update_or_create(
        stage=stage,
        name=pa_data["name"],
        defaults=pa_defaults,
    )
    _restore_timestamps(process, pa_data)

    for validation_data in data.get("process_validations", []):
        defaults = _scalar_defaults(ProcessValidation, validation_data)
        defaults["validated_by"] = _username(validation_data.get("validated_by"))
        validation, _ = ProcessValidation.objects.update_or_create(
            process_analysis=process,
            process_version=validation_data["process_version"],
            defaults=defaults,
        )
        _restore_timestamps(validation, validation_data)

    option_map = {}
    for option_data in data.get("solution_options", []):
        defaults = _scalar_defaults(SolutionOption, option_data)
        defaults["created_by"] = _username(option_data.get("created_by"))
        option, _ = SolutionOption.objects.update_or_create(
            process_analysis=process,
            name=option_data["name"],
            defaults=defaults,
        )
        _restore_timestamps(option, option_data)
        option_map[option.name] = option

    for decision_data in data.get("solution_selection_decisions", []):
        selected = option_map.get(decision_data.get("selected_option_name"))
        if selected is None:
            continue
        defaults = _scalar_defaults(SolutionSelectionDecision, decision_data)
        defaults["decided_by"] = _username(decision_data.get("decided_by"))
        decided_at = defaults.pop("decided_at", None)
        lookup = {
            "process_analysis": process,
            "selected_option": selected,
        }
        if decided_at is not None:
            lookup["decided_at"] = decided_at
        decision, created = SolutionSelectionDecision.objects.get_or_create(
            **lookup,
            defaults=defaults,
        )
        if created:
            _restore_timestamps(decision, decision_data)

    origin_data = data.get("origin") or {}
    selected_option = option_map.get(origin_data.get("selected_solution_option_name"))
    origin_defaults = _scalar_defaults(UseCaseOrigin, origin_data)
    origin_defaults.update(
        {
            "stage": stage,
            "process_analysis": process,
            "solution_option": selected_option,
        }
    )
    origin, _ = UseCaseOrigin.objects.update_or_create(
        use_case=use_case,
        defaults=origin_defaults,
    )
    _restore_timestamps(origin, origin_data)


def _upsert_classifications(use_case: UseCase, items: list[dict]) -> None:
    if not items:
        return
    data = items[-1]
    defaults = _scalar_defaults(UseCaseClassification, data)
    classification, _ = UseCaseClassification.objects.update_or_create(
        use_case=use_case,
        defaults=defaults,
    )
    _restore_timestamps(classification, data)


def _upsert_decision_data(use_case: UseCase, item: dict) -> dict[int, DecisionAssessment]:
    assessments = {}
    for data in item.get("decision_assessments", []):
        defaults = _scalar_defaults(DecisionAssessment, data)
        defaults["assessed_by"] = _username(data.get("assessed_by"))
        assessment, _ = DecisionAssessment.objects.update_or_create(
            use_case=use_case,
            version=data["version"],
            defaults=defaults,
        )
        _restore_timestamps(assessment, data)
        assessments[assessment.version] = assessment

    for data in item.get("approval_decisions", []):
        assessment = assessments.get(data.get("assessment_version"))
        defaults = _scalar_defaults(ApprovalDecision, data)
        defaults.update(
            {
                "condition_owner": _username(data.get("condition_owner")),
                "decided_by": _username(data.get("decided_by")),
                "second_approved_by": _username(data.get("second_approved_by")),
                "second_approval_assignee": _username(data.get("second_approval_assignee")),
                "second_approval_returned_by": _username(
                    data.get("second_approval_returned_by")
                ),
            }
        )
        decision, created = ApprovalDecision.objects.get_or_create(
            use_case=use_case,
            assessment=assessment,
            decision_status=data["decision_status"],
            defaults=defaults,
        )
        if created:
            _restore_timestamps(decision, data)
    return assessments


def _upsert_governance(use_case: UseCase, item: dict) -> None:
    screening_map = {}
    for data in item.get("governance_assessments", []):
        defaults = _scalar_defaults(GovernanceAssessment, data)
        defaults["reviewer"] = _username(data.get("reviewer"))
        screening, _ = GovernanceAssessment.objects.update_or_create(
            use_case=use_case,
            basis_version=data["basis_version"],
            defaults=defaults,
        )
        _restore_timestamps(screening, data)
        screening_map[screening.basis_version] = screening

    for data in item.get("governance_reviews", []):
        screening = screening_map.get(data.get("screening_basis_version"))
        defaults = _scalar_defaults(GovernanceReview, data)
        defaults.update(
            {
                "reviewer": _username(data.get("reviewer")),
                "screening": screening,
            }
        )
        review, created = GovernanceReview.objects.get_or_create(
            use_case=use_case,
            review_type=data["review_type"],
            reviewed_at=GovernanceReview._meta.get_field("reviewed_at").to_python(
                data["reviewed_at"]
            ),
            defaults=defaults,
        )
        if created:
            _restore_timestamps(review, data)


def _upsert_reviews(use_case: UseCase, item: dict) -> None:
    for data in item.get("reviews", []):
        defaults = _scalar_defaults(Review, data)
        defaults.update(
            {
                "reviewer": _username(data.get("reviewer")),
                "action_owner": _username(data.get("action_owner")),
            }
        )
        review, created = Review.objects.get_or_create(
            use_case=use_case,
            review_date=Review._meta.get_field("review_date").to_python(data["review_date"]),
            decision=data["decision"],
            defaults=defaults,
        )
        if created:
            _restore_timestamps(review, data)


def _upsert_delivery(use_case: UseCase, item: dict) -> None:
    for data in item.get("delivery_packages", []):
        assessment_version = data.get("generated_from_assessment_version")
        decision_status = data.get("generated_from_decision_status")
        generated_from = ApprovalDecision.objects.filter(
            use_case=use_case,
            decision_status=decision_status,
            assessment__version=assessment_version,
        ).first()
        if generated_from is None:
            continue
        defaults = _scalar_defaults(DeliveryPackage, data)
        defaults.update(
            {
                "generated_from_decision": generated_from,
                "created_by": _username(data.get("created_by")),
                "technical_owner": _username(data.get("technical_owner")),
                "handed_over_by": _username(data.get("handed_over_by")),
            }
        )
        package, created = DeliveryPackage.objects.get_or_create(
            use_case=use_case,
            version=data["version"],
            defaults=defaults,
        )
        if created:
            _restore_timestamps(package, data)


@transaction.atomic
def import_legacy_usecases() -> dict:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    if snapshot.get("metadata", {}).get("contains_secrets") is not False:
        raise RuntimeError("Legacy transfer snapshot safety marker is missing.")

    _upsert_business_units(snapshot)
    _upsert_users(snapshot)
    _advance_use_case_counter(snapshot)

    imported = []
    for item in snapshot.get("use_cases", []):
        use_case = _upsert_use_case(item["record"])
        _upsert_architecture(use_case, item.get("architecture"))
        _upsert_classifications(use_case, item.get("classifications", []))
        _upsert_decision_data(use_case, item)
        _upsert_governance(use_case, item)
        _upsert_reviews(use_case, item)
        _upsert_delivery(use_case, item)
        imported.append(use_case.short_id)

    return {
        "use_cases": imported,
        "count": len(imported),
        "business_units": BusinessUnit.objects.filter(
            name__in=[x["name"] for x in snapshot.get("business_units", [])]
        ).count(),
    }
