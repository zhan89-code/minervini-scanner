"""WSGI entry point for PythonAnywhere's free tier, which only serves WSGI
apps directly -- FastAPI is ASGI. PythonAnywhere's "Web" tab wants a
module-level `application` callable. Set this file as the WSGI
configuration file's import target (see DEPLOY_PYTHONANYWHERE.md).

Purpose-built minimal ASGI->WSGI adapter instead of a library like a2wsgi:
every route handler in this app is a plain sync function (no real async
I/O), so there's no need for a persistent background event-loop thread
shared across requests -- that threading model is a known bad fit for
PythonAnywhere's uWSGI hosting (requests hang indefinitely rather than
erroring). Each request here just runs a fresh, self-contained
`asyncio.run()` call instead.

Env vars (ALLOWED_ORIGINS etc.) are set here directly rather than via a
.env file, since PythonAnywhere's free tier has no env-var UI -- edit the
values below after cloning the repo there.
"""
import asyncio
import os
from http import HTTPStatus

os.environ.setdefault("ALLOWED_ORIGINS", "https://your-frontend.vercel.app")

from api.main import app as _fastapi_app  # noqa: E402


async def _call_asgi(scope, body: bytes):
    response = {"status": None, "headers": []}
    body_chunks: list[bytes] = []
    sent_body = False

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            response["headers"] = message["headers"]
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    await _fastapi_app(scope, receive, send)
    return response, b"".join(body_chunks)


def application(environ, start_response):
    headers = [
        (
            (key[5:] if key.startswith("HTTP_") else key).lower().replace("_", "-"),
            value,
        )
        for key, value in environ.items()
        if key.startswith("HTTP_") or key in ("CONTENT_TYPE", "CONTENT_LENGTH")
    ]
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(content_length) if content_length else b""

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.5"},
        "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/")[-1],
        "method": environ["REQUEST_METHOD"],
        "scheme": environ.get("wsgi.url_scheme", "https"),
        "path": environ.get("PATH_INFO", ""),
        "root_path": "",
        "query_string": environ.get("QUERY_STRING", "").encode("latin1"),
        "headers": [(k.encode("latin1"), v.encode("latin1")) for k, v in headers],
        "server": (environ.get("SERVER_NAME", ""), int(environ.get("SERVER_PORT") or 80)),
    }

    response, body_bytes = asyncio.run(_call_asgi(scope, body))

    status_line = f"{response['status']} {HTTPStatus(response['status']).phrase}"
    response_headers = [
        (name.decode("latin1"), value.decode("latin1")) for name, value in response["headers"]
    ]
    start_response(status_line, response_headers)
    return [body_bytes]
