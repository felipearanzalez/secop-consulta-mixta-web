"""SECOP Croma bridge, stdlib-only. Deploy as a separate Render free Python service.

Security by default: does not make upstream requests without two server-side secrets.
Never accepts an arbitrary upstream URL, never puts CROMA_API_KEY in HTML or logs.
"""
import hmac
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CROMA_ENDPOINT = 'https://api.croma.run/co/secop/contracts-search/v1'
API_VERSION = '1.0'
MAX_REQUEST_BYTES = 2048
MAX_RESPONSE_BYTES = 2_100_000
ALLOWED_ORIGIN = os.getenv('SECOP_ORIGIN', 'https://secop-consulta-mixta-web.onrender.com').rstrip('/')
CROMA_KEY = os.getenv('CROMA_API_KEY', '').strip()
APP_SECRET = os.getenv('SECOP_ACCESS_TOKEN', '').strip()
MAX_PAGES = max(1, min(30, int(os.getenv('CROMA_PAGE_LIMIT', '5'))))
DAILY_LIMIT = max(1, min(300, int(os.getenv('SECOP_DAILY_LIMIT', '50'))))
ALLOW_TEST_ORIGIN = os.getenv('SECOP_ALLOW_TEST_ORIGIN') == '1'
_requests = {}
_lock = threading.Lock()


class ApiFault(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def ready():
    return bool(CROMA_KEY and APP_SECRET and len(APP_SECRET) >= 20)


def as_document(value):
    raw = str(value or '').strip()
    if not re.fullmatch(r'[0-9.,\- ]{5,24}', raw):
        raise ApiFault(400, 'Identificación inválida: utilice solamente números y separadores.')
    digits = re.sub(r'\D', '', raw)
    base = raw.split('-')[0]
    if '-' in raw and not re.fullmatch(r'\s*\d\s*', raw.split('-')[-1]):
        raise ApiFault(400, 'Dígito de verificación incorrecto.')
    if not 5 <= len(re.sub(r'\D', '', base)) <= 15:
        raise ApiFault(400, 'Identificación fuera del rango admitido.')
    return raw


def rate_limit(source):
    # In-memory quota provides an additional guard; platform-level limits are advisable.
    period = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    with _lock:
        key = (period, source)
        active = {k: v for k, v in _requests.items() if k[0] == period}
        _requests.clear()
        _requests.update(active)
        if _requests.get(key, 0) >= DAILY_LIMIT:
            raise ApiFault(429, 'Límite diario de consultas alcanzado. Intente mañana.')
        _requests[key] = _requests.get(key, 0) + 1


def request_croma(payload):
    """Only known fixed endpoint; injectable in tests."""
    req = Request(CROMA_ENDPOINT, data=json.dumps(payload).encode('utf-8'),
                  headers={'Authorization': f'Bearer {CROMA_KEY}',
                           'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=25) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise ApiFault(502, 'La respuesta de Croma supera el límite seguro.')
            data = json.loads(content.decode('utf-8'))
    except HTTPError as e:
        if e.code in (401, 403):
            raise ApiFault(502, 'Croma rechazó la autenticación o autorización de la aplicación.') from e
        if e.code in (402, 429):
            raise ApiFault(429, 'Croma informa falta de créditos o límite de solicitudes.') from e
        raise ApiFault(502, f'Croma devolvió HTTP {e.code}.') from e
    except (URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as e:
        raise ApiFault(502, 'No fue posible obtener una respuesta válida de Croma.') from e
    if not isinstance(data, dict):
        raise ApiFault(502, 'El formato de respuesta de Croma no es un objeto JSON.')
    return data


def unpack_api(data):
    # Croma's API returns an envelope (data) and some lists nested under data.
    body = data.get('data', data)
    if not isinstance(body, dict):
        raise ApiFault(502, 'Respuesta de Croma sin datos reconocibles.')
    if body.get('error'):
        raise ApiFault(502, 'Croma reportó un error en la consulta.')
    rows = body.get('results', body.get('contracts', []))
    if not isinstance(rows, list):
        raise ApiFault(502, 'No se encontró una lista de contratos en Croma.')
    try:
        total = int(body.get('total', len(rows)))
        pages = int(body.get('total_pages', 1))
    except (TypeError, ValueError):
        total, pages = len(rows), 1
    return body, rows, max(total, len(rows)), max(1, pages)


def collect(document, criterion, platform="any", api_call=request_croma):
    output = []
    as_of = ''
    pages_processed = 0
    total = 0
    available_pages = 1
    for page in range(1, MAX_PAGES + 1):
        payload = {criterion: document, 'page': page, 'per_page': 100, 'platform': platform, 'sort': 'recent'}
        body, rows, count, total_pages = unpack_api(api_call(payload))
        pages_processed = page
        total = max(total, count)
        available_pages = total_pages
        as_of = str(body.get('as_of') or '')
        output.extend(rows)
        if not rows or page >= total_pages:
            break
    # Cap output for bounded memory and request costs; not a claim of completeness.
    return {'records': output, 'count_returned': len(output), 'total_reported': total,
            'pages_checked': pages_processed, 'total_pages': available_pages,
            'truncated': available_pages > pages_processed or total > len(output), 'as_of': as_of}


def search(body, api_call=request_croma):
    document = as_document(body.get('document', ''))
    representative = body.get('representative_document')
    platform = body.get('platform', 'any')
    if platform not in ('any', 'secop_i', 'secop_ii'):
        raise ApiFault(400, 'Plataforma no admitida.')
    direct = collect(document, 'provider_document', platform, api_call)
    rep = None
    if representative:
        rep = collect(as_document(representative), 'legal_rep_document', platform, api_call)
    return {'source': 'Croma / SECOP I y II', 'search_document': document,
            'direct': direct, 'representative_candidates': rep,
            'at_utc': datetime.now(timezone.utc).isoformat(),
            'notice': 'Coincidir con un representante legal no demuestra que el NIT consultado integre el contratista. La ejecución requiere corroboración documental.'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'SECOP-Croma-Bridge'
    def log_message(self, format, *args):
        # Do not log IDs, request bodies or tokens.
        return

    def headers_base(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Vary', 'Origin')
        origin = self.headers.get('Origin', '').rstrip('/')
        if origin == ALLOWED_ORIGIN or (ALLOW_TEST_ORIGIN and origin.startswith('http://localhost:')):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-SECOP-Access')

    def respond(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.headers_base()
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        if self.path not in ('/health', '/api/croma/search'):
            self.respond(404, {'error': 'Ruta no encontrada'}); return
        self.send_response(204)
        self.headers_base()
        self.end_headers()

    def do_GET(self):
        if self.path != '/health':
            self.respond(404, {'error': 'Ruta no encontrada'}); return
        self.respond(200, {'status': 'ok', 'version': API_VERSION, 'configured': ready()})

    def do_POST(self):
        if self.path != '/api/croma/search':
            self.respond(404, {'error': 'Ruta no encontrada'}); return
        origin = self.headers.get('Origin', '').rstrip('/')
        if origin and origin != ALLOWED_ORIGIN and not (ALLOW_TEST_ORIGIN and origin.startswith('http://localhost:')):
            self.respond(403, {'error': 'Origen no autorizado'}); return
        if not ready():
            self.respond(503, {'error': 'Integración Croma no configurada aún en Render.'}); return
        presented = self.headers.get('X-SECOP-Access', '')
        if not hmac.compare_digest(presented.encode(), APP_SECRET.encode()):
            self.respond(401, {'error': 'Clave de acceso del buscador no válida.'}); return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 2 or size > MAX_REQUEST_BYTES:
                raise ApiFault(413, 'Solicitud demasiado grande o vacía.')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict) or set(body) - {'document', 'representative_document', 'platform'}:
                raise ApiFault(400, 'Parámetros no admitidos.')
            source_ip = self.client_address[0]  # never trust arbitrary X-Forwarded-For.
            rate_limit(source_ip)
            result = search(body)
            self.respond(200, result)
        except ApiFault as exc:
            self.respond(exc.status, {'error': str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError):
            self.respond(400, {'error': 'El cuerpo debe ser JSON válido.'})
        except Exception:
            self.respond(502, {'error': 'Error interno al consultar el origen. No se ha concluido que no existan contratos.'})


def main():
    port = int(os.getenv('PORT', '10000'))
    print(f'SECOP-Croma backend {API_VERSION} escuchando en puerto {port} (configurado: {ready()})', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
