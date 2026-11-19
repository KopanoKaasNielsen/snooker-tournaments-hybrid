# Frontend API contract

Generated from `app.main:app.openapi()` using an isolated SQLite database. See [full schema](backend-openapi.json) for exact fields, defaults, validation and nullable types.

No route has authentication dependencies or OpenAPI security requirements. Public player IDs do not identify a signed-in user.

## Frontend requests

| Page | Method | Backend route | Request | Response |
|---|---|---|---|---|
| Dashboard | GET | `/tournaments/` | none | `Tournament[]` |
| Wallet selector | GET | `/players/` | none | `Player[]` |
| Wallet balance | GET | `/players/{player_id}/balance` | integer player ID | `PlayerBalanceOut` |
| Wallet history | GET | `/players/{player_id}/transactions` | integer player ID | Array of `{id, type, amount, timestamp}` from route implementation |

All frontend calls use the shared Axios client. Default `/api` is stripped by the Vite proxy. Production hosting must proxy `/api` similarly or set `VITE_API_BASE_URL` at build time. No financial mutations are exposed by the UI.

## All backend operations

| Method | Route | JSON body schema | Success response schema |
|---|---|---|---|
| GET | `/players/` | `{}` | `{"items": {"$ref": "#/components/schemas/Player"}, "type": "array", "title": "Response List Players Players  Get"}` |
| POST | `/players/` | `{"$ref": "#/components/schemas/PlayerCreate"}` | `{"$ref": "#/components/schemas/Player"}` |
| GET | `/players/leaderboard` | `{}` | `{"items": {"$ref": "#/components/schemas/PlayerOut"}, "type": "array", "title": "Response Get Leaderboard Players Leaderboard Get"}` |
| GET | `/players/{player_id}` | `{}` | `{"$ref": "#/components/schemas/Player"}` |
| POST | `/players/{player_id}/deposit` | `{"$ref": "#/components/schemas/WalletAmount"}` | `{"$ref": "#/components/schemas/PlayerBalanceOut"}` |
| POST | `/players/{player_id}/withdraw` | `{"$ref": "#/components/schemas/WalletAmount"}` | `{"$ref": "#/components/schemas/PlayerBalanceOut"}` |
| GET | `/players/{player_id}/balance` | `{}` | `{"$ref": "#/components/schemas/PlayerBalanceOut"}` |
| GET | `/players/{player_id}/elo` | `{}` | `{"$ref": "#/components/schemas/PlayerEloOut"}` |
| GET | `/players/{player_id}/transactions` | `{}` | `{}` |
| GET | `/tournaments/` | `{}` | `{"items": {"$ref": "#/components/schemas/Tournament"}, "type": "array", "title": "Response List Tournaments Tournaments  Get"}` |
| POST | `/tournaments/` | `{"$ref": "#/components/schemas/TournamentCreate"}` | `{"$ref": "#/components/schemas/Tournament"}` |
| POST | `/tournaments/{tournament_id}/register` | `{"$ref": "#/components/schemas/TournamentRegistrationCreate"}` | `{}` |
| POST | `/tournaments/{tournament_id}/complete` | `{"type": "array", "items": {"$ref": "#/components/schemas/WinnerCreate"}, "title": "Winners"}` | `{"type": "array", "items": {"$ref": "#/components/schemas/TournamentResult"}, "title": "Response Complete Tournament Tournaments  Tournament Id  Complete Post"}` |
| GET | `/matches/` | `{}` | `{"items": {"$ref": "#/components/schemas/Match"}, "type": "array", "title": "Response List Matches Matches  Get"}` |
| POST | `/matches/` | `{"$ref": "#/components/schemas/MatchCreate"}` | `{"$ref": "#/components/schemas/Match"}` |
| POST | `/matches/{match_id}/result` | `{"$ref": "#/components/schemas/MatchResult"}` | `{"$ref": "#/components/schemas/Match"}` |
| GET | `/health` | `{}` | `{}` |

Empty response schemas above mean the route has no declared response model, not that it returns no data. Registration returns a registration ORM record; transactions return the array described above. Health returns `{ "ok": true }`. Inspect `app/routes` and `app/crud.py` for untyped registration behavior.

## Capability gaps

- `/auth/login` and `/users/me` do not exist. No tokens, session cookies, logout API, authentication guards or current-user profile exist. The provider makes no network calls and stores no credentials. Profile supports injected data for existing tests only; the real provider supplies no user.
- No settings persistence, notification settings, favourite cue, email, world ranking, venue readiness, ticket revenue or sponsorship API exists.
- Player balance is numeric with no currency metadata. The UI does not assume GBP or label public records as personal accounts.
- Dashboard uses tournament records; no live fixture scheduling or real-time transport is claimed.
- Wallet reads are public. Do not deploy publicly without a separate access-control review. Deposit/withdraw/registration/completion routes mutate financial data and remain outside this frontend task.
- 401 errors explain access denial, network failures offer retry. No invented login redirect or automatic token handling is added.

## Principal schemas

### HTTPValidationError

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "type": "array",
      "title": "Detail"
    }
  },
  "type": "object",
  "title": "HTTPValidationError"
}
```

### Match

```json
{
  "properties": {
    "tournament_id": {
      "type": "integer",
      "title": "Tournament Id"
    },
    "player1_id": {
      "type": "integer",
      "title": "Player1 Id"
    },
    "player2_id": {
      "type": "integer",
      "title": "Player2 Id"
    },
    "scheduled_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Scheduled At"
    },
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "score_player1": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Score Player1",
      "default": 0
    },
    "score_player2": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Score Player2",
      "default": 0
    },
    "winner_id": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Winner Id"
    },
    "completed_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Completed At"
    }
  },
  "type": "object",
  "required": [
    "tournament_id",
    "player1_id",
    "player2_id",
    "id"
  ],
  "title": "Match"
}
```

### MatchCreate

```json
{
  "properties": {
    "tournament_id": {
      "type": "integer",
      "title": "Tournament Id"
    },
    "player1_id": {
      "type": "integer",
      "title": "Player1 Id"
    },
    "player2_id": {
      "type": "integer",
      "title": "Player2 Id"
    },
    "scheduled_at": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Scheduled At"
    }
  },
  "type": "object",
  "required": [
    "tournament_id",
    "player1_id",
    "player2_id"
  ],
  "title": "MatchCreate"
}
```

### MatchResult

```json
{
  "properties": {
    "score_player1": {
      "type": "integer",
      "title": "Score Player1"
    },
    "score_player2": {
      "type": "integer",
      "title": "Score Player2"
    },
    "winner_id": {
      "type": "integer",
      "title": "Winner Id"
    }
  },
  "type": "object",
  "required": [
    "score_player1",
    "score_player2",
    "winner_id"
  ],
  "title": "MatchResult",
  "description": "Used to report the result of a match."
}
```

### Player

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "rating": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Rating",
      "default": 1500
    },
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "name",
    "id",
    "created_at"
  ],
  "title": "Player"
}
```

### PlayerBalanceOut

```json
{
  "properties": {
    "player_id": {
      "type": "integer",
      "title": "Player Id"
    },
    "balance": {
      "type": "number",
      "title": "Balance"
    }
  },
  "type": "object",
  "required": [
    "player_id",
    "balance"
  ],
  "title": "PlayerBalanceOut"
}
```

### PlayerCreate

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "rating": {
      "type": "integer",
      "title": "Rating",
      "default": 1500
    }
  },
  "type": "object",
  "required": [
    "name"
  ],
  "title": "PlayerCreate"
}
```

### PlayerEloOut

```json
{
  "properties": {
    "player_id": {
      "type": "integer",
      "title": "Player Id"
    },
    "elo": {
      "type": "integer",
      "title": "Elo"
    }
  },
  "type": "object",
  "required": [
    "player_id",
    "elo"
  ],
  "title": "PlayerEloOut"
}
```

### PlayerOut

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "name": {
      "type": "string",
      "title": "Name"
    },
    "elo": {
      "type": "integer",
      "title": "Elo"
    },
    "balance": {
      "type": "number",
      "title": "Balance"
    }
  },
  "type": "object",
  "required": [
    "id",
    "name",
    "elo",
    "balance"
  ],
  "title": "PlayerOut"
}
```

### Tournament

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "type": {
      "type": "string",
      "title": "Type",
      "description": "league|knockout|double_elimination"
    },
    "date": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Date"
    },
    "entry_fee": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Entry Fee",
      "default": 0
    },
    "best_of": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Best Of",
      "default": 3
    },
    "race_to": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Race To"
    },
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "status": {
      "type": "string",
      "title": "Status"
    }
  },
  "type": "object",
  "required": [
    "name",
    "type",
    "id",
    "status"
  ],
  "title": "Tournament"
}
```

### TournamentCreate

```json
{
  "properties": {
    "name": {
      "type": "string",
      "title": "Name"
    },
    "type": {
      "type": "string",
      "title": "Type",
      "description": "league|knockout|double_elimination"
    },
    "date": {
      "anyOf": [
        {
          "type": "string",
          "format": "date-time"
        },
        {
          "type": "null"
        }
      ],
      "title": "Date"
    },
    "entry_fee": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Entry Fee",
      "default": 0
    },
    "best_of": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Best Of",
      "default": 3
    },
    "race_to": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "title": "Race To"
    }
  },
  "type": "object",
  "required": [
    "name",
    "type"
  ],
  "title": "TournamentCreate"
}
```

### TournamentRegistrationCreate

```json
{
  "properties": {
    "player_id": {
      "type": "integer",
      "title": "Player Id"
    }
  },
  "type": "object",
  "required": [
    "player_id"
  ],
  "title": "TournamentRegistrationCreate"
}
```

### TournamentResult

```json
{
  "properties": {
    "id": {
      "type": "integer",
      "title": "Id"
    },
    "tournament_id": {
      "type": "integer",
      "title": "Tournament Id"
    },
    "player_id": {
      "type": "integer",
      "title": "Player Id"
    },
    "position": {
      "type": "integer",
      "title": "Position"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "title": "Created At"
    }
  },
  "type": "object",
  "required": [
    "id",
    "tournament_id",
    "player_id",
    "position",
    "created_at"
  ],
  "title": "TournamentResult"
}
```

### ValidationError

```json
{
  "properties": {
    "loc": {
      "items": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "integer"
          }
        ]
      },
      "type": "array",
      "title": "Location"
    },
    "msg": {
      "type": "string",
      "title": "Message"
    },
    "type": {
      "type": "string",
      "title": "Error Type"
    }
  },
  "type": "object",
  "required": [
    "loc",
    "msg",
    "type"
  ],
  "title": "ValidationError"
}
```

### WalletAmount

```json
{
  "properties": {
    "amount": {
      "type": "number",
      "exclusiveMinimum": 0.0,
      "title": "Amount"
    }
  },
  "type": "object",
  "required": [
    "amount"
  ],
  "title": "WalletAmount"
}
```

### WinnerCreate

```json
{
  "properties": {
    "player_id": {
      "type": "integer",
      "title": "Player Id"
    },
    "position": {
      "type": "integer",
      "maximum": 4.0,
      "minimum": 1.0,
      "title": "Position"
    }
  },
  "type": "object",
  "required": [
    "player_id",
    "position"
  ],
  "title": "WinnerCreate"
}
```
