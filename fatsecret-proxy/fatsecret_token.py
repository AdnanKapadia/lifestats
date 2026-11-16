"""Mint FatSecret OAuth 2.0 access tokens.

FatSecret allowlists the IP addresses that are permitted to *request* tokens
(see https://platform.fatsecret.com/docs/guides/authentication/oauth2 — "tokens
can only be requested from a finite number of IP addresses"). That restriction
is the only reason this code has to run on a host with a stable IP rather than
on Vercel, whose outbound address changes per invocation.

Deliberate choices, don't "fix" them without re-testing against the live API:

* Credentials go in the HTTP Basic auth header. The docs list client_id and
  client_secret as parameters but every official example uses Basic auth.
* `scope=basic` is sent explicitly. FatSecret's docs say v1 foods.search needs
  the `premier` scope, which suggests omitting scope (to get every scope the key
  has) would be safer. It isn't necessary: the Railway service has been running
  `scope=basic` against these exact v1 methods in production and returns full
  results. Matching it keeps the token identical to the one in use today, so
  the cutover changes nothing about what FatSecret sees. Don't "upgrade" this
  without re-running scripts/diff_fatsecret_proxy.py.
* Tokens live 86400s (24h). Callers should refresh well before expiry rather
  than waiting for a 401, since a failed refresh is the expected symptom of the
  host's IP falling off the allowlist.
"""

import os
import time

import requests

TOKEN_URL = 'https://oauth.fatsecret.com/connect/token'

# Refresh this far ahead of the stated expiry so a caller never presents a token
# that expires mid-flight.
EXPIRY_MARGIN_SECONDS = 15 * 60


class FatSecretAuthError(RuntimeError):
    """Raised when a token could not be minted."""


def _credentials():
    client_id = os.getenv('FATSECRET_CLIENT_ID')
    client_secret = os.getenv('FATSECRET_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise FatSecretAuthError(
            'FATSECRET_CLIENT_ID and FATSECRET_CLIENT_SECRET must be set'
        )
    return client_id, client_secret


def mint_token(timeout=15):
    """Request a fresh access token.

    Returns a dict with 'access_token' and 'expires_at' (unix seconds, already
    reduced by EXPIRY_MARGIN_SECONDS).
    """
    client_id, client_secret = _credentials()

    # Read the clock before the request: if the call takes a while, this errs
    # toward expiring early rather than late.
    requested_at = time.time()

    try:
        response = requests.post(
            TOKEN_URL,
            auth=(client_id, client_secret),
            data={'grant_type': 'client_credentials', 'scope': 'basic'},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FatSecretAuthError(f'token request failed: {exc}') from exc

    if response.status_code != 200:
        # A 400/401 here is what an IP that is no longer allowlisted looks like.
        raise FatSecretAuthError(
            f'token endpoint returned {response.status_code}: {response.text[:500]}'
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise FatSecretAuthError(
            f'token endpoint returned non-JSON: {response.text[:500]}'
        ) from exc

    access_token = payload.get('access_token')
    if not access_token:
        raise FatSecretAuthError(f'no access_token in response: {payload}')

    expires_in = payload.get('expires_in')
    try:
        expires_in = int(expires_in)
    except (TypeError, ValueError):
        # Don't guess long if the API stops telling us; an hour is safe.
        expires_in = 3600

    expires_at = requested_at + max(expires_in - EXPIRY_MARGIN_SECONDS, 60)

    return {
        'access_token': access_token,
        'expires_at': expires_at,
        'expires_in': expires_in,
    }


class TokenCache:
    """Keeps one token in memory and re-mints it shortly before it expires."""

    def __init__(self):
        self._token = None
        self._expires_at = 0.0

    def get(self):
        if self._token and time.time() < self._expires_at:
            return self._token
        minted = mint_token()
        self._token = minted['access_token']
        self._expires_at = minted['expires_at']
        return self._token

    def invalidate(self):
        """Drop the cached token so the next get() re-mints.

        Call this on a FatSecret error 13 (invalid token) so a revoked token
        doesn't wedge the process until its nominal expiry.
        """
        self._token = None
        self._expires_at = 0.0


if __name__ == '__main__':
    # Smoke test: prove this host's IP is allowlisted. Prints no secrets.
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
    except ImportError:
        pass

    result = mint_token()
    print('OK: minted a token')
    print(f"  length:     {len(result['access_token'])} chars")
    print(f"  expires_in: {result['expires_in']}s")
