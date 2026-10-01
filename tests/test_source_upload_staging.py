from pathlib import Path


def test_source_upload_staging_accumulates_lists_and_removes_files():
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "js" / "source-upload-staging.js").read_text(encoding="utf-8")

    assert "new DataTransfer()" in script
    assert "transfer.items.add(file)" in script
    assert "input.files = transfer.files" in script
    assert "data-file-staging-remove" in script
    assert "Datei(en) für den Quellenstand ausgewählt" in script


def test_source_upload_staging_is_loaded_globally():
    root = Path(__file__).resolve().parents[1]
    base = (root / "templates" / "base.html").read_text(encoding="utf-8")

    assert "js/source-upload-staging.js" in base
