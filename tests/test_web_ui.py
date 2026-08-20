from fastapi.testclient import TestClient

from controlcheck.api import create_app


def test_web_ui_root_endpoint():
    app = create_app()
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ControlCheck" in response.text
    assert "AI Audit Copilot" in response.text


def test_web_ui_static_assets():
    app = create_app()
    client = TestClient(app)

    css_res = client.get("/static/css/app.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers["content-type"]

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers["content-type"] or "text/plain" in js_res.headers["content-type"]
