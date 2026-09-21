from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

METHODOLOGY_PATH = Path(settings.BASE_DIR) / "docs" / "VALUE_STREAM_METHODOLOGY.md"
METHODOLOGY_DOWNLOAD_NAME = "KI-Radar_Value-Stream-Methodik_v1.0.md"


@login_required
def value_stream_methodology_download(request):
    methodology = METHODOLOGY_PATH.read_text(encoding="utf-8")
    response = HttpResponse(methodology, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{METHODOLOGY_DOWNLOAD_NAME}"'
    return response
