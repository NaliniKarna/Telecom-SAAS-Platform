from app.services.sms_renderer import render_template


def test_render_template_replaces_known_placeholders():
    rendered = render_template(
        "Hello {{name}}, your phone is {{phone}} and company is {{company}}",
        {"name": "Asha", "phone": "+9779812345678", "company": "Telecom"},
    )

    assert rendered == "Hello Asha, your phone is +9779812345678 and company is Telecom"


def test_render_template_leaves_unknown_placeholders_unchanged():
    rendered = render_template("Hello {{name}}", {"company": "Telecom"})

    assert rendered == "Hello {{name}}"
