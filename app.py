import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
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


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-secret"),
        DATABASE=os.path.join(app.instance_path, "bolsa.db"),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.executescript(SCHEMA)
        db.close()

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(current_app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            submitted = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not secrets.compare_digest(submitted, expected):
                abort(400, description="La sesión del formulario expiró. Inténtalo de nuevo.")

    @app.context_processor
    def template_context():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        user = None
        if session.get("user_id"):
            user = get_db().execute(
                "SELECT id, name, email FROM users WHERE id = ?", (session["user_id"],)
            ).fetchone()
        return {"csrf_token": session["csrf_token"], "current_user": user}

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Inicia sesión para continuar.", "info")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    @app.route("/")
    def index():
        search = request.args.get("q", "").strip()
        query = """
            SELECT jobs.*, users.name AS poster_name
            FROM jobs JOIN users ON users.id = jobs.user_id
        """
        params = ()
        if search:
            query += """
                WHERE jobs.title LIKE ? OR jobs.company LIKE ?
                OR jobs.location LIKE ? OR jobs.description LIKE ?
            """
            term = f"%{search}%"
            params = (term, term, term, term)
        query += " ORDER BY jobs.created_at DESC, jobs.id DESC"
        jobs = get_db().execute(query, params).fetchall()
        return render_template("index.html", jobs=jobs, search=search)

    @app.route("/registro", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            error = None
            if not name or len(name) > 80:
                error = "Escribe tu nombre (máximo 80 caracteres)."
            elif not email or len(email) > 254 or "@" not in email:
                error = "Escribe un correo electrónico válido."
            elif len(password) < 8:
                error = "La contraseña debe tener al menos 8 caracteres."
            if error:
                flash(error, "error")
            else:
                db = get_db()
                try:
                    cursor = db.execute(
                        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
                    db.commit()
                except sqlite3.IntegrityError:
                    flash("Ya existe una cuenta con ese correo.", "error")
                else:
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    flash("¡Cuenta creada! Ya puedes explorar las ofertas.", "success")
                    return redirect(url_for("index"))
        return render_template("register.html")

    @app.route("/iniciar-sesion", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT id, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("El correo o la contraseña no son correctos.", "error")
            else:
                destination = request.args.get("next", "")
                if not destination.startswith("/") or destination.startswith("//"):
                    destination = url_for("index")
                session.clear()
                session["user_id"] = user["id"]
                flash("¡Qué bueno verte de nuevo!", "success")
                return redirect(destination)
        return render_template("login.html")

    @app.post("/cerrar-sesion")
    @login_required
    def logout():
        session.clear()
        flash("Has cerrado sesión.", "info")
        return redirect(url_for("index"))

    @app.route("/publicar", methods=["GET", "POST"])
    @login_required
    def create_job():
        if request.method == "POST":
            fields = {
                "title": request.form.get("title", "").strip(),
                "company": request.form.get("company", "").strip(),
                "location": request.form.get("location", "").strip(),
                "job_type": request.form.get("job_type", "").strip(),
                "salary": request.form.get("salary", "").strip(),
                "description": request.form.get("description", "").strip(),
            }
            limits = {"title": 120, "company": 100, "location": 100, "salary": 80}
            if any(not fields[key] for key in ("title", "company", "location", "job_type", "description")):
                flash("Completa todos los campos obligatorios.", "error")
            elif any(len(fields[key]) > limit for key, limit in limits.items()):
                flash("Revisa la longitud de los campos.", "error")
            elif fields["job_type"] not in ("Tiempo completo", "Medio tiempo", "Remoto", "Contrato", "Prácticas"):
                flash("Selecciona un tipo de empleo válido.", "error")
            elif len(fields["description"]) > 5000:
                flash("La descripción no puede superar los 5000 caracteres.", "error")
            else:
                cursor = get_db().execute(
                    """INSERT INTO jobs
                    (user_id, title, company, location, job_type, salary, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session["user_id"],
                        fields["title"],
                        fields["company"],
                        fields["location"],
                        fields["job_type"],
                        fields["salary"],
                        fields["description"],
                    ),
                )
                get_db().commit()
                flash("Tu oferta ya está publicada.", "success")
                return redirect(url_for("job_detail", job_id=cursor.lastrowid))
        return render_template("create_job.html")

    @app.route("/empleos/<int:job_id>")
    def job_detail(job_id):
        job = get_db().execute(
            """SELECT jobs.*, users.name AS poster_name FROM jobs
            JOIN users ON users.id = jobs.user_id WHERE jobs.id = ?""",
            (job_id,),
        ).fetchone()
        if job is None:
            abort(404)
        applied = False
        if session.get("user_id"):
            applied = get_db().execute(
                "SELECT 1 FROM applications WHERE job_id = ? AND user_id = ?",
                (job_id, session["user_id"]),
            ).fetchone() is not None
        return render_template("job_detail.html", job=job, applied=applied)

    @app.post("/empleos/<int:job_id>/postular")
    @login_required
    def apply(job_id):
        db = get_db()
        job = db.execute("SELECT user_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            abort(404)
        if job["user_id"] == session["user_id"]:
            flash("No puedes postularte a una oferta que publicaste.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO applications (job_id, user_id, message) VALUES (?, ?, ?)",
                    (job_id, session["user_id"], request.form.get("message", "").strip()[:1000]),
                )
                db.commit()
                flash("¡Postulación enviada! Mucha suerte.", "success")
            except sqlite3.IntegrityError:
                flash("Ya te postulaste a esta oferta.", "info")
        return redirect(url_for("job_detail", job_id=job_id))

    @app.route("/mi-cuenta")
    @login_required
    def dashboard():
        db = get_db()
        user_id = session["user_id"]
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
        return render_template("dashboard.html", jobs=jobs, applications=applications)

    @app.route("/empleos/<int:job_id>/postulantes")
    @login_required
    def applicants(job_id):
        db = get_db()
        job = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, session["user_id"]),
        ).fetchone()
        if job is None:
            abort(404)
        people = db.execute(
            """SELECT users.name, users.email, applications.message, applications.created_at
            FROM applications JOIN users ON users.id = applications.user_id
            WHERE applications.job_id = ? ORDER BY applications.created_at DESC""",
            (job_id,),
        ).fetchall()
        return render_template("applicants.html", job=job, people=people)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
