"""
Remote API (/api/agent/*) — key-protected read/write access to a user's data.

Exists so that something outside the browser (a Claude skill, a script, a person
with curl) can read and write the same data the app writes, without pretending to
be the frontend. Three rules shape everything in here:

  1. Every route requires the shared key. No exceptions, including reads.
  2. Every route resolves the user id through require_user() first. There is no
     users table, so an unchecked write would silently invent a user.
  3. Times cross the wire as epoch milliseconds (matching the DB) but are always
     echoed back as local date/time in an IANA timezone, and any local date the
     caller sends is interpreted in that timezone.

Routes are grouped by resource and return the same {'error': '...'} shape as the
rest of app.py.
"""

import hmac
import os
import re
import time
import uuid
from datetime import date, datetime, time as dtime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

import db

agent_api = Blueprint('agent_api', __name__)

# The shared phrase. Override in prod via env; the default matches what the app ships with.
API_KEY = os.getenv('LIFESTATS_API_KEY', 'foodtrack')

# No per-user timezone column exists, so every request falls back to this.
DEFAULT_TZ = os.getenv('LIFESTATS_DEFAULT_TZ', 'America/Los_Angeles')

MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack']

# Nutrition keys accepted on meal writes — mirrors what db.add_meal/update_meal read.
NUTRITION_KEYS = [
    'calories', 'protein', 'carbs', 'fat', 'cholesterol', 'sodium', 'fiber',
    'sugar', 'saturatedFat', 'transFat', 'polyunsaturatedFat',
    'monounsaturatedFat', 'addedSugar', 'vitaminD', 'calcium', 'iron',
    'potassium', 'vitaminC'
]

MAX_LIMIT = 1000
DEFAULT_LIMIT = 200

# /summary aggregates one day per query, so keep the range from fanning out.
MAX_SUMMARY_DAYS = 92

# A bare local calendar day, as opposed to a full ISO datetime.
PLAIN_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


# ============================================================================
# AUTH + USER RESOLUTION
# ============================================================================

class ApiError(Exception):
    """Raised anywhere in this module to abort with a specific status + message."""

    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra

    def to_response(self):
        body = {'error': self.message}
        body.update(self.extra)
        return jsonify(body), self.status


def _provided_key():
    """Read the key from a header or the query string (the latter for browser use)."""
    header = request.headers.get('X-API-Key')
    if header:
        return header.strip()

    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()

    return (request.args.get('key') or '').strip()


def require_key(fn):
    """Gate a route behind the shared phrase and turn ApiError into a JSON response."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        supplied = _provided_key()
        # Compare as bytes so a non-ASCII key can't blow up compare_digest.
        if not supplied or not hmac.compare_digest(supplied.encode('utf-8'), API_KEY.encode('utf-8')):
            return jsonify({
                'error': 'Invalid or missing key',
                'hint': "Pass the shared phrase as the X-API-Key header or a ?key= query param."
            }), 401

        try:
            return fn(*args, **kwargs)
        except ApiError as e:
            return e.to_response()
        except Exception as e:  # noqa: BLE001 - surface the reason, don't leak a stack trace
            print(f"Agent API error in {fn.__name__}: {e}")
            return jsonify({'error': 'Server error', 'detail': str(e)}), 500

    return wrapper


def body_json():
    """
    The request's JSON body as a dict, or {} if there isn't one.

    force=True matters: without it Flask refuses to parse a body whose
    Content-Type isn't application/json, which is an easy header to forget from
    curl and would otherwise make a perfectly good userId invisible.
    """
    payload = request.get_json(silent=True, force=True)
    return payload if isinstance(payload, dict) else {}


def require_user():
    """
    Resolve and verify the userId for this request.

    This is the only place a user id enters the system, and it never creates one:
    an id with no existing footprint is a 404, not an implicit signup.
    """
    user_id = request.args.get('userId')
    if not user_id:
        user_id = body_json().get('userId')

    if not user_id:
        raise ApiError(
            'userId required',
            400,
            hint='Call GET /api/agent/users to see the ids that exist.'
        )

    if not isinstance(user_id, str):
        raise ApiError(f'userId must be a string, got {user_id!r}', 400)

    if not db.user_exists(user_id):
        raise ApiError(
            f"Unknown user '{user_id}'",
            404,
            hint='This API never creates users. Call GET /api/agent/users to see the ids that exist.'
        )

    return user_id


# ============================================================================
# TIMEZONE + TIME HELPERS
# ============================================================================

def resolve_tz():
    """Resolve the request's IANA timezone, falling back to the configured default."""
    name = (request.args.get('tz') or '').strip()

    if not name:
        body_tz = body_json().get('tz')
        name = body_tz.strip() if isinstance(body_tz, str) else ''

    if not name:
        name = DEFAULT_TZ

    if ZoneInfo is None:
        raise ApiError('Server is missing zoneinfo support', 500)

    try:
        return ZoneInfo(name), name
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ApiError(
            f"Unknown timezone '{name}'",
            400,
            hint="Use an IANA name such as 'America/Los_Angeles' or 'UTC'."
        )


def now_ms():
    return int(time.time() * 1000)


def to_ms(dt):
    return int(dt.timestamp() * 1000)


def local_fields(timestamp_ms, tzinfo):
    """The local-time view of a stored UTC millisecond timestamp."""
    if timestamp_ms is None:
        return {'localTime': None, 'localDate': None}

    local = datetime.fromtimestamp(timestamp_ms / 1000, tzinfo)
    return {
        'localTime': local.isoformat(),
        'localDate': local.date().isoformat()
    }


def with_local(record, tzinfo, key='timestamp'):
    """Annotate a record with localTime/localDate alongside its raw ms timestamp."""
    enriched = dict(record)
    enriched.update(local_fields(record.get(key), tzinfo))
    return enriched


def day_bounds(date_str, tzinfo):
    """Half-open [start, end) millisecond bounds of a local calendar day."""
    try:
        day = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise ApiError(f"Invalid date '{date_str}' — expected YYYY-MM-DD", 400)

    start = datetime.combine(day, dtime.min, tzinfo)
    end = datetime.combine(day + timedelta(days=1), dtime.min, tzinfo)
    return to_ms(start), to_ms(end)


def parse_when(value, tzinfo, field='when'):
    """
    Turn a caller-supplied instant into epoch milliseconds.

    Accepts epoch milliseconds, epoch seconds, a full ISO 8601 datetime (its own
    offset wins if present, otherwise it is read as local to tzinfo), or a bare
    YYYY-MM-DD, which lands at local noon so it can't drift across a day boundary.
    """
    if value is None:
        return now_ms()

    if isinstance(value, bool):
        raise ApiError(f"Invalid {field}: expected a timestamp, got a boolean", 400)

    if isinstance(value, (int, float)):
        # Anything below 1e11 is far too small to be milliseconds, so read it as seconds.
        return int(value * 1000) if abs(value) < 1e11 else int(value)

    if not isinstance(value, str):
        raise ApiError(f"Invalid {field}: expected a string or number", 400)

    text = value.strip()
    if not text:
        return now_ms()

    if text.lower() == 'now':
        return now_ms()

    if text.lstrip('-').isdigit():
        return parse_when(int(text), tzinfo, field)

    # Bare calendar date -> local noon.
    try:
        day = date.fromisoformat(text)
        return to_ms(datetime.combine(day, dtime(12, 0), tzinfo))
    except ValueError:
        pass

    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        raise ApiError(
            f"Invalid {field}: '{value}'",
            400,
            hint='Use epoch milliseconds, "YYYY-MM-DD", or an ISO 8601 datetime.'
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tzinfo)

    return to_ms(parsed)


def resolve_range(tzinfo):
    """
    Work out the [start, end) millisecond window a read request is asking for.

    Supports ?date=YYYY-MM-DD (one local day), ?start=&end= (a span, where a bare
    end date means through the end of that day), or ?days=N (the last N local days
    including today). Defaults to the last 7 days.
    """
    date_arg = request.args.get('date')
    start_arg = request.args.get('start')
    end_arg = request.args.get('end')
    days_arg = request.args.get('days')

    if date_arg:
        return day_bounds(date_arg, tzinfo)

    if start_arg or end_arg:
        # Decide by shape, so a malformed date reports as a bad date rather than
        # falling through and complaining about datetime format instead.
        if start_arg:
            start_ms = (day_bounds(start_arg, tzinfo)[0] if PLAIN_DATE_RE.match(start_arg)
                        else parse_when(start_arg, tzinfo, 'start'))
        else:
            start_ms = 0

        if end_arg:
            # A bare end date means "through the end of that day".
            end_ms = (day_bounds(end_arg, tzinfo)[1] if PLAIN_DATE_RE.match(end_arg)
                      else parse_when(end_arg, tzinfo, 'end'))
        else:
            end_ms = day_bounds(datetime.now(tzinfo).date().isoformat(), tzinfo)[1]

        if end_ms <= start_ms:
            raise ApiError('end must be after start', 400)

        return start_ms, end_ms

    try:
        days = int(days_arg) if days_arg else 7
    except (TypeError, ValueError):
        raise ApiError(f"Invalid days '{days_arg}' — expected an integer", 400)

    if days < 1:
        raise ApiError('days must be at least 1', 400)

    today = datetime.now(tzinfo).date()
    start_ms, _ = day_bounds((today - timedelta(days=days - 1)).isoformat(), tzinfo)
    _, end_ms = day_bounds(today.isoformat(), tzinfo)
    return start_ms, end_ms


def resolve_limit():
    raw = request.args.get('limit')
    if not raw:
        return DEFAULT_LIMIT
    try:
        limit = int(raw)
    except ValueError:
        raise ApiError(f"Invalid limit '{raw}' — expected an integer", 400)

    if limit < 1:
        raise ApiError('limit must be at least 1', 400)

    return min(limit, MAX_LIMIT)


# ============================================================================
# VALIDATION
# ============================================================================

def json_body():
    payload = request.get_json(silent=True, force=True)
    if not isinstance(payload, dict):
        raise ApiError('Expected a JSON object body', 400)
    return payload


def resolve_event_type(event_type_id, user_id):
    """
    Fetch an event type and confirm this user is allowed to use it.

    System types (user_id IS NULL) are shared; custom types belong to one user.
    """
    event_type = db.get_event_type(event_type_id)
    if not event_type:
        raise ApiError(
            f"Unknown eventTypeId '{event_type_id}'",
            404,
            hint='Call GET /api/agent/schema to see the event types this user tracks.'
        )

    owner = event_type.get('userId')
    if owner is not None and owner != user_id:
        raise ApiError(f"Event type '{event_type_id}' belongs to another user", 403)

    return event_type


def validate_event_data(event_type, data):
    """
    Check an event's data payload against its type's field schema.

    Rejecting rather than warning is deliberate: events.data is unconstrained
    JSONB, so a misspelled field name would write a row that looks saved but
    never appears in any chart. The schema goes back in the error so the caller
    can correct itself.
    """
    if not isinstance(data, dict):
        raise ApiError('data must be a JSON object', 400)

    fields = (event_type.get('fieldSchema') or {}).get('fields', [])
    if not fields:
        return data

    # Field schemas for custom types are user-authored, so tolerate malformed entries.
    by_name = {f['name']: f for f in fields if isinstance(f, dict) and f.get('name')}
    errors = []

    unknown = [k for k in data if k not in by_name]
    if unknown:
        errors.append(f"Unknown field(s): {', '.join(sorted(unknown))}")

    for name, field in by_name.items():
        if field.get('required') and (name not in data or data[name] is None or data[name] == ''):
            errors.append(f"Missing required field '{name}'")

    cleaned = {}
    for name, value in data.items():
        field = by_name.get(name)
        if not field:
            continue

        ftype = field.get('type')
        if ftype == 'number' and value is not None:
            try:
                cleaned[name] = float(value)
            except (TypeError, ValueError):
                errors.append(f"Field '{name}' must be a number, got {value!r}")
                cleaned[name] = value
        elif ftype == 'enum' and value is not None:
            allowed = field.get('values', [])
            if allowed and value not in allowed:
                errors.append(f"Field '{name}' must be one of: {', '.join(map(str, allowed))}")
            cleaned[name] = value
        else:
            cleaned[name] = value

    if errors:
        raise ApiError(
            'Event data does not match the event type schema',
            400,
            details=errors,
            eventTypeId=event_type['id'],
            fieldSchema=event_type.get('fieldSchema')
        )

    return cleaned


def validate_nutrition(nutrition):
    if nutrition is None:
        return {}
    if not isinstance(nutrition, dict):
        raise ApiError('nutrition must be a JSON object', 400)

    unknown = [k for k in nutrition if k not in NUTRITION_KEYS]
    if unknown:
        raise ApiError(
            f"Unknown nutrition field(s): {', '.join(sorted(unknown))}",
            400,
            allowedFields=NUTRITION_KEYS
        )

    cleaned = {}
    for key, value in nutrition.items():
        if value is None:
            continue
        try:
            cleaned[key] = float(value)
        except (TypeError, ValueError):
            raise ApiError(f"Nutrition field '{key}' must be a number, got {value!r}", 400)

    return cleaned


# ============================================================================
# DISCOVERY ROUTES
# ============================================================================

@agent_api.route('/api/agent', methods=['GET'])
@require_key
def agent_index():
    """Self-documenting index — the entry point for a caller that knows nothing."""
    return jsonify({
        'name': 'lifestats remote API',
        'version': '1',
        'auth': {
            'how': 'X-API-Key header, Authorization: Bearer, or ?key= query param',
            'note': 'Shared phrase, configured server-side via LIFESTATS_API_KEY.'
        },
        'users': {
            'note': 'Every route needs a userId that already exists. This API never creates users.',
            'discover': 'GET /api/agent/users'
        },
        'time': {
            'storage': 'All timestamps are epoch milliseconds, UTC.',
            'tz': "Pass ?tz= as an IANA name (e.g. America/New_York) to control how local dates are read and returned.",
            'defaultTz': DEFAULT_TZ,
            'writes': 'The "when" field accepts epoch ms, "YYYY-MM-DD" (local noon), an ISO 8601 datetime, or "now".',
            'reads': 'Use ?date=YYYY-MM-DD, ?start=&end=, or ?days=N. Windows are half-open [start, end).',
            'responses': 'Every record carries raw timestamp (ms) plus localTime and localDate.'
        },
        'endpoints': [
            {'method': 'GET', 'path': '/api/agent', 'description': 'This index.'},
            {'method': 'GET', 'path': '/api/agent/users', 'description': 'User ids that exist, with activity counts.'},
            {'method': 'GET', 'path': '/api/agent/schema',
             'params': ['userId', 'tz'],
             'description': "Everything this user tracks: categories, event types with their field schemas, goals, profile."},
            {'method': 'GET', 'path': '/api/agent/summary',
             'params': ['userId', 'tz', 'date | start+end | days'],
             'description': 'Per-day nutrition totals and event aggregates, with goal progress.'},
            {'method': 'GET', 'path': '/api/agent/meals',
             'params': ['userId', 'tz', 'date | start+end | days', 'limit'],
             'description': 'Logged meals in a window.'},
            {'method': 'POST', 'path': '/api/agent/meals',
             'body': ['userId', 'foodName', 'mealType', 'nutrition', 'servingSize', 'servingUnit', 'brandName', 'when', 'tz'],
             'description': 'Log a meal.'},
            {'method': 'PATCH', 'path': '/api/agent/meals/<mealId>',
             'params': ['userId'], 'description': 'Update a logged meal.'},
            {'method': 'DELETE', 'path': '/api/agent/meals/<mealId>',
             'params': ['userId'], 'description': 'Delete a logged meal.'},
            {'method': 'GET', 'path': '/api/agent/events',
             'params': ['userId', 'tz', 'eventTypeId', 'category', 'date | start+end | days', 'limit'],
             'description': 'Logged events in a window.'},
            {'method': 'POST', 'path': '/api/agent/events',
             'body': ['userId', 'eventTypeId', 'data', 'when', 'notes', 'tz'],
             'description': 'Log an event. data is validated against the event type field schema.'},
            {'method': 'PATCH', 'path': '/api/agent/events/<eventId>',
             'params': ['userId'], 'description': 'Update a logged event.'},
            {'method': 'DELETE', 'path': '/api/agent/events/<eventId>',
             'params': ['userId'], 'description': 'Delete a logged event.'},
        ],
        'notThroughThisApi': {
            'createUser': 'Users are created only by opening the app in a browser.',
            'createEventType': 'Define new event types or categories in the app UI.',
            'foodLookup': 'Use the existing GET /api/search-food?query=... to find nutrition data before logging.'
        }
    })


@agent_api.route('/api/agent/users', methods=['GET'])
@require_key
def agent_users():
    """List the user ids that exist, so a caller can identify which one is theirs."""
    tzinfo, tz_name = resolve_tz()
    users = db.list_known_users()

    return jsonify({
        'timezone': tz_name,
        'count': len(users),
        'users': [with_local(u, tzinfo, key='lastActivity') for u in users]
    })


@agent_api.route('/api/agent/schema', methods=['GET'])
@require_key
def agent_schema():
    """
    What this user tracks: their categories, every event type available to them
    with its field schema, their goals and profile. Call this before writing —
    it is where the exact field names for an event's data payload come from.
    """
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()

    event_types = db.get_event_types(user_id=user_id)
    categories = db.get_user_categories(user_id)
    goals = db.get_user_goals(user_id)
    profile = db.get_user_profile(user_id)
    data_range = db.get_user_data_range(user_id)

    # Categories in use, whether or not the user created a custom entry for them.
    category_names = sorted({et['category'] for et in event_types if et.get('category')})
    custom_by_name = {c['name']: c for c in categories}

    return jsonify({
        'userId': user_id,
        'timezone': tz_name,
        'now': {'timestamp': now_ms(), **local_fields(now_ms(), tzinfo)},
        'dataRange': {
            'first': data_range['first'],
            'firstLocalDate': local_fields(data_range['first'], tzinfo)['localDate'],
            'last': data_range['last'],
            'lastLocalDate': local_fields(data_range['last'], tzinfo)['localDate']
        },
        'categories': [{
            'name': name,
            'icon': custom_by_name.get(name, {}).get('icon'),
            'isCustom': name in custom_by_name,
            'eventTypeIds': [et['id'] for et in event_types if et.get('category') == name]
        } for name in category_names],
        'eventTypes': [{
            'id': et['id'],
            'name': et['name'],
            'category': et['category'],
            'icon': et['icon'],
            'isCustom': et['userId'] is not None,
            'isFavorite': et['isFavorite'],
            'aggregationType': et['aggregationType'],
            'primaryUnit': et['primaryUnit'],
            'trackingType': et['trackingType'],
            'fieldSchema': et['fieldSchema'],
            'lastUsed': et['lastUsed'],
            'lastUsedLocalDate': local_fields(et['lastUsed'], tzinfo)['localDate'] if et['lastUsed'] else None
        } for et in event_types],
        'goals': goals,
        'profile': profile,
        'mealFields': {
            'required': ['foodName', 'mealType'],
            'mealTypes': MEAL_TYPES,
            'optional': ['brandName', 'servingSize', 'servingUnit', 'when'],
            'nutrition': NUTRITION_KEYS,
            'note': "Meals live in their own table, not in events. Log them via POST /api/agent/meals."
        }
    })


# ============================================================================
# SUMMARY ROUTES
# ============================================================================

@agent_api.route('/api/agent/summary', methods=['GET'])
@require_key
def agent_summary():
    """Per-day totals across the requested window, with goal progress attached."""
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    start_ms, end_ms = resolve_range(tzinfo)

    goals = {g['eventTypeId']: g for g in db.get_user_goals(user_id)}

    first_day = datetime.fromtimestamp(start_ms / 1000, tzinfo).date()
    last_day = datetime.fromtimestamp((end_ms - 1) / 1000, tzinfo).date()

    span = (last_day - first_day).days + 1
    if span > MAX_SUMMARY_DAYS:
        raise ApiError(
            f"Range covers {span} days; the maximum is {MAX_SUMMARY_DAYS}",
            400,
            hint='Request a narrower range, or use /api/agent/events for raw rows.'
        )

    days = []
    cursor = first_day

    while cursor <= last_day:
        day_start, day_end = day_bounds(cursor.isoformat(), tzinfo)
        stats = db.get_todays_stats(user_id, day_start, day_end)

        totals = {}
        for stat_id, stat in stats.items():
            entry = {'value': stat['value'], 'unit': stat['unit']}
            goal = goals.get(stat_id)
            if goal:
                entry['goal'] = goal['targetValue']
                entry['goalPeriod'] = goal.get('period', 'daily')
            totals[stat_id] = entry

        days.append({
            'date': cursor.isoformat(),
            'start': day_start,
            'end': day_end,
            'totals': totals
        })
        cursor += timedelta(days=1)

    return jsonify({
        'userId': user_id,
        'timezone': tz_name,
        'range': {
            'start': start_ms,
            'end': end_ms,
            'startLocalDate': local_fields(start_ms, tzinfo)['localDate'],
            'endLocalDate': local_fields(end_ms - 1, tzinfo)['localDate']
        },
        'days': days,
        'note': "The 'meal' total is calories; protein/carbs/fat appear alongside it."
    })


# ============================================================================
# MEAL ROUTES
# ============================================================================

@agent_api.route('/api/agent/meals', methods=['GET'])
@require_key
def agent_get_meals():
    """Meals logged inside the requested local window."""
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    start_ms, end_ms = resolve_range(tzinfo)
    limit = resolve_limit()

    meals = db.get_meals_in_range(user_id, start_ms, end_ms, limit)

    return jsonify({
        'userId': user_id,
        'timezone': tz_name,
        'range': {'start': start_ms, 'end': end_ms},
        'count': len(meals),
        'meals': [with_local(m, tzinfo) for m in meals]
    })


@agent_api.route('/api/agent/meals', methods=['POST'])
@require_key
def agent_create_meal():
    """Log a meal for an existing user."""
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    payload = json_body()

    food_name = (payload.get('foodName') or '').strip()
    if not food_name:
        raise ApiError('foodName required', 400)

    meal_type = (payload.get('mealType') or '').strip().lower()
    if meal_type not in MEAL_TYPES:
        raise ApiError(
            f"Invalid mealType '{payload.get('mealType')}'",
            400,
            allowedValues=MEAL_TYPES
        )

    timestamp = parse_when(payload.get('when', payload.get('timestamp')), tzinfo)
    nutrition = validate_nutrition(payload.get('nutrition'))

    try:
        serving_size = float(payload.get('servingSize', 1.0))
    except (TypeError, ValueError):
        raise ApiError(f"servingSize must be a number, got {payload.get('servingSize')!r}", 400)

    meal = {
        'id': f"meal-{now_ms()}-{uuid.uuid4().hex[:6]}",
        'userId': user_id,
        'foodName': food_name,
        'brandName': payload.get('brandName'),
        'mealType': meal_type,
        'nutrition': nutrition,
        'servingSize': serving_size,
        'servingUnit': payload.get('servingUnit', 'serving'),
        'timestamp': timestamp
    }

    db.add_meal(meal)

    return jsonify({
        'success': True,
        'timezone': tz_name,
        'meal': with_local(meal, tzinfo)
    }), 201


@agent_api.route('/api/agent/meals/<meal_id>', methods=['PATCH'])
@require_key
def agent_update_meal(meal_id):
    """Update fields on a meal the user owns."""
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    payload = json_body()

    updates = {}

    if 'foodName' in payload:
        updates['foodName'] = payload['foodName']
    if 'brandName' in payload:
        updates['brandName'] = payload['brandName']
    if 'servingSize' in payload:
        updates['servingSize'] = payload['servingSize']
    if 'servingUnit' in payload:
        updates['servingUnit'] = payload['servingUnit']

    if 'mealType' in payload:
        meal_type = (payload.get('mealType') or '').strip().lower()
        if meal_type not in MEAL_TYPES:
            raise ApiError(
                f"Invalid mealType '{payload.get('mealType')}'",
                400,
                allowedValues=MEAL_TYPES
            )
        updates['mealType'] = meal_type

    if 'when' in payload or 'timestamp' in payload:
        updates['timestamp'] = parse_when(payload.get('when', payload.get('timestamp')), tzinfo)

    if 'nutrition' in payload:
        updates['nutrition'] = validate_nutrition(payload['nutrition'])

    if not updates:
        raise ApiError(
            'No recognized fields to update',
            400,
            allowedFields=['foodName', 'brandName', 'mealType', 'servingSize', 'servingUnit', 'when', 'nutrition']
        )

    if not db.get_meal(meal_id, user_id):
        raise ApiError(f"Meal '{meal_id}' not found for this user", 404)

    if not db.update_meal(meal_id, user_id, updates):
        raise ApiError(f"Meal '{meal_id}' was not updated", 400)

    updated = db.get_meal(meal_id, user_id)

    return jsonify({
        'success': True,
        'timezone': tz_name,
        'meal': with_local(updated, tzinfo)
    })


@agent_api.route('/api/agent/meals/<meal_id>', methods=['DELETE'])
@require_key
def agent_delete_meal(meal_id):
    """Delete a meal the user owns."""
    user_id = require_user()

    if not db.delete_meal(meal_id, user_id):
        raise ApiError(f"Meal '{meal_id}' not found for this user", 404)

    return jsonify({'success': True, 'deleted': meal_id})


# ============================================================================
# EVENT ROUTES
# ============================================================================

@agent_api.route('/api/agent/events', methods=['GET'])
@require_key
def agent_get_events():
    """Events logged inside the requested local window, optionally filtered."""
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    start_ms, end_ms = resolve_range(tzinfo)

    filters = {
        'startDate': start_ms,
        # get_events treats endDate as inclusive; keep our window half-open.
        'endDate': end_ms - 1,
        'limit': resolve_limit()
    }
    if request.args.get('eventTypeId'):
        filters['eventTypeId'] = request.args.get('eventTypeId')
    if request.args.get('category'):
        filters['category'] = request.args.get('category')

    events = db.get_events(user_id, filters)

    return jsonify({
        'userId': user_id,
        'timezone': tz_name,
        'range': {'start': start_ms, 'end': end_ms},
        'count': len(events),
        'events': [with_local(e, tzinfo) for e in events]
    })


@agent_api.route('/api/agent/events', methods=['POST'])
@require_key
def agent_create_event():
    """
    Log an event. The data payload is validated against the event type's field
    schema, and the category comes from the resolved type rather than the caller.
    """
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    payload = json_body()

    event_type_id = (payload.get('eventTypeId') or '').strip()
    if not event_type_id:
        raise ApiError(
            'eventTypeId required',
            400,
            hint='Call GET /api/agent/schema to list the event types this user tracks.'
        )

    if event_type_id == 'meal':
        raise ApiError(
            "Meals are not stored as events",
            400,
            hint='Use POST /api/agent/meals instead.'
        )

    event_type = resolve_event_type(event_type_id, user_id)
    data = validate_event_data(event_type, payload.get('data') or {})

    event = {
        'id': f"evt_{uuid.uuid4().hex[:12]}",
        'userId': user_id,
        'eventTypeId': event_type_id,
        'timestamp': parse_when(payload.get('when', payload.get('timestamp')), tzinfo),
        # Derived, not caller-supplied: a mismatched category orphans the row.
        'category': event_type['category'],
        'data': data,
        'notes': payload.get('notes', '')
    }

    saved = db.log_event(event)

    return jsonify({
        'success': True,
        'timezone': tz_name,
        'event': with_local(saved, tzinfo)
    }), 201


@agent_api.route('/api/agent/events/<event_id>', methods=['PATCH'])
@require_key
def agent_update_event(event_id):
    """Update the data, notes, or time of an event the user owns."""
    user_id = require_user()
    tzinfo, tz_name = resolve_tz()
    payload = json_body()

    existing = db.get_event(event_id, user_id)
    if not existing:
        raise ApiError(f"Event '{event_id}' not found for this user", 404)

    updates = {}

    if 'data' in payload:
        event_type = resolve_event_type(existing['eventTypeId'], user_id)
        # Merge onto the stored data so a partial update can't drop required fields.
        merged = dict(existing.get('data') or {})
        incoming = payload['data']
        if not isinstance(incoming, dict):
            raise ApiError('data must be a JSON object', 400)
        merged.update(incoming)
        updates['data'] = validate_event_data(event_type, merged)

    if 'notes' in payload:
        updates['notes'] = payload['notes']

    if 'when' in payload or 'timestamp' in payload:
        updates['timestamp'] = parse_when(payload.get('when', payload.get('timestamp')), tzinfo)

    if not updates:
        raise ApiError('No recognized fields to update', 400, allowedFields=['data', 'notes', 'when'])

    if not db.update_event(event_id, user_id, updates):
        raise ApiError(f"Event '{event_id}' was not updated", 400)

    updated = db.get_event(event_id, user_id)

    return jsonify({
        'success': True,
        'timezone': tz_name,
        'event': with_local(updated, tzinfo)
    })


@agent_api.route('/api/agent/events/<event_id>', methods=['DELETE'])
@require_key
def agent_delete_event(event_id):
    """Delete an event the user owns."""
    user_id = require_user()

    if not db.delete_event(event_id, user_id):
        raise ApiError(f"Event '{event_id}' not found for this user", 404)

    return jsonify({'success': True, 'deleted': event_id})
