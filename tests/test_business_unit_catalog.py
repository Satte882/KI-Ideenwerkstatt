import pytest

EXPECTED_PRODUCTIVE_UNITS = {
    "Unternehmenssteuerung",
    "Touristik & Operations",
    "Kundenservice & Buchung",
    "Marketing & Vertrieb",
    "IT & Digitalisierung",
    "Finanzen & Administration",
}


@pytest.mark.django_db
def test_productive_catalog_is_seeded_without_company_prefix():
    from ki_radar.accounts import business_units

    names = set(business_units.active_productive_business_units().values_list("name", flat=True))
    assert names == EXPECTED_PRODUCTIVE_UNITS
    assert not any(name.startswith("RSD") for name in EXPECTED_PRODUCTIVE_UNITS)


@pytest.mark.django_db
def test_new_business_unit_defaults_to_productive():
    from ki_radar.accounts import business_units
    from ki_radar.accounts.models import BusinessUnit

    unit = BusinessUnit.objects.create(name="Neue bestätigte Einheit")
    assert unit.catalog_scope == BusinessUnit.CatalogScope.PRODUCTIVE
    assert business_units.active_productive_business_units().filter(pk=unit.pk).exists()


@pytest.mark.django_db
def test_demo_and_legacy_units_are_not_productive_choices():
    from ki_radar.accounts import business_units
    from ki_radar.accounts.models import BusinessUnit

    demo = BusinessUnit.objects.create(
        name="Demo Einheit",
        catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
    )
    legacy = BusinessUnit.objects.create(
        name="Historischer Bestand",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    ids = set(business_units.active_productive_business_units().values_list("pk", flat=True))
    assert demo.pk not in ids
    assert legacy.pk not in ids


@pytest.mark.django_db
def test_existing_legacy_reference_can_be_rendered_as_current_choice():
    from ki_radar.accounts import business_units
    from ki_radar.accounts.models import BusinessUnit

    legacy = BusinessUnit.objects.create(
        name="Historischer Bestand für Referenz",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    ids = set(
        business_units.selectable_business_units(current_id=legacy.pk).values_list("pk", flat=True)
    )
    assert legacy.pk in ids


@pytest.mark.django_db
def test_all_productive_business_unit_forms_hide_demo_and_legacy_units():
    from ki_radar.accelerator.architect_forms import AutonomousDiscoveryStartForm
    from ki_radar.accounts.models import BusinessUnit
    from ki_radar.architecture.forms import ValueStreamForm
    from ki_radar.use_cases.forms import UseCaseForm
    from ki_radar.use_cases.idea_forms import IdeaCandidateForm
    from ki_radar.use_cases.intake import ProblemStepForm

    demo = BusinessUnit.objects.create(
        name="Nicht auswählbare Demo-Einheit",
        catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
    )
    legacy = BusinessUnit.objects.create(
        name="Nicht auswählbarer Bestand",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )

    forms = [
        AutonomousDiscoveryStartForm(),
        IdeaCandidateForm(),
        ProblemStepForm(),
        UseCaseForm(),
        ValueStreamForm(),
    ]

    for form in forms:
        ids = set(form.fields["business_unit"].queryset.values_list("pk", flat=True))
        assert demo.pk not in ids
        assert legacy.pk not in ids


@pytest.mark.django_db
def test_discovery_service_rejects_demo_unit_when_form_is_bypassed(owner):
    from django.core.exceptions import ValidationError

    from ki_radar.accelerator.services import create_autonomous_capture_session
    from ki_radar.accounts.models import BusinessUnit

    demo = BusinessUnit.objects.create(
        name="Manipulierte Demo-Einheit",
        catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
    )

    with pytest.raises(ValidationError, match="freigegebenen Organisationskatalog"):
        create_autonomous_capture_session(
            actor=owner,
            problem_statement="Kundenanfragen benötigen zu viele manuelle Schritte.",
            business_unit_id=demo.pk,
        )


@pytest.mark.django_db
def test_existing_legacy_assignment_remains_selectable_only_on_its_own_edit_form():
    from ki_radar.accounts.models import BusinessUnit
    from ki_radar.use_cases.idea_forms import IdeaCandidateForm
    from ki_radar.use_cases.idea_models import IdeaCandidate

    legacy = BusinessUnit.objects.create(
        name="Historische Zuordnung",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    idea = IdeaCandidate.objects.create(
        title="Historischer Eintrag",
        description="Bestehende Zuordnung darf nicht still verschwinden.",
        business_unit=legacy,
    )

    form = IdeaCandidateForm(instance=idea)
    ids = set(form.fields["business_unit"].queryset.values_list("pk", flat=True))
    assert legacy.pk in ids

    create_form = IdeaCandidateForm()
    create_ids = set(create_form.fields["business_unit"].queryset.values_list("pk", flat=True))
    assert legacy.pk not in create_ids


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scope,active", [("demo_test", True), ("legacy", True), ("productive", False)]
)
def test_assignment_forms_reject_manipulated_catalog_ids(scope, active, owner):
    from ki_radar.accelerator.architect_forms import AutonomousDiscoveryStartForm
    from ki_radar.accounts.models import BusinessUnit
    from ki_radar.architecture.forms import ValueStreamForm
    from ki_radar.use_cases.forms import UseCaseForm
    from ki_radar.use_cases.idea_forms import IdeaCandidateForm
    from ki_radar.use_cases.intake import ProblemStepForm

    unit = BusinessUnit.objects.create(
        name="Unzulässige Zuordnung", catalog_scope=scope, is_active=active
    )
    for form_class in [
        AutonomousDiscoveryStartForm,
        ValueStreamForm,
        UseCaseForm,
        IdeaCandidateForm,
        ProblemStepForm,
    ]:
        form = form_class(data={"business_unit": unit.pk})
        assert not form.is_valid()
        assert "business_unit" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scope,active", [("demo_test", True), ("legacy", True), ("productive", False)]
)
def test_edit_preserves_current_unit_but_rejects_other_nonproductive_unit(scope, active, owner):
    from ki_radar.accounts.models import BusinessUnit
    from ki_radar.architecture.forms import ValueStreamForm
    from ki_radar.architecture.models import ValueStream
    from ki_radar.use_cases.forms import UseCaseForm
    from ki_radar.use_cases.idea_forms import IdeaCandidateForm
    from ki_radar.use_cases.idea_models import IdeaCandidate
    from ki_radar.use_cases.models import UseCase

    current = BusinessUnit.objects.create(
        name="Bestehende Zuordnung", catalog_scope=scope, is_active=active
    )
    other = BusinessUnit.objects.create(
        name="Andere Altzuordnung", catalog_scope=scope, is_active=active
    )
    idea = IdeaCandidate.objects.create(
        title="Historisch", description="Unverändert", business_unit=current
    )
    use_case = UseCase.objects.create(
        title="Historisch", business_unit=current, business_owner=owner, submitter=owner
    )
    stream = ValueStream.objects.create(name="Historisch", business_unit=current, owner=owner)
    for form_class, instance in [
        (IdeaCandidateForm, idea),
        (UseCaseForm, use_case),
        (ValueStreamForm, stream),
    ]:
        form = form_class(data={"business_unit": current.pk}, instance=instance)
        form.is_valid()
        assert "business_unit" not in form.errors
        assert form.cleaned_data["business_unit"] == current
        form = form_class(data={"business_unit": other.pk}, instance=instance)
        assert not form.is_valid()
        assert "business_unit" in form.errors
        instance.refresh_from_db()
        assert instance.business_unit_id == current.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scope,active", [("demo_test", True), ("legacy", True), ("productive", False)]
)
def test_intake_revalidates_catalog_at_final_submission(client, owner, scope, active):
    from django.urls import reverse
    from test_guided_intake_hard_gates import set_intake_session

    from ki_radar.use_cases.models import UseCase

    set_intake_session(client, owner.business_unit, owner)
    owner.business_unit.catalog_scope = scope
    owner.business_unit.is_active = active
    owner.business_unit.save()
    client.force_login(owner)
    response = client.post(reverse("use_cases:intake_step", kwargs={"step": 6}))
    assert response.status_code == 302
    assert response.url == reverse("use_cases:create")
    assert not UseCase.objects.exists()


@pytest.mark.django_db
def test_admin_assignment_forms_use_catalog_and_preserve_history(rf, owner):
    from django.contrib import admin
    from django.core.exceptions import ValidationError

    from ki_radar.accounts.models import BusinessUnit, User
    from ki_radar.architecture.models import ValueStream
    from ki_radar.use_cases.models import UseCase

    legacy = BusinessUnit.objects.create(name="Admin-Altbestand", catalog_scope="legacy")
    demo = BusinessUnit.objects.create(name="Admin-Demo", catalog_scope="demo_test")
    request = rf.get("/admin/")
    request.user = User.objects.create_superuser(username="catalog-admin", password="x")
    objects = [
        owner,
        ValueStream.objects.create(name="Alt", business_unit=legacy, owner=owner),
        UseCase.objects.create(
            title="Alt", business_unit=legacy, business_owner=owner, submitter=owner
        ),
    ]
    owner.business_unit = legacy
    owner.save()
    for obj in objects:
        model_admin = admin.site._registry[type(obj)]
        create_form = model_admin.get_form(request)
        ids = set(create_form.base_fields["business_unit"].queryset.values_list("pk", flat=True))
        assert legacy.pk not in ids
        assert demo.pk not in ids
        edit_form = model_admin.get_form(request, obj)
        field = edit_form.base_fields["business_unit"]
        assert field.clean(legacy.pk) == legacy
        with pytest.raises(ValidationError):
            field.clean(demo.pk)


@pytest.mark.django_db
def test_frozen_discovery_retains_legacy_scope_after_catalog_change(owner):
    from ki_radar.accelerator.discovery_context import active_discovery_business_unit
    from ki_radar.accelerator.services import create_autonomous_capture_session

    session = create_autonomous_capture_session(
        actor=owner, problem_statement="Historische Untersuchung"
    )
    frozen = session.answers["business_unit"].copy()
    owner.business_unit.catalog_scope = "legacy"
    owner.business_unit.save()
    assert active_discovery_business_unit(session) == owner.business_unit
    session.refresh_from_db()
    assert session.answers["business_unit"] == frozen


@pytest.mark.django_db(transaction=True)
def test_catalog_migration_preserves_existing_references():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.utils import timezone

    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    before = [node for node in latest if node[0] != "accounts"] + [("accounts", "0001_initial")]
    executor.migrate(before)
    try:
        apps = executor.loader.project_state(before).apps
        Unit = apps.get_model("accounts", "BusinessUnit")
        User = apps.get_model("accounts", "User")
        Idea = apps.get_model("use_cases", "IdeaCandidate")
        Stream = apps.get_model("architecture", "ValueStream")
        Case = apps.get_model("use_cases", "UseCase")
        Session = apps.get_model("accelerator", "CaptureSession")
        Unit.objects.all().delete()
        unit = Unit.objects.create(name="Ungeprüfte Bestandsdaten")
        confirmed = Unit.objects.create(name="IT & Digitalisierung", is_active=False)
        user = User.objects.create(username="migration-owner", business_unit=unit)
        idea = Idea.objects.create(title="Alt", description="Alt", business_unit=unit)
        stream = Stream.objects.create(name="Alt", business_unit=unit, owner=user)
        case = Case.objects.create(
            title="Alt", business_unit=unit, business_owner=user, submitter=user
        )
        frozen = {"id": unit.pk, "name": unit.name}
        session = Session.objects.create(
            owner=user,
            capture_type="value_stream",
            answers={"business_unit": frozen},
            expires_at=timezone.now(),
        )
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        apps = executor.loader.project_state(latest).apps
        Unit = apps.get_model("accounts", "BusinessUnit")
        assert Unit.objects.get(pk=unit.pk).catalog_scope == "legacy"
        assert Unit.objects.get(pk=confirmed.pk).catalog_scope == "productive"
        assert Unit.objects.get(pk=confirmed.pk).is_active
        assert (
            set(Unit.objects.filter(catalog_scope="productive").values_list("name", flat=True))
            == EXPECTED_PRODUCTIVE_UNITS
        )
        for model, obj in [
            ("accounts.User", user),
            ("use_cases.IdeaCandidate", idea),
            ("architecture.ValueStream", stream),
            ("use_cases.UseCase", case),
        ]:
            assert apps.get_model(model).objects.get(pk=obj.pk).business_unit_id == unit.pk
        assert (
            apps.get_model("accelerator", "CaptureSession")
            .objects.get(pk=session.pk)
            .answers["business_unit"]
            == frozen
        )
    finally:
        MigrationExecutor(connection).migrate(latest)
