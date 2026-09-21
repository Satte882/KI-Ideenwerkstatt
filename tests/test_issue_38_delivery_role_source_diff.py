"""Focused tests for Technical-Owner source changes in Delivery Packages."""

from types import SimpleNamespace

from ki_radar.delivery.services import technical_owner_source_state


class _SectionReviews:
    def __init__(self, review):
        self.review = review

    def filter(self, **kwargs):
        assert kwargs == {"section_key": "architecture_and_data"}
        return self

    def first(self):
        return self.review


def test_technical_owner_source_state_exposes_concrete_old_and_new_values():
    snapshot_owner = SimpleNamespace(pk=7)
    current_owner = SimpleNamespace(pk=11)
    review = SimpleNamespace(
        source_manifest={
            "role_sources": {
                "technical_owner": {
                    "id": "7",
                    "value": "Technischer Owner Alt",
                    "adoption": "copied",
                }
            }
        }
    )
    package = SimpleNamespace(
        technical_owner_id=snapshot_owner.pk,
        technical_owner="Technischer Owner Alt",
        use_case=SimpleNamespace(
            technical_owner_id=current_owner.pk,
            technical_owner="Technischer Owner Neu",
        ),
        section_reviews=_SectionReviews(review),
    )

    assert technical_owner_source_state(package) == {
        "role_key": "technical_owner",
        "working_id": "7",
        "working_value": "Technischer Owner Alt",
        "snapshot_id": "7",
        "snapshot_value": "Technischer Owner Alt",
        "current_source_id": "11",
        "current_source_value": "Technischer Owner Neu",
        "source_changed": True,
        "adoption": "copied",
    }


def test_technical_owner_source_state_reports_no_change_for_same_owner():
    review = SimpleNamespace(
        source_manifest={
            "role_sources": {
                "technical_owner": {
                    "id": "7",
                    "value": "Technischer Owner",
                    "adoption": "kept",
                }
            }
        }
    )
    package = SimpleNamespace(
        technical_owner_id=7,
        technical_owner="Technischer Owner",
        use_case=SimpleNamespace(
            technical_owner_id=7,
            technical_owner="Technischer Owner",
        ),
        section_reviews=_SectionReviews(review),
    )

    state = technical_owner_source_state(package)

    assert state is not None
    assert state["source_changed"] is False
    assert state["adoption"] == "kept"


def test_technical_owner_source_state_is_absent_without_role_manifest():
    package = SimpleNamespace(
        section_reviews=_SectionReviews(SimpleNamespace(source_manifest={})),
    )

    assert technical_owner_source_state(package) is None


def test_technical_owner_source_state_handles_unassigned_owner_values():
    review = SimpleNamespace(
        source_manifest={
            "role_sources": {"technical_owner": {"id": "", "value": "", "adoption": "copied"}}
        }
    )
    package = SimpleNamespace(
        technical_owner_id=None,
        technical_owner=None,
        use_case=SimpleNamespace(technical_owner_id=None, technical_owner=None),
        section_reviews=_SectionReviews(review),
    )

    state = technical_owner_source_state(package)

    assert state is not None
    assert state["source_changed"] is False
