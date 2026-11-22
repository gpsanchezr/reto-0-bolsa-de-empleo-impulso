import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

from app import create_app


class JobBoardTests(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": os.environ.get("SECRET_KEY"),
                "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_secret_key_is_required(self):
        with patch.dict(os.environ, {"SECRET_KEY": ""}), self.assertRaisesRegex(
            RuntimeError, "SECRET_KEY"
        ):
            create_app()

    def post_form(self, path, data):
        with self.client.session_transaction() as session:
            token = session.get("csrf_token")
        if token is None:
            self.client.get("/")
            with self.client.session_transaction() as session:
                token = session["csrf_token"]
        return self.client.post(path, data={**data, "csrf_token": token}, follow_redirects=True)

    def register(self, name, email):
        return self.post_form(
            "/registro",
            {"name": name, "email": email, "password": "contraseña-segura"},
        )

    def create_job(self):
        return self.post_form(
            "/publicar",
            {
                "title": "Diseñador/a de producto",
                "company": "Estudio Verde",
                "location": "Remoto",
                "job_type": "Remoto",
                "salary": "$40,000",
                "description": "Diseña experiencias digitales centradas en las personas.",
            },
        )

    def test_registration_login_and_duplicate_email(self):
        response = self.register("Ana López", "ana@example.com")
        self.assertIn("¡Cuenta creada!".encode(), response.data)
        duplicate = self.post_form(
            "/registro",
            {"name": "Ana", "email": "ana@example.com", "password": "contraseña-segura"},
        )
        self.assertIn(b"Ya existe una cuenta", duplicate.data)
        self.post_form("/cerrar-sesion", {})
        login = self.post_form(
            "/iniciar-sesion", {"email": "ana@example.com", "password": "contraseña-segura"}
        )
        self.assertIn("Qué bueno verte".encode(), login.data)

    def test_job_posting_application_and_duplicate_prevention(self):
        self.register("Ana", "ana@example.com")
        response = self.create_job()
        self.assertIn("Diseñador/a de producto".encode(), response.data)
        self.post_form("/cerrar-sesion", {})
        self.register("Luis", "luis@example.com")
        with self.app.app_context():
            import sqlite3

            connection = sqlite3.connect(self.app.config["DATABASE"])
            job_id = connection.execute("SELECT id FROM jobs").fetchone()[0]
            connection.close()
        path = f"/empleos/{job_id}/postular"
        first = self.post_form(path, {"message": "Me interesa mucho este puesto."})
        self.assertIn("Postulación enviada".encode(), first.data)
        duplicate = self.post_form(path, {"message": "Intento duplicado."})
        self.assertIn(b"Ya te postulaste", duplicate.data)
        dashboard = self.client.get("/mi-cuenta")
        self.assertIn(b"Mis postulaciones", dashboard.data)

    def test_application_rejects_message_over_1000_chars(self):
        self.register("Ana", "ana@example.com")
        self.create_job()
        with self.app.app_context():
            import sqlite3

            connection = sqlite3.connect(self.app.config["DATABASE"])
            job_id = connection.execute("SELECT id FROM jobs").fetchone()[0]
            connection.close()

        self.post_form("/cerrar-sesion", {})
        self.register("Luis", "luis@example.com")
        response = self.post_form(
            f"/empleos/{job_id}/postular", {"message": "x" * 1001}
        )
        self.assertIn(b"El mensaje no puede superar los 1000 caracteres.", response.data)

        with self.app.app_context():
            connection = sqlite3.connect(self.app.config["DATABASE"])
            application_count = connection.execute(
                "SELECT COUNT(*) FROM applications"
            ).fetchone()[0]
            connection.close()
        self.assertEqual(application_count, 0)

    def test_application_message_is_optional_and_accepts_1000_chars(self):
        self.register("Ana", "ana@example.com")
        self.create_job()
        self.post_form(
            "/publicar",
            {
                "title": "Investigador/a de experiencia",
                "company": "Estudio Verde",
                "location": "Remoto",
                "job_type": "Tiempo completo",
                "salary": "",
                "description": "Investiga las necesidades de los usuarios.",
            },
        )
        with self.app.app_context():
            import sqlite3

            connection = sqlite3.connect(self.app.config["DATABASE"])
            job_ids = [
                row[0]
                for row in connection.execute("SELECT id FROM jobs ORDER BY id")
            ]
            connection.close()

        self.post_form("/cerrar-sesion", {})
        self.register("Luis", "luis@example.com")
        empty_message = self.post_form(
            f"/empleos/{job_ids[0]}/postular", {"message": "   "}
        )
        self.assertIn(b"Postulaci\xc3\xb3n enviada", empty_message.data)
        max_message = "x" * 1000
        max_message_response = self.post_form(
            f"/empleos/{job_ids[1]}/postular", {"message": max_message}
        )
        self.assertIn(b"Postulaci\xc3\xb3n enviada", max_message_response.data)

        with self.app.app_context():
            connection = sqlite3.connect(self.app.config["DATABASE"])
            stored_messages = connection.execute(
                "SELECT job_id, message FROM applications ORDER BY job_id"
            ).fetchall()
            connection.close()
        self.assertEqual(
            stored_messages,
            [(job_ids[0], ""), (job_ids[1], max_message)],
        )

    def test_csrf_required_for_post(self):
        response = self.client.post("/registro", data={"name": "Ana"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
