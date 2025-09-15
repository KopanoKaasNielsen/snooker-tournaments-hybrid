#!/usr/bin/env bash
set -euo pipefail
BASE=http://127.0.0.1:8000
echo '=== List players ==='
curl -s $BASE/players/ | jq '.'
echo
echo '=== Create tournament ==='
curl -s -X POST $BASE/tournaments/ -H 'Content-Type: application/json' -d '{ "name":"Curl Test Open", "type":"knockout", "date":"2025-09-15T12:00:00", "best_of":5, "race_to":3, "entry_fee":50 }' | jq '.'
echo
echo '=== Register player (existing id 1) ==='
curl -s -X POST $BASE/tournaments/1/register -H 'Content-Type: application/json' -d '{ "player_id": 1 }' | jq '.' || true
echo
echo '=== Complete tournament (example) ==='
curl -s -X POST $BASE/tournaments/1/complete -H 'Content-Type: application/json' -d '[{ "player_id": 1, "position": 1 }, { "player_id": 2, "position": 2 }]' | jq '.' || true
