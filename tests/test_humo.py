from app import create_app


def test_pagina_principal_responde(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test_humo.db"),
        }
    )
    response = app.test_client().get("/")

    assert response.status_code == 200
