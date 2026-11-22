import inspect
import sqlite3

from app import create_app


def test_arquitectura_modular_servicios():
    import servicios

    funciones_negocio = [
        nombre
        for nombre, objeto in inspect.getmembers(servicios, inspect.isfunction)
        if objeto.__module__ == servicios.__name__ and not nombre.startswith("_")
    ]
    modelos = [
        nombre
        for nombre, objeto in inspect.getmembers(servicios, inspect.isclass)
        if objeto.__module__ == servicios.__name__ and not nombre.startswith("_")
    ]

    assert funciones_negocio or modelos, (
        "servicios debe definir funciones de negocio o modelos propios."
    )


def test_validacion_entradas_ofertas(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test_validacion.db"),
        }
    )
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf_token = session["csrf_token"]

    registration = client.post(
        "/registro",
        data={
            "name": "Validador",
            "email": "validacion@example.com",
            "password": "contraseña-segura",
            "csrf_token": csrf_token,
        },
    )
    assert registration.status_code == 302

    def submit_job(fields):
        client.get("/publicar")
        with client.session_transaction() as session:
            token = session["csrf_token"]
        return client.post("/publicar", data={**fields, "csrf_token": token})

    empty_fields = {
        "title": "   ",
        "company": " ",
        "location": " ",
        "job_type": " ",
        "salary": "",
        "description": "   ",
    }
    empty_response = submit_job(empty_fields)
    assert empty_response.status_code == 200
    assert b"Completa todos los campos obligatorios." in empty_response.data

    long_title_fields = {
        "title": "T" * 201,
        "company": "Empresa",
        "location": "Madrid",
        "job_type": "Tiempo completo",
        "salary": "",
        "description": "Descripción del puesto",
    }
    long_title_response = submit_job(long_title_fields)
    assert long_title_response.status_code == 200
    assert b"Revisa la longitud de los campos." in long_title_response.data


def test_control_acceso_recursos_ajenos(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test_acceso.db"),
        }
    )
    client = app.test_client()

    def csrf_token():
        with client.session_transaction() as session:
            return session["csrf_token"]

    client.get("/")
    response_a = client.post(
        "/registro",
        data={
            "name": "Usuario A",
            "email": "usuario-a@example.com",
            "password": "contraseña-segura",
            "csrf_token": csrf_token(),
        },
    )
    assert response_a.status_code == 302

    client.get("/publicar")
    response_job = client.post(
        "/publicar",
        data={
            "title": "Oferta privada de A",
            "company": "Empresa A",
            "location": "Remoto",
            "job_type": "Tiempo completo",
            "salary": "",
            "description": "Descripción de la oferta de A.",
            "csrf_token": csrf_token(),
        },
    )
    assert response_job.status_code == 302

    connection = sqlite3.connect(app.config["DATABASE"])
    job_id = connection.execute("SELECT id FROM jobs").fetchone()[0]
    connection.close()

    response_logout = client.post(
        "/cerrar-sesion",
        data={"csrf_token": csrf_token()},
    )
    assert response_logout.status_code == 302

    client.get("/")
    response_b = client.post(
        "/registro",
        data={
            "name": "Usuario B",
            "email": "usuario-b@example.com",
            "password": "contraseña-segura",
            "csrf_token": csrf_token(),
        },
    )
    assert response_b.status_code == 302
    assert client.get("/mi-cuenta").status_code == 200

    response = client.get(f"/empleos/{job_id}/postulantes")
    assert response.status_code in (403, 404)

    response_delete = client.post(
        f"/empleos/{job_id}/eliminar",
        data={"csrf_token": csrf_token()},
    )
    assert response_delete.status_code in (403, 404)

    connection = sqlite3.connect(app.config["DATABASE"])
    job_count = connection.execute(
        "SELECT COUNT(*) FROM jobs WHERE id = ?", (job_id,)
    ).fetchone()[0]
    connection.close()
    assert job_count == 1
