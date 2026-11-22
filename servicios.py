import sqlite3

from flask import current_app, g
from werkzeug.security import check_password_hash, generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    job_type TEXT NOT NULL,
    salary TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, user_id)
);
"""

JOB_TYPES = ("Tiempo completo", "Medio tiempo", "Remoto", "Contrato", "Prácticas")


class ServiceError(Exception):
    """Error de validación o regla de negocio."""


class JobNotFound(ServiceError):
    """La oferta solicitada no existe o no pertenece al usuario."""


class OwnJobApplication(ServiceError):
    """El autor de una oferta intenta postularse a ella."""


class DuplicateApplication(ServiceError):
    """El usuario ya se postuló a la oferta."""


def init_db(database_path):
    db = sqlite3.connect(database_path)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
    finally:
        db.close()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_user_by_id(user_id):
    return get_db().execute(
        "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def register_user(name, email, password):
    name = name.strip()
    email = email.strip().lower()
    if not name or len(name) > 80:
        raise ServiceError("Escribe tu nombre (máximo 80 caracteres).")
    if not email or len(email) > 254 or "@" not in email:
        raise ServiceError("Escribe un correo electrónico válido.")
    if len(password) < 8:
        raise ServiceError("La contraseña debe tener al menos 8 caracteres.")

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        raise ServiceError("Ya existe una cuenta con ese correo.") from error
    return get_user_by_id(cursor.lastrowid)


def authenticate_user(email, password):
    user = get_db().execute(
        "SELECT id, password_hash FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return None
    return user


def list_jobs(search=""):
    query = """
        SELECT jobs.*, users.name AS poster_name
        FROM jobs JOIN users ON users.id = jobs.user_id
    """
    params = ()
    search = search.strip()
    if search:
        query += """
            WHERE jobs.title LIKE ? OR jobs.company LIKE ?
            OR jobs.location LIKE ? OR jobs.description LIKE ?
        """
        term = f"%{search}%"
        params = (term, term, term, term)
    query += " ORDER BY jobs.created_at DESC, jobs.id DESC"
    return get_db().execute(query, params).fetchall()


def create_job(user_id, title, company, location, job_type, salary, description):
    fields = {
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "job_type": job_type.strip(),
        "salary": salary.strip(),
        "description": description.strip(),
    }
    limits = {"title": 120, "company": 100, "location": 100, "salary": 80}
    if any(
        not fields[key]
        for key in ("title", "company", "location", "job_type", "description")
    ):
        raise ServiceError("Completa todos los campos obligatorios.")
    if any(len(fields[key]) > limit for key, limit in limits.items()):
        raise ServiceError("Revisa la longitud de los campos.")
    if fields["job_type"] not in JOB_TYPES:
        raise ServiceError("Selecciona un tipo de empleo válido.")
    if len(fields["description"]) > 5000:
        raise ServiceError("La descripción no puede superar los 5000 caracteres.")

    cursor = get_db().execute(
        """INSERT INTO jobs
        (user_id, title, company, location, job_type, salary, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            fields["title"],
            fields["company"],
            fields["location"],
            fields["job_type"],
            fields["salary"],
            fields["description"],
        ),
    )
    get_db().commit()
    return cursor.lastrowid


def get_job(job_id):
    return get_db().execute(
        """SELECT jobs.*, users.name AS poster_name FROM jobs
        JOIN users ON users.id = jobs.user_id WHERE jobs.id = ?""",
        (job_id,),
    ).fetchone()


def has_applied(job_id, user_id):
    return get_db().execute(
        "SELECT 1 FROM applications WHERE job_id = ? AND user_id = ?",
        (job_id, user_id),
    ).fetchone() is not None


def apply_to_job(job_id, user_id, message):
    db = get_db()
    job = db.execute("SELECT user_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        raise JobNotFound()
    if job["user_id"] == user_id:
        raise OwnJobApplication()
    message = message.strip()
    if len(message) > 1000:
        raise ServiceError("El mensaje no puede superar los 1000 caracteres.")
    try:
        db.execute(
            "INSERT INTO applications (job_id, user_id, message) VALUES (?, ?, ?)",
            (job_id, user_id, message),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        raise DuplicateApplication() from error


def get_dashboard_data(user_id):
    db = get_db()
    jobs = db.execute(
        """SELECT jobs.*,
            (SELECT COUNT(*) FROM applications WHERE applications.job_id = jobs.id) AS applicant_count
        FROM jobs WHERE user_id = ? ORDER BY created_at DESC""",
        (user_id,),
    ).fetchall()
    applications = db.execute(
        """SELECT applications.created_at AS applied_at, jobs.*
        FROM applications JOIN jobs ON jobs.id = applications.job_id
        WHERE applications.user_id = ? ORDER BY applications.created_at DESC""",
        (user_id,),
    ).fetchall()
    return jobs, applications


def get_owned_job(job_id, user_id):
    return get_db().execute(
        "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
        (job_id, user_id),
    ).fetchone()


def delete_owned_job(job_id, user_id):
    db = get_db()
    cursor = db.execute(
        "DELETE FROM jobs WHERE id = ? AND user_id = ?",
        (job_id, user_id),
    )
    db.commit()
    return cursor.rowcount == 1


def list_applicants(job_id):
    return get_db().execute(
        """SELECT users.name, users.email, applications.message, applications.created_at
        FROM applications JOIN users ON users.id = applications.user_id
        WHERE applications.job_id = ? ORDER BY applications.created_at DESC""",
        (job_id,),
    ).fetchall()
