import logging
import os
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel


logger = logging.getLogger('uvicorn.error')

class SkipHealthcheckLog(logging.Filter):
    '''Drop healthcheck lines from the access log: nothing else calls /api/v1/ping locally.'''

    def filter(self, record):
        if not isinstance(record.args, tuple) or len(record.args) < 3:
            return True
        client, path = record.args[0], record.args[2]
        return not (str(client).startswith('127.0.0.1:') and path == '/api/v1/ping')

logging.getLogger('uvicorn.access').addFilter(SkipHealthcheckLog())

# Off by default: the docs pages need a relaxed CSP (see DOCS_CSP)
DOCS_ENABLED = os.environ.get('DOCS_ENABLED', 'false').lower() == 'true'

app = FastAPI(
    title='Sclerotin - Secure FastAPI demo',
    description='One endpoint behind Nginx in a hardened Docker Compose deployment.',
    version='1.0.0',
    openapi_url='/openapi.json' if DOCS_ENABLED else None,
)

STATIC_DIR = Path(__file__).resolve().parent / 'static'

# API responses are JSON: no scripts, styles or frames needed
API_CSP = "default-src 'none'; frame-ancestors 'none'"

# The landing page: its script and stylesheet are files, so no unsafe-inline and no nonce
LANDING_CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'"
)

# Swagger UI and ReDoc load assets from CDNs and rely on inline scripts and styles
DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "connect-src 'self'; "
    "worker-src blob:; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

DOCS_PATHS = (
    {app.docs_url, app.redoc_url, app.swagger_ui_oauth2_redirect_url} if DOCS_ENABLED else set()
)


@app.middleware('http')
async def add_security_headers(request: Request, call_next):
    # The path the router matches; url.path re-parses it and reads /%3F as /
    path = request.scope['path']

    # Unhandled exceptions would otherwise be answered by ServerErrorMiddleware,
    # which sits outside this middleware, so the 500 would lack the headers below
    try:
        response = await call_next(request)
    except Exception:
        logger.exception('Unhandled error: %s %s', request.method, path)
        response = JSONResponse({'detail': 'Internal Server Error'}, status_code=500)

    # Repeated in webserver/default.conf for Nginx's own responses; keep in sync
    if path in DOCS_PATHS:
        csp = DOCS_CSP
    elif path == '/':
        csp = LANDING_CSP
    else:
        csp = API_CSP

    response.headers['Content-Security-Policy'] = csp

    response.headers['X-Content-Type-Options'] = 'nosniff'

    response.headers['Permissions-Policy'] = (
        'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
    )

    # robots.txt disallows nothing on purpose: a crawler must fetch a path to see this header
    if path != '/':
        response.headers['X-Robots-Tag'] = 'noindex'

    return response


# One route per file, nothing mounted: an allowlist, not whatever ends up in static/


@app.api_route('/', methods=['GET', 'HEAD'], include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/robots.txt', include_in_schema=False)
async def robots():
    return FileResponse(STATIC_DIR / 'robots.txt')


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get('/static/favicon.svg', include_in_schema=False)
async def favicon_svg():
    return FileResponse(STATIC_DIR / 'favicon.svg')


@app.get('/static/logo.jpeg', include_in_schema=False)
async def logo_jpeg():
    return FileResponse(STATIC_DIR / 'logo.jpeg')


@app.get('/static/style.css', include_in_schema=False)
async def stylesheet():
    return FileResponse(STATIC_DIR / 'style.css')


@app.get('/static/headers.js', include_in_schema=False)
async def headers_script():
    return FileResponse(STATIC_DIR / 'headers.js')


class PingResponse(BaseModel):
    '''Body of a health check response.'''

    status: str
    message: str

    model_config = {
        'json_schema_extra': {
            'examples': [{'status': 'ok', 'message': 'Sclerotin is running!'}],
        }
    }


# HEAD too: uptime monitors that probe with HEAD would get a 405 otherwise
@app.api_route('/api/v1/ping', methods=['GET', 'HEAD'], summary='Health check')
async def ping() -> PingResponse:
    return PingResponse(status='ok', message='Sclerotin is running!')
