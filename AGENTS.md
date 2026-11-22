# AGENTS.md
## Proyecto
Aplicación web "Impulso" para la publicación de ofertas de empleo y postulación de candidatos.
Permite el registro de usuarios, inicio de sesión, creación de ofertas laborales y postulación a vacantes.
## Stack
- Framework: Flask
- Base de datos: SQLite vía Flask-SQLAlchemy
- Formularios y Autenticación: Flask-Login, Flask-WTF / WTForms, Jinja2
- Variables de entorno: python-dotenv
- Pruebas y Calidad: pytest, httpx, ruff, pre-commit
## Comandos
- Instalar: python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt
- Ejecutar: python app.py
- Pruebas: python -m pytest -v
- Estilo: ruff check .
## Estructura
- app.py: Fábrica de la aplicación, definición de rutas HTTP y endpoints principales.
- servicios.py: Lógica de negocio, modelos de base de datos y validaciones.
- requirements.txt: Dependencias del proyecto.
- .env.example: Plantilla de variables de entorno (sin valores reales).
- .gitignore: Excluye .venv/, cachés, .env e instance/*.db.
- templates/: Plantillas HTML (Jinja2) para la interfaz de usuario.
- static/: Hojas de estilo CSS y recursos estáticos.
- tests/: Pruebas automatizadas (test_humo.py, test_app.py, test_fallos.py).
## Qué no hacer
- No modificar las pruebas para que pasen.
- No escribir claves ni secretos en el código.
- No instalar dependencias sin explicar su propósito.
- No hacer commit ni push directamente.
## Lecciones aprendidas
- Extraer siempre todas las claves y tokens a variables de entorno cargadas con python-dotenv.
- Separar la lógica de negocio y acceso a datos en servicios.py desde la fase inicial.
- Validar rigurosamente los campos en el servidor antes de guardarlos en la base de datos.
- Verificar la propiedad del recurso antes de autorizar modificaciones o eliminaciones.
