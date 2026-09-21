from django.urls import reverse

from ki_radar.accounts.views import RadarLoginView


def test_demo_portal_requires_authentication(client):
    response = client.get(reverse("demo-portal"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_login_view_uses_demo_portal_as_default_target():
    assert RadarLoginView.next_page == "demo-portal"


def test_authenticated_user_sees_three_demo_entries(client, reader):
    client.force_login(reader)

    response = client.get(reverse("demo-portal"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Projektbeispiel: Angebotsvergleich im Einkauf" in body
    assert "Use Case: Gesprächsmuster &amp; Vertriebswirkung" in body
    assert "ohne individuelle Personenbewertung" in body
    assert "Anwendung: KI-Use-Case-Radar" in body
    assert f'href="{reverse("case-procurement")}"' in body
    assert f'href="{reverse("case-sales-conversation")}"' in body
    assert f'href="{reverse("reporting:dashboard")}"' in body


def test_existing_dashboard_url_is_preserved(client, reader):
    client.force_login(reader)

    assert reverse("reporting:dashboard") == "/"
    assert client.get(reverse("reporting:dashboard")).status_code == 200


def test_case_routes_are_protected_and_procurement_is_two_scene_presentation(client, reader):
    for route_name in ("case-procurement", "case-sales-conversation"):
        anonymous_response = client.get(reverse(route_name))
        assert anonymous_response.status_code == 302
        assert anonymous_response.url.startswith(reverse("accounts:login"))

    client.force_login(reader)
    response = client.get(reverse("case-procurement"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "In Vorbereitung" not in body
    assert body.count('class="procurement-slide"') == 2
    assert 'id="procurement-slide-1"' in body
    assert 'id="procurement-slide-2"' in body
    assert "case-procurement.css" in body
    assert "case-procurement.js" in body
    assert "erst standardisieren, dann KI einsetzen" in body
    assert "KI gezielt einsetzen" in body
    assert "AI gezielt einsetzen" not in body
    assert "5,0 → 2,8 Tage" in body
    assert "\u201344 %" in body
    assert "\u201370 %" in body
    assert "KI bereitet vor, der Einkauf entscheidet." in body


def test_sales_conversation_case_is_four_slide_web_presentation(client, reader):
    client.force_login(reader)

    response = client.get(reverse("case-sales-conversation"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "In Vorbereitung" not in body
    for slide_number in range(1, 5):
        assert f'id="sci-slide-{slide_number}"' in body

    assert (
        "Welche Merkmale eines Beratungsgesprächs stehen mit einer Buchung in Zusammenhang?" in body
    )
    assert "wird \u2013 oder nicht?" not in body
    assert "Der Case steht und fällt mit der Datenbasis." in body
    assert "Schlanker Pilot statt KI-Plattform." in body
    assert "Datenpipeline, nicht das Gesamtsystem." in body
    assert "Investieren erst nach drei Belegen." in body
    assert "Gesprächsmuster &amp; Vertriebswirkung" in body
    assert "Sales Conversation Intelligence" not in body
    assert body.count('class="sci-no">Nein</div>') == 2
    assert "Pilotkanal mit ausdrücklicher Einwilligung" in body
    assert "Opt-in-Pilotkanal" not in body
    assert "Gate 1 negativ?" in body
    assert "2-wöchiger Data-&amp;-Legal-Feasibility-Check" in body
    assert "6%" not in body
    assert "14%" not in body


def test_sales_conversation_case_matches_management_reference_structure(client, reader):
    client.force_login(reader)

    body = client.get(reverse("case-sales-conversation")).content.decode()

    assert body.count('class="sci-slide-shell"') == 4
    assert 'class="sci-flow"' in body
    assert 'class="sci-data-graph"' in body
    assert 'class="sci-architecture"' in body
    assert 'class="sci-gates"' in body
    assert "sales-conversation-viewer.css" in body
    assert "sales-conversation-viewer.js" in body
    assert "sci-deck-nav" not in body
    assert "sci-process-line" not in body
    assert "sci-pipeline" not in body
    assert "sci-gate-line" not in body


def test_authenticated_shell_exposes_small_home_control(client, reader):
    client.force_login(reader)

    response = client.get(reverse("reporting:dashboard"))
    body = response.content.decode()

    assert f'href="{reverse("demo-portal")}"' in body
    assert 'aria-label="Zur Startseite"' in body
    assert "⌂" in body
