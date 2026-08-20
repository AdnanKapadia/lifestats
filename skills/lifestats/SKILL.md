---
name: lifestats
description: Read and write the user's lifestats food & fitness tracker (meals, weight, workouts, steps, and any custom event types they track). Use when the user wants to log something they ate or did, asks what they ate or logged on a given day, asks about calories/macros/weight/steps trends, or asks what they are currently tracking. Also use for correcting or deleting a previously logged entry.
---

# lifestats

Remote access to the user's personal tracking app at `https://lifestats-pi.vercel.app`.
Everything goes through the `/api/agent/*` API, which is plain JSON over HTTPS.

## Auth

Every request needs the shared phrase. Send it as a header:

```
X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}
```

The phrase is `foodtrack` — the default the deployed app ships with. Don't ask the user
for it. If `LIFESTATS_API_KEY` is set in the environment it overrides that default, so
write the examples below exactly as shown: `${LIFESTATS_API_KEY:-foodtrack}` uses the
override when present and falls back to `foodtrack` when it isn't.

A `?key=` query param also works and is handy for pasting a read URL into a browser;
prefer the header for anything you run yourself, since query strings land in server logs.

## The two rules that matter

1. **Call `GET /api/agent/schema` before your first write in a session.** It returns the
   exact field names each event type accepts. Guessed field names are rejected, and even
   if they weren't, a wrong key writes a row that never appears in the user's charts.
2. **Never invent a userId.** The API refuses unknown ids and cannot create users. Get the
   real one from `GET /api/agent/users`, and reuse it for the rest of the session.

## Orientation (do this first)

```bash
curl -s -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" \
  "https://lifestats-pi.vercel.app/api/agent/users"
```

Returns each known user id with meal/event counts and last activity. **The default user is
`Adnan`.** Note the list also contains a second real account (`Estefani`) plus a couple of
dozen abandoned test ids from development — so do not just take the first or only id you
see. Use `Adnan` unless the user says otherwise, and if they name someone else, match it
against the list rather than guessing. Writing to the wrong id puts their data on another
person's account. Then:

```bash
curl -s -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" \
  "https://lifestats-pi.vercel.app/api/agent/schema?userId=USER_ID&tz=America/Los_Angeles"
```

This is the map of everything the user tracks: their categories, every event type with its
`fieldSchema` (the field names, types, units, and which are required), their goals, profile,
and the date range of their data. `GET /api/agent` returns the full endpoint index if you
need to check a parameter.

## Time

- Stored timestamps are **epoch milliseconds, UTC**.
- Pass `tz` as an IANA name (`America/Los_Angeles`, `America/New_York`, `UTC`) on every
  request. It decides how local dates are interpreted *and* how they are echoed back. The
  server default is `America/Los_Angeles`. If the user's timezone is known, always pass it
  explicitly — do not rely on the default.
- Writing a time: `when` accepts `"now"`, epoch ms, an ISO 8601 datetime
  (`2026-08-19T19:30:00`, read as local unless it carries its own offset), or a bare
  `"2026-08-19"`, which lands at local noon. Omit `when` entirely to mean now.
- Reading a window: `?date=YYYY-MM-DD` for one local day, `?start=&end=` for a span (a bare
  end date means through the end of that day), or `?days=N` for the last N days including
  today. Windows are half-open, so adjacent days never double-count.
- Every returned record carries raw `timestamp` plus `localTime` and `localDate`. Quote
  local dates back to the user, not raw milliseconds.

## Meals vs events

Meals live in their own table with full nutrition columns — log them via `/api/agent/meals`.
Everything else (weight, steps, workouts, and any custom type the user made) is an event
via `/api/agent/events`, with a `data` object matching that type's `fieldSchema`.
Posting `eventTypeId: "meal"` to `/events` is rejected on purpose.

## Worked examples

**Log a meal.** Look up real nutrition first — don't invent numbers:

```bash
curl -s "https://lifestats-pi.vercel.app/api/search-food?query=greek%20yogurt"
```

Then post the one the user meant, scaling nutrition to the serving they actually ate:

```bash
curl -s -X POST "https://lifestats-pi.vercel.app/api/agent/meals" \
  -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" -H "Content-Type: application/json" \
  -d '{
    "userId": "USER_ID",
    "tz": "America/Los_Angeles",
    "foodName": "Greek Yogurt, plain nonfat",
    "brandName": "Fage",
    "mealType": "breakfast",
    "servingSize": 170,
    "servingUnit": "g",
    "when": "now",
    "nutrition": {"calories": 100, "protein": 18, "carbs": 6, "fat": 0}
  }'
```

`mealType` must be one of `breakfast`, `lunch`, `dinner`, `snack`.

**Log a weight** (field names come from `/schema` — check them, don't copy blindly):

```bash
curl -s -X POST "https://lifestats-pi.vercel.app/api/agent/events" \
  -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" -H "Content-Type: application/json" \
  -d '{
    "userId": "USER_ID",
    "tz": "America/Los_Angeles",
    "eventTypeId": "weight",
    "when": "2026-08-19T07:15:00",
    "data": {"weight": 171.2}
  }'
```

If the data doesn't match the schema, the 400 response includes the offending type's
`fieldSchema` — read it and retry with the right names rather than guessing again.

**What did I eat yesterday / how many calories:**

```bash
curl -s -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" \
  "https://lifestats-pi.vercel.app/api/agent/meals?userId=USER_ID&tz=America/Los_Angeles&date=2026-08-18"

curl -s -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" \
  "https://lifestats-pi.vercel.app/api/agent/summary?userId=USER_ID&tz=America/Los_Angeles&date=2026-08-18"
```

`/summary` gives per-day totals with goal progress attached. In its `totals`, `meal` is
calories, with `protein`/`carbs`/`fat` alongside; other keys are event type ids.

**Trend over the last two weeks:**

```bash
curl -s -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" \
  "https://lifestats-pi.vercel.app/api/agent/summary?userId=USER_ID&tz=America/Los_Angeles&days=14"
```

**Fix or remove an entry.** Find its id with a GET first, then:

```bash
curl -s -X PATCH "https://lifestats-pi.vercel.app/api/agent/meals/MEAL_ID?userId=USER_ID" \
  -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}" -H "Content-Type: application/json" \
  -d '{"nutrition": {"calories": 240}, "tz": "America/Los_Angeles"}'

curl -s -X DELETE "https://lifestats-pi.vercel.app/api/agent/events/EVENT_ID?userId=USER_ID" \
  -H "X-API-Key: ${LIFESTATS_API_KEY:-foodtrack}"
```

Event PATCH merges into existing `data`, so you can change one field without resending all.

## What this API deliberately cannot do

Creating users, defining new event types, and adding categories are app-UI operations. If
the user wants a new thing to track, tell them to create the event type in the app first,
then you can log to it.

## Behavior

- Deleting and overwriting are destructive — confirm with the user before a DELETE or a
  PATCH that overwrites data, and quote what you're about to change.
- When logging food, state the nutrition numbers you used and where they came from, so the
  user can correct them.
- If a request 404s on the user id, stop and re-run `/users`. Do not retry with a different
  id you made up.
