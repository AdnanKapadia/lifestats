# FatSecret proxy (replaces the Railway service)

## Why this exists

FatSecret allowlists IP addresses, and Vercel functions have no stable outbound
IP. Something with a fixed address has to make the calls. That is the only job
this service has, and the only reason the Railway service ever existed.

The old service was `fatsecret-proxy-production-e380.up.railway.app`
(source: `github.com/AdnanKapadia/fatsecret-proxy`): an open, unauthenticated
pass-through. Anyone who found the URL could spend the FatSecret quota.

This is a port of that service, keeping everything that was proven in
production and changing four things — see **What changed** below.

## Host

The "mac mini" is 2011 Apple hardware running **Ubuntu 24.04**, not macOS. Use
`systemd` and `apt`; there is no `launchd` and no `brew`.

- Hostname `macmini`, LAN `192.168.1.248`, user `adnan`, Python 3.12.3
- Public IP `76.187.64.226` (Spectrum). **It can change** — see the risk note.
- `cloudflared` is already installed and running a named tunnel `macmini`
  (`67a65dd7-c858-4607-a676-bc4dc9d6b94a`), today serving
  `garden.adnankapadia.org`. We add an ingress rule rather than a new tunnel.
- Real sshd is LAN-only (nftables drops outside traffic to :22); public :22 is
  a Cowrie honeypot on :2222. Don't confuse the two.
- Log in from the Windows PC with `C:\Users\adnan\Documents\macmini\ub.sh`.

## Design: full pass-through (settled empirically)

FatSecret's OAuth2 docs say the allowlist restricts *token requests*. **That is
backwards.** Measured from an un-allowlisted IP on 2026-11-16:

```
$ python3 fatsecret_token.py
OK: minted a token          # token request SUCCEEDS from any IP
$ ...search_foods('apple')
FatSecretApiError: FatSecret error 21: Invalid IP address detected: '76.187.64.226'
```

Method calls are IP-checked; token requests are not. So the lighter design —
the mini minting a token every few hours and Vercel calling FatSecret directly —
does **not** work. Every search must originate from an allowlisted IP, so the
mini sits in the request path and needs the tunnel. Don't revisit this without
re-running that check.

Note error 21 arrived **inside an HTTP 200**. That is the failure `proxy.py`
maps to a 502 and that `backend/app.py` now refuses to cache.

### Allowlist propagation is eventually consistent

After adding an IP, expect a window of **intermittent** error 21s — the same
query fails, then succeeds, as FatSecret's fleet picks up the change. Observed
~2/6 failures immediately after the change, trending to zero. Don't debug this;
re-run the diff until it is clean.

## What changed from the Railway source

| | Railway | Here | Why |
|---|---|---|---|
| Auth | none | `X-Proxy-Secret`, fails closed | the old one was open to the internet |
| FatSecret error body | passed through as 200 | mapped to 502 | `raise_for_status()` misses errors returned inside a 200, which is how error 21 arrives |
| Token margin | 60s | 15min | a request starting at second 59 could present a token that expires mid-flight |
| Credentials | `os.environ[...]` at import | lazy, raises per-request | a missing var killed the whole process at startup |

Kept exactly as-is, because they are proven in production and the docs are
wrong about both: **`scope=basic`** (docs claim v1 `foods.search` needs
`premier`) and **`GET` with query params** (docs document `POST`). Also staying
on **v1** `foods.search`/`food.get` despite the deprecation banner — v6 returns
a different serving shape than `normalize_food_data()` in `backend/app.py`
parses.

## Setup on the mini

```bash
ssh adnan@192.168.1.248     # or: bash ~/Documents/macmini/ub.sh '<cmd>'
sudo apt-get install -y python3-venv
git clone https://github.com/AdnanKapadia/lifestats.git ~/lifestats
cd ~/lifestats/fatsecret-proxy
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp env.example .env     # fill in; same values as the Railway service's vars
```

`.env` is gitignored — confirm with `git check-ignore fatsecret-proxy/.env`.
Generate the shared secret with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Confirm the mini's IP is allowlisted before going further:

```bash
./.venv/bin/python fatsecret_token.py   # proves credentials
./.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv('.env')
import fatsecret_client as fc; print(len(fc.search_foods('apple')['foods']['food']))
"                                        # proves the IP allowlist
```

The first can succeed while the second fails — that is the whole point above.

### systemd unit

`/etc/systemd/system/fatsecret-proxy.service`:

```ini
[Unit]
Description=FatSecret proxy for lifestats
After=network-online.target
Wants=network-online.target

[Service]
User=adnan
WorkingDirectory=/home/adnan/lifestats/fatsecret-proxy
ExecStart=/home/adnan/lifestats/fatsecret-proxy/.venv/bin/gunicorn --bind 127.0.0.1:8787 --workers 2 --timeout 30 --access-logfile /var/log/fatsecret-proxy.access.log proxy:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fatsecret-proxy
curl -s localhost:8787/healthz     # {"ok":true,...}
```

Binds to `127.0.0.1` only. `cloudflared` runs on the same host, so it never
needs to be reachable on the LAN — and must not be port-forwarded.

### Cloudflare ingress

The tunnel already exists. **Add** to the `ingress:` list in
`/etc/cloudflared/config.yml`, above the catch-all `http_status:404`:

```yaml
  - hostname: fatsecret.adnankapadia.org
    service: http://localhost:8787
```

```bash
cloudflared tunnel route dns macmini fatsecret.adnankapadia.org
sudo systemctl restart cloudflared
curl -s https://fatsecret.adnankapadia.org/healthz
```

`cloudflared` here has no `ExecReload`, and SIGHUP makes it **exit** rather
than reload config — with no `Restart=` in its unit the tunnel then stays
down until you start it again. Use `systemctl restart cloudflared`, which
briefly interrupts `garden.adnankapadia.org` too, and confirm with
`systemctl is-active cloudflared` afterwards.

## Cutover

In order. Each step is reversible until the last.

1. Mini's IP on the FatSecret allowlist, **Railway's entry still there**.
2. `/healthz` returns `{"ok": true}` through the tunnel.
3. Diff against Railway until clean (retry through the propagation window):
   ```bash
   python3 scripts/diff_fatsecret_proxy.py \
     --new https://fatsecret.adnankapadia.org --secret "$FATSECRET_PROXY_SECRET"
   ```
4. Set in Vercel (Production + Preview):
   - `FATSECRET_PROXY_URL=https://fatsecret.adnankapadia.org`
   - `FATSECRET_PROXY_SECRET=<the generated secret>`
5. Redeploy. Verify with a query **not** already in `search_cache` and a
   `food_id` not in `food_cache` — otherwise you are reading cache and never
   reaching FatSecret at all.
6. Watch for a day, then shut Railway down and remove its IP from the allowlist.

Rollback: unset `FATSECRET_PROXY_URL` in Vercel and redeploy. The code defaults
back to the Railway URL.

## Known risk: the home IP is not static

Spectrum residential IPs are stable for long stretches but not guaranteed. If
it changes, calls fail with error 21 and new food searches stop. Cached foods
keep working and nothing gets poisoned (`backend/app.py` refuses to cache empty
results). Symptom:

```bash
curl -s https://fatsecret.adnankapadia.org/healthz
# {"ok":true} — token minting is NOT IP-gated, so health can look fine
curl -s -H "X-Proxy-Secret: $SECRET" \
  "https://fatsecret.adnankapadia.org/search?query=apple"
# {"code":21,...} — this is the real check
```

**The durable fix is FatSecret Premier Free** (free; startups, non-profits and
students qualify), which allows allowlisting **CIDR ranges** rather than single
IPs — so drift within the ISP's block stops mattering. It also adds barcode
scanning and autocomplete. Basic is single IPs only.
