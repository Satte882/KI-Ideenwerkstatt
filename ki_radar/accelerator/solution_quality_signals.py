from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SolutionGenerationRun, SolutionQualityRun
from .solution_critic_service import run_final_solution_critic, run_initial_solution_critic


@receiver(
    post_save,
    sender=SolutionGenerationRun,
    dispatch_uid="accelerator_schedule_initial_solution_critic_v1",
)
def schedule_initial_solution_critic(sender, instance: SolutionGenerationRun, **kwargs) -> None:
    del sender, kwargs
    if (
        instance.status != SolutionGenerationRun.Status.SUCCESS
        or not instance.preview_payload
        or not isinstance(instance.preview_payload.get("source_context"), dict)
    ):
        return

    run_id = instance.pk

    def run_critic_after_commit() -> None:
        run_initial_solution_critic(solution_generation_run_id=run_id)

    transaction.on_commit(run_critic_after_commit, robust=True)


@receiver(
    post_save,
    sender=SolutionQualityRun,
    dispatch_uid="accelerator_schedule_final_solution_critic_v1",
)
def schedule_final_solution_critic(sender, instance: SolutionQualityRun, **kwargs) -> None:
    del sender, kwargs
    if (
        instance.step_type != SolutionQualityRun.StepType.REPAIR
        or instance.status != SolutionQualityRun.Status.SUCCESS
    ):
        return

    generation_run_id = instance.solution_generation_run_id

    def run_critic_after_commit() -> None:
        run_final_solution_critic(solution_generation_run_id=generation_run_id)

    transaction.on_commit(run_critic_after_commit, robust=True)
