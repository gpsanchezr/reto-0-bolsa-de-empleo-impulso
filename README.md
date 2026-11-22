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
$env:SECRET_KEY = "reemplaza-por-una-clave-aleatoria"
python app.py
```

Abre http://127.0.0.1:5000. La base SQLite se crea automáticamente en `instance\bolsa.db`.

## Funcionalidades

- Registro e inicio de sesión con contraseñas protegidas mediante hash.
- Listado y búsqueda de ofertas por puesto, empresa, descripción o ubicación.
- Publicación de empleos por usuarios registrados.
- Postulaciones con mensaje opcional y prevención de duplicados.
- Panel personal con las postulaciones enviadas, ofertas publicadas y acceso a los postulantes.
- Protección CSRF para formularios.

Para ejecutar las pruebas: `python -m unittest discover -s tests`.
