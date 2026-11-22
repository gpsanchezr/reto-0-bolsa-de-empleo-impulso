import os
import secrets
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import servicios

load_dotenv()


def create_app(test_config=None):
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY no está definida. Configura el archivo .env.")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        DATABASE=os.path.join(app.instance_path, "bolsa.db"),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    servicios.init_db(app.config["DATABASE"])
    app.teardown_appcontext(servicios.close_db)

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
            user = servicios.get_user_by_id(session["user_id"])
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
        jobs = servicios.list_jobs(search)
        return render_template("index.html", jobs=jobs, search=search)

    @app.route("/registro", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            try:
                user = servicios.register_user(
                    request.form.get("name", ""),
                    request.form.get("email", ""),
                    request.form.get("password", ""),
                )
            except servicios.ServiceError as error:
                flash(str(error), "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("¡Cuenta creada! Ya puedes explorar las ofertas.", "success")
                return redirect(url_for("index"))
        return render_template("register.html")

    @app.route("/iniciar-sesion", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = servicios.authenticate_user(email, password)
            if user is None:
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
            try:
                job_id = servicios.create_job(
                    session["user_id"],
                    request.form.get("title", ""),
                    request.form.get("company", ""),
                    request.form.get("location", ""),
                    request.form.get("job_type", ""),
                    request.form.get("salary", ""),
                    request.form.get("description", ""),
                )
            except servicios.ServiceError as error:
                flash(str(error), "error")
            else:
                flash("Tu oferta ya está publicada.", "success")
                return redirect(url_for("job_detail", job_id=job_id))
        return render_template("create_job.html")

    @app.route("/empleos/<int:job_id>")
    def job_detail(job_id):
        job = servicios.get_job(job_id)
        if job is None:
            abort(404)
        applied = False
        if session.get("user_id"):
            applied = servicios.has_applied(job_id, session["user_id"])
        return render_template("job_detail.html", job=job, applied=applied)

    @app.post("/empleos/<int:job_id>/postular")
    @login_required
    def apply(job_id):
        try:
            servicios.apply_to_job(
                job_id,
                session["user_id"],
                request.form.get("message", ""),
            )
        except servicios.JobNotFound:
            abort(404)
        except servicios.OwnJobApplication:
            flash("No puedes postularte a una oferta que publicaste.", "error")
        except servicios.DuplicateApplication:
            flash("Ya te postulaste a esta oferta.", "info")
        else:
            flash("¡Postulación enviada! Mucha suerte.", "success")
        return redirect(url_for("job_detail", job_id=job_id))

    @app.route("/mi-cuenta")
    @login_required
    def dashboard():
        user_id = session["user_id"]
        jobs, applications = servicios.get_dashboard_data(user_id)
        return render_template("dashboard.html", jobs=jobs, applications=applications)

    @app.route("/empleos/<int:job_id>/postulantes")
    @login_required
    def applicants(job_id):
        job = servicios.get_owned_job(job_id, session["user_id"])
        if job is None:
            abort(404)
        people = servicios.list_applicants(job_id)
        return render_template("applicants.html", job=job, people=people)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
