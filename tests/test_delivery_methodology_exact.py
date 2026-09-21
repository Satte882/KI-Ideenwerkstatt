import hashlib
from pathlib import Path

from django.conf import settings

EXPECTED_METHODOLOGY_SHA256 = "34a6a36a18e70751542bf5023a2cc05f71710f25fb5d9557647c06163cc2062e"
METHODOLOGY_TITLE = "# Vorgehensmodell für produktionsreife KI-Systeme".encode()


def test_embedded_methodology_matches_the_agreed_version_2_exactly():
    # Raw bytes keep the original CRLF line endings inside the versioned contract.
    document = (Path(settings.BASE_DIR) / "docs" / "DELIVERY_METHODOLOGY.md").read_bytes()
    embedded_methodology = document[document.index(METHODOLOGY_TITLE) :]

    assert hashlib.sha256(embedded_methodology).hexdigest() == EXPECTED_METHODOLOGY_SHA256
