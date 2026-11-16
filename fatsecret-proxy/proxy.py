"""FatSecret pass-through proxy — the replacement for the Railway service.

Exposes the same two endpoints the Railway proxy did, returning byte-identical
FatSecret v1 payloads so backend/app.py needs no parsing changes:

    GET /search?query=<text>   -> foods.search
    GET /food?food_id=<id>     -> food.get
    GET /healthz               -> liveness + token check (no secrets)

Two things this does that the Railway service did not:

1. Requires a shared secret. The Railway proxy was open to the internet, so
   anyone who found the URL could burn the FatSecret quota. Set
   FATSECRET_PROXY_SECRET here and in Vercel, and callers must send it as
   X-Proxy-Secret.

2. Maps FatSecret error bodies to HTTP 502. FatSecret returns failures as
   {"error": {...}} inside a 200, and backend/app.py only checks the status
   code. Passing that through would make app.py parse zero foods and then
   cache {'foods': []} permanently for that query — a wrong empty result that
   never expires. Returning 502 makes app.py's existing status check catch it.

Run behind a Cloudflare named tunnel; do not port-forward this directly.
"""

import hmac
import logging
import os

from flask import Flask, jsonify, request

from fatsecret_client import FatSecretApiError, get_food, search_foods
from fatsecret_token import FatSecretAuthError

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('fatsecret-proxy')

PROXY_SECRET = os.getenv('FATSECRET_PROXY_SECRET', '')


def _authorized():
    """Constant-time comparison of the shared secret.

    If no secret is configured the proxy refuses every request rather than
    running open to the internet — failing closed, since a misconfigured
    deploy that silently accepts anyone is the worse outcome.
    """
    if not PROXY_SECRET:
        return False
    presented = request.headers.get('X-Proxy-Secret', '')
    return hmac.compare_digest(presented, PROXY_SECRET)


@app.before_request
def _check_secret():
    if request.path == '/healthz':
        return None
    if not _authorized():
        if not PROXY_SECRET:
            log.error('FATSECRET_PROXY_SECRET is not set; refusing all requests')
            return jsonify({'error': 'proxy not configured'}), 503
        return jsonify({'error': 'forbidden'}), 403
    return None


def _handle_upstream(fn, *args, **kwargs):
    """Run a FatSecret call, turning failures into non-200 responses."""
    try:
        return jsonify(fn(*args, **kwargs))
    except FatSecretAuthError as exc:
        # Could not mint a token at all. The usual cause is this host's public
        # IP no longer being on the FatSecret allowlist.
        log.error('auth failure: %s', exc)
        return jsonify({'error': 'upstream auth failed', 'detail': str(exc)}), 502
    except FatSecretApiError as exc:
        if exc.code == 21:
            log.error('FatSecret rejected this host IP (code 21): %s', exc.message)
        else:
            log.error('upstream error %s: %s', exc.code, exc.message)
        return jsonify({
            'error': 'upstream error',
            'code': exc.code,
            'detail': exc.message,
        }), 502
    except Exception as exc:  # noqa: BLE001 - never leak a traceback upstream
        log.exception('unexpected failure')
        return jsonify({'error': 'proxy failure', 'detail': str(exc)}), 502


@app.route('/search')
def search():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'error': 'query required'}), 400

    max_results = request.args.get('max_results', type=int)
    page_number = request.args.get('page_number', type=int)

    return _handle_upstream(
        search_foods, query, max_results=max_results, page_number=page_number
    )


@app.route('/food')
def food():
    food_id = request.args.get('food_id', '').strip()
    if not food_id:
        return jsonify({'error': 'food_id required'}), 400
    return _handle_upstream(get_food, food_id)


@app.route('/healthz')
def healthz():
    """Unauthenticated, but reveals nothing beyond whether auth works."""
    try:
        from fatsecret_token import mint_token

        mint_token()
        return jsonify({'ok': True, 'token': 'ok', 'secret_configured': bool(PROXY_SECRET)})
    except Exception as exc:  # noqa: BLE001
        return jsonify({
            'ok': False,
            'token': 'failed',
            'detail': str(exc)[:300],
            'secret_configured': bool(PROXY_SECRET),
        }), 503


if __name__ == '__main__':
    # Bind to loopback only: Cloudflare's tunnel daemon runs on the same host,
    # so the listener never needs to be reachable on the LAN.
    port = int(os.getenv('PORT', '8787'))
    app.run(host='127.0.0.1', port=port)
