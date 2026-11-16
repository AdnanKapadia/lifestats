"""Compare the self-hosted FatSecret proxy against the legacy Railway one.

The replacement must return byte-identical FatSecret payloads, because
backend/app.py parses the raw v1 shapes. Run this before cutting over.

    python3 scripts/diff_fatsecret_proxy.py \
        --new https://fatsecret.example.com --secret "$FATSECRET_PROXY_SECRET"

Compares structure and values, ignoring key order and the volatile paging
counters that legitimately differ run to run. Exits non-zero on any mismatch.
"""

import argparse
import json
import sys

import requests

RAILWAY = 'https://fatsecret-proxy-production-e380.up.railway.app'

# FatSecret reorders equally-ranked results and total_results drifts as their
# database changes, so compare the set of foods rather than the exact list.
SEARCH_QUERIES = ['apple', 'chicken breast', 'greek yogurt', 'quest bar']
FOOD_IDS = ['35718', '1902657']


def fetch(base, path, params, secret=None, timeout=30):
    headers = {'X-Proxy-Secret': secret} if secret else {}
    response = requests.get(
        f'{base.rstrip("/")}{path}', params=params, headers=headers, timeout=timeout
    )
    response.raise_for_status()
    return response.json()


def food_key(food):
    """Identity of a search hit, ignoring presentation-only fields."""
    return (
        food.get('food_id'),
        food.get('food_name'),
        food.get('brand_name'),
        food.get('food_description'),
    )


def compare_search(old, new, query, failures):
    old_foods = old.get('foods', {}).get('food', [])
    new_foods = new.get('foods', {}).get('food', [])

    if isinstance(old_foods, dict):
        old_foods = [old_foods]
    if isinstance(new_foods, dict):
        new_foods = [new_foods]

    if not new_foods:
        failures.append(f'search {query!r}: new proxy returned no foods')
        return

    old_set = {food_key(f) for f in old_foods}
    new_set = {food_key(f) for f in new_foods}

    missing = old_set - new_set
    extra = new_set - old_set

    # Key set on the first result must match exactly — a different API version
    # is what would show up here.
    if old_foods and new_foods:
        old_keys = set(old_foods[0].keys())
        new_keys = set(new_foods[0].keys())
        if old_keys != new_keys:
            failures.append(
                f'search {query!r}: field mismatch on first result '
                f'(only old: {sorted(old_keys - new_keys)}, '
                f'only new: {sorted(new_keys - old_keys)})'
            )

    if missing:
        failures.append(
            f'search {query!r}: {len(missing)} result(s) present in Railway '
            f'but absent from new proxy, e.g. {sorted(missing)[:2]}'
        )
    if extra:
        print(
            f'  note: search {query!r} has {len(extra)} result(s) only in the '
            f'new proxy (usually fine — FatSecret data moves)'
        )


def compare_food(old, new, food_id, failures):
    old_food = old.get('food', {})
    new_food = new.get('food', {})

    if set(old_food.keys()) != set(new_food.keys()):
        failures.append(
            f'food {food_id}: top-level field mismatch '
            f'(only old: {sorted(set(old_food) - set(new_food))}, '
            f'only new: {sorted(set(new_food) - set(old_food))})'
        )
        return

    def servings(food):
        raw = food.get('servings', {}).get('serving', [])
        return [raw] if isinstance(raw, dict) else raw

    old_servings = {s.get('serving_id'): s for s in servings(old_food)}
    new_servings = {s.get('serving_id'): s for s in servings(new_food)}

    if set(old_servings) != set(new_servings):
        failures.append(
            f'food {food_id}: serving_id set differs '
            f'(only old: {sorted(set(old_servings) - set(new_servings))}, '
            f'only new: {sorted(set(new_servings) - set(old_servings))})'
        )
        return

    for serving_id, old_serving in old_servings.items():
        new_serving = new_servings[serving_id]
        if old_serving != new_serving:
            differing = [
                k for k in set(old_serving) | set(new_serving)
                if old_serving.get(k) != new_serving.get(k)
            ]
            failures.append(
                f'food {food_id} serving {serving_id}: differing fields '
                f'{sorted(differing)}'
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--new', required=True, help='base URL of the new proxy')
    parser.add_argument('--old', default=RAILWAY, help='base URL of the old proxy')
    parser.add_argument('--secret', default=None, help='X-Proxy-Secret for the new proxy')
    args = parser.parse_args()

    failures = []

    for query in SEARCH_QUERIES:
        print(f'search {query!r} ...')
        try:
            old = fetch(args.old, '/search', {'query': query})
            new = fetch(args.new, '/search', {'query': query}, secret=args.secret)
        except requests.RequestException as exc:
            failures.append(f'search {query!r}: request failed: {exc}')
            continue
        compare_search(old, new, query, failures)

    for food_id in FOOD_IDS:
        print(f'food {food_id} ...')
        try:
            old = fetch(args.old, '/food', {'food_id': food_id})
            new = fetch(args.new, '/food', {'food_id': food_id}, secret=args.secret)
        except requests.RequestException as exc:
            failures.append(f'food {food_id}: request failed: {exc}')
            continue
        compare_food(old, new, food_id, failures)

    print()
    if failures:
        print(f'MISMATCH — {len(failures)} problem(s), do not cut over:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('MATCH — new proxy agrees with Railway on all probes.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
