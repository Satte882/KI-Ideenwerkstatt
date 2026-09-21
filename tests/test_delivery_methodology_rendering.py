import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_methodology_page_renders_markdown_structure(client, owner):
    client.force_login(owner)

    response = client.get(reverse("delivery:methodology_reference"))

    assert response.status_code == 200
    content = response.content.decode()
    assert '<article class="app-card card-body methodology-document">' in content
    assert "<h1>Methodische Referenz des Delivery-Handover</h1>" in content
    assert "<h2>Mapping der sieben Delivery-Sektionen</h2>" in content
    assert '<div class="methodology-table-wrap">' in content
    assert "<ul>" in content
    assert "<ol>" in content
    assert "<blockquote>" in content
    assert "<pre><code" in content
    assert "text-preline" not in content
    assert "Evaluation, Qualitätsmetriken und Stichproben" in content
    assert "Confidence und Unsicherheit nach Output-Typ" in content
    assert "Ende-zu-Ende-Latenz, Timeouts und Retries" in content
    assert "Audit und Retention" in content
    assert "Beispiele für belastbare Delivery-Angaben" in content
