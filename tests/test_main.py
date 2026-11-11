import importlib
import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


DEFAULT_CONF = Path(__file__).resolve().parent.parent / 'webserver' / 'default.conf'

PERMISSIONS_POLICY = 'geolocation=(), microphone=(), camera=(), payment=(), usb=()'


def load_app(monkeypatch, docs_enabled):
    '''Run main.py again: it reads DOCS_ENABLED once, at import.'''
    if docs_enabled:
        monkeypatch.setenv('DOCS_ENABLED', 'true')
    else:
        monkeypatch.delenv('DOCS_ENABLED', raising=False)
    importlib.reload(main)
    return TestClient(main.app)


@pytest.fixture
def client(monkeypatch):
    return load_app(monkeypatch, docs_enabled=False)


@pytest.fixture
def docs_client(monkeypatch):
    return load_app(monkeypatch, docs_enabled=True)


def test_ping(client):
    response = client.get('/api/v1/ping')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'message': 'Sclerotin is running!'}


def test_ping_head(client):
    response = client.head('/api/v1/ping')
    assert response.status_code == 200
    assert response.content == b''


def test_ping_other_methods(client):
    # The price of the separate HEAD route: Allow lists only GET
    response = client.post('/api/v1/ping')
    assert response.status_code == 405
    assert response.headers['allow'] == 'GET'


def test_api_headers(client):
    headers = client.get('/api/v1/ping').headers
    assert headers['content-security-policy'] == main.API_CSP
    assert headers['x-content-type-options'] == 'nosniff'
    assert headers['permissions-policy'] == PERMISSIONS_POLICY
    assert headers['x-robots-tag'] == 'noindex'


def test_landing_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert response.headers['content-security-policy'] == main.LANDING_CSP
    assert 'x-robots-tag' not in response.headers


def test_landing_page_head(client):
    assert client.head('/').status_code == 200


@pytest.mark.parametrize('path', [
    '/robots.txt',
    '/static/favicon.svg',
    '/static/logo.jpeg',
    '/static/style.css',
    '/static/headers.js',
])
def test_static_files(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['content-security-policy'] == main.API_CSP
    assert response.headers['x-robots-tag'] == 'noindex'


def test_favicon_ico(client):
    assert client.get('/favicon.ico').status_code == 204


@pytest.mark.parametrize('path', [
    '/static/index.html',
    '/static/',
    '/main.py',
    '/static/%2e%2e/main.py',
])
def test_only_listed_files_are_served(client, path):
    # One route per file, nothing mounted
    response = client.get(path)
    assert response.status_code == 404
    assert response.headers['content-security-policy'] == main.API_CSP


def test_encoded_question_mark_is_not_the_landing_page(client):
    # The router sees the path '/?' here: the strict CSP, not the landing page's
    response = client.get('/%3F')
    assert response.status_code == 404
    assert response.headers['content-security-policy'] == main.API_CSP
    assert response.headers['x-robots-tag'] == 'noindex'


@pytest.mark.parametrize('path', ['/docs', '/redoc', '/docs/oauth2-redirect', '/openapi.json'])
def test_docs_off_by_default(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize('path', ['/docs', '/redoc', '/docs/oauth2-redirect'])
def test_docs_get_the_relaxed_csp(docs_client, path):
    response = docs_client.get(path)
    assert response.status_code == 200
    assert response.headers['content-security-policy'] == main.DOCS_CSP


def test_schema_gets_the_strict_csp(docs_client):
    response = docs_client.get('/openapi.json')
    assert response.status_code == 200
    assert response.headers['content-security-policy'] == main.API_CSP


def test_schema_operation_ids_are_unique(docs_client):
    # A route shared by GET and HEAD gave both methods one operationId (#25)
    paths = docs_client.get('/openapi.json').json()['paths']
    ids = [operation['operationId'] for methods in paths.values() for operation in methods.values()]
    assert len(ids) == len(set(ids))
    assert list(paths['/api/v1/ping']) == ['get']


def test_unhandled_error_keeps_the_headers(client, monkeypatch, caplog):
    def fail(**kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr(main, 'PingResponse', fail)
    response = client.get('/api/v1/ping')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal Server Error'}
    assert response.headers['content-security-policy'] == main.API_CSP
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'Unhandled error: GET /api/v1/ping' in caplog.text


def access_record(client_address, path):
    return logging.LogRecord(
        'uvicorn.access', logging.INFO, __file__, 0,
        '%s - "%s %s HTTP/%s" %d', (client_address, 'GET', path, '1.1', 200), None,
    )


@pytest.mark.parametrize(('client_address', 'path', 'kept'), [
    ('127.0.0.1:41234', '/api/v1/ping', False),  # the container's own healthcheck
    ('172.18.0.3:41234', '/api/v1/ping', True),  # a request through Nginx
    ('127.0.0.1:41234', '/', True),
])
def test_healthcheck_log_filter(client_address, path, kept):
    assert main.SkipHealthcheckLog().filter(access_record(client_address, path)) is kept


def test_healthcheck_log_filter_keeps_other_records():
    record = logging.LogRecord('uvicorn.access', logging.INFO, __file__, 0, 'started', (), None)
    assert main.SkipHealthcheckLog().filter(record) is True


def nginx_fallback(variable):
    '''The value default.conf gives $variable when the app sent no such header.'''
    match = re.search(rf'\${variable} \{{\s*"" (?:"([^"]*)"|([^\s;]+));', DEFAULT_CONF.read_text())
    assert match, f'${variable} not found in default.conf'
    return match.group(1) or match.group(2)


def test_nginx_fallbacks_match_the_app(client):
    # The same values live in main.py and default.conf: change both together
    headers = client.get('/api/v1/ping').headers
    assert nginx_fallback('fallback_csp') == headers['content-security-policy']
    assert nginx_fallback('fallback_nosniff') == headers['x-content-type-options']
    assert nginx_fallback('fallback_permissions_policy') == headers['permissions-policy']
