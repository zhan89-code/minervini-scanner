"""WSGI entry point for PythonAnywhere's free tier, which only serves WSGI
apps directly -- FastAPI is ASGI, so this wraps it with a2wsgi.

PythonAnywhere's "Web" tab wants a module-level `application` callable. Set
this file as the WSGI configuration file's import target (see
DEPLOY_PYTHONANYWHERE.md).

Env vars (ALLOWED_ORIGINS etc.) are set here directly rather than via a
.env file, since PythonAnywhere's free tier has no env-var UI -- edit the
values below after cloning the repo there.
"""
import os

os.environ.setdefault("ALLOWED_ORIGINS", "https://your-frontend.vercel.app")

from a2wsgi import ASGIMiddleware  # noqa: E402  (must follow the env var setup above)

from api.main import app as _fastapi_app  # noqa: E402

application = ASGIMiddleware(_fastapi_app)
