"""Thin FatSecret REST client that returns the API's raw JSON.

The response shapes here are deliberately *unmodified* FatSecret v1 payloads,
because backend/app.py already parses those shapes:

    foods.search -> {"foods": {"food": [...], "max_results", "page_number",
                               "total_results"}}
    food.get     -> {"food": {"food_id", "food_name", "food_type", "food_url",
                              "servings": {"serving": [...]}}}

food.get v1 carries a deprecation banner in FatSecret's docs, but v6 returns a
different serving structure than normalize_food_data() in backend/app.py
expects. Stay on v1 until that parsing is updated and re-tested.
"""

import time

import requests

from fatsecret_token import TokenCache

API_URL = 'https://platform.fatsecret.com/rest/server.api'

# Error codes worth retrying rather than surfacing.
#
# 21 ("Invalid IP address detected") is in here for a non-obvious reason. It is
# normally a hard configuration error, but FatSecret's allowlist is eventually
# consistent across their fleet: right after adding an IP, identical requests
# fail and succeed at random — measured at roughly a 1-in-3 failure rate, with
# a *different* subset of queries failing on each run. Retrying turns that into
# a non-event. A genuinely un-allowlisted IP still fails, just after
# RETRY_CODES attempts instead of one.
#
# 20 ("System temporarily unavailable") and 24 ("A timeout has occurred") are
# transient by definition.
RETRY_CODES = {20, 21, 24}
MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 0.4

_tokens = TokenCache()


class FatSecretApiError(RuntimeError):
    """A FatSecret error response, carrying the API's own error code."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f'FatSecret error {code}: {message}')


def _extract_error(payload):
    """Return (code, message) if the payload is a FatSecret error, else None.

    FatSecret reports failures in the body as
    {"error": {"code": "21", "message": "Invalid IP address detected: ..."}}
    and does not reliably use a non-200 HTTP status, so the body must be
    inspected on every call. Codes that matter here:
      13 - invalid token (re-mint)
      14 - missing scope (the token was requested with too narrow a scope)
      21 - invalid IP address (this host fell off the allowlist)
    """
    if not isinstance(payload, dict):
        return None
    error = payload.get('error')
    if not isinstance(error, dict):
        return None
    # The docs show code as a string; don't assume either way.
    raw_code = error.get('code')
    try:
        code = int(raw_code)
    except (TypeError, ValueError):
        code = raw_code
    return code, error.get('message', 'unknown error')


def call(method, params, timeout=10):
    """Call a FatSecret method and return its parsed JSON.

    Retries transient failures (see RETRY_CODES) and re-mints the token once if
    it is rejected. Raises FatSecretApiError if every attempt fails,
    requests.RequestException for transport failures, and FatSecretAuthError if
    a token can't be minted at all.
    """
    body = {'method': method, 'format': 'json'}
    body.update(params)

    token_retried = False
    last_error = None

    for attempt in range(MAX_ATTEMPTS):
        if attempt:
            # Linear backoff. Deliberately short: this sits in the path of a
            # user-facing food search, and backend/app.py gives up at 5s.
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        token = _tokens.get()

        # GET with query params, not the POST the docs show. This is what the
        # Railway service does today, and it is the combination proven against
        # these v1 methods in production.
        response = requests.get(
            API_URL,
            params=body,
            headers={'Authorization': f'Bearer {token}'},
            timeout=timeout,
        )

        if response.status_code == 401 and not token_retried:
            # Rejected at the HTTP layer; mint a new token and go again.
            token_retried = True
            _tokens.invalidate()
            continue

        if response.status_code >= 500:
            last_error = FatSecretApiError(
                f'http_{response.status_code}', response.text[:500]
            )
            continue

        if response.status_code != 200:
            raise FatSecretApiError(
                f'http_{response.status_code}', response.text[:500]
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise FatSecretApiError('non_json', response.text[:500]) from exc

        error = _extract_error(payload)
        if not error:
            return payload

        code, message = error

        if code == 13 and not token_retried:
            # Invalid token; a revoked one shouldn't wedge us until expiry.
            token_retried = True
            _tokens.invalidate()
            continue

        last_error = FatSecretApiError(code, message)
        if code in RETRY_CODES:
            continue

        raise last_error

    raise last_error


def search_foods(query, max_results=None, page_number=None):
    """foods.search v1. max_results defaults to 20 server-side, capped at 50."""
    params = {'search_expression': query}
    if max_results is not None:
        params['max_results'] = max_results
    if page_number is not None:
        params['page_number'] = page_number
    return call('foods.search', params)


def get_food(food_id):
    """food.get v1."""
    return call('food.get', {'food_id': food_id})
