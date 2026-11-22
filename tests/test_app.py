import tempfile
import unittest
from pathlib import Path

from app import create_app


class JobBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "DATABASE": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

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
        self.assertIn("Ya existe una cuenta".encode(), duplicate.data)
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
        self.assertIn("Ya te postulaste".encode(), duplicate.data)
        dashboard = self.client.get("/mi-cuenta")
        self.assertIn("Mis postulaciones".encode(), dashboard.data)

    def test_csrf_required_for_post(self):
        response = self.client.post("/registro", data={"name": "Ana"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
