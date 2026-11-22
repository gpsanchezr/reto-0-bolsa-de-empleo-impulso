# Impulso

Aplicación web en español para publicar ofertas de empleo y postularse con una cuenta.

## Requisitos

- Python 3.10 o posterior
- Flask (`pip install -r requirements.txt`)

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "from pathlib import Path; import secrets; Path('.env').write_text('SECRET_KEY=' + secrets.token_urlsafe(32) + '\n', encoding='utf-8')"
python app.py
```

El comando genera un `.env` local con una clave aleatoria; también puedes copiar `.env.example` a `.env` y sustituir el valor de ejemplo. No compartas ni subas `.env`. Abre http://127.0.0.1:5000. La base SQLite se crea automáticamente en `instance\bolsa.db`.

## Funcionalidades

- Registro e inicio de sesión con contraseñas protegidas mediante hash.
- Listado y búsqueda de ofertas por puesto, empresa, descripción o ubicación.
- Publicación de empleos por usuarios registrados.
- Postulaciones con mensaje opcional y prevención de duplicados.
- Panel personal con las postulaciones enviadas, ofertas publicadas y acceso a los postulantes.
- Protección CSRF para formularios.

Para ejecutar las pruebas: `python -m unittest discover -s tests`.
