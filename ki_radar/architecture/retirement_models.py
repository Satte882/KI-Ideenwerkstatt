from django.conf import settings
from django.db import models
from django.utils import timezone


class SolutionOptionRetirement(models.Model):
    option = models.OneToOneField(
        "architecture.SolutionOption",
        on_delete=models.PROTECT,
        related_name="retirement",
    )
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="retired_solution_options",
    )
    retired_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        app_label = "architecture"
        ordering = ["-retired_at"]

    def __str__(self) -> str:
        return f"Nicht weiterverfolgt: {self.option}"
