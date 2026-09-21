from __future__ import annotations

from dataclasses import dataclass

from .role_defaults import RoleDefaultResolution

STATE_LABELS = {
    "existing": "Bestehende Zuordnung",
    "prefill": "Vorbelegung",
    "suggestion": "Vorschlag",
    "role_only": "Erforderliche Rolle",
    "open": "Offen",
    "conflict": "Konflikt",
    "ineligible": "Nicht zulässig",
}


@dataclass(frozen=True)
class RoleDefaultPresentation:
    state: str
    state_label: str
    user_id: int | None
    user_label: str
    source_kind: str
    source_id: str
    source_label: str
    reason: str

    @property
    def help_text(self) -> str:
        parts = [self.state_label]
        if self.user_label:
            parts[-1] = f"{parts[-1]}: {self.user_label}"
        if self.source_label:
            parts.append(f"Quelle: {self.source_label}")
        if self.reason:
            parts.append(self.reason)
        return " · ".join(parts)


def present_role_default(resolution: RoleDefaultResolution) -> RoleDefaultPresentation:
    return RoleDefaultPresentation(
        state=resolution.state,
        state_label=STATE_LABELS.get(resolution.state, resolution.state),
        user_id=resolution.user_id,
        user_label=resolution.user_label,
        source_kind=resolution.source_kind,
        source_id=resolution.source_id,
        source_label=resolution.source_label,
        reason=resolution.reason,
    )


def attach_role_default(field, resolution: RoleDefaultResolution) -> RoleDefaultPresentation:
    presentation = present_role_default(resolution)
    field.role_default = presentation
    existing_help = str(field.help_text or "").strip()
    provenance_help = presentation.help_text
    field.help_text = (
        f"{existing_help} {provenance_help}".strip() if existing_help else provenance_help
    )
    return presentation
