# Rules API

This document describes the HTTP endpoints related to playlist rules and their evaluation.

Playlist rules provide a declarative way to express how tracks should be grouped into
playlists based on their enrichment categories (mood, energy, genre, etc.).

## Data model

### ConditionOperator

The `ConditionOperator` enum represents comparison operators:

- `eq`, `ne` – equality / inequality
- `gt`, `lt`, `gte`, `lte` – numeric comparisons
- `in`, `not_in` – membership in a collection
- (future) `between`, `contains`, `starts_with`, `ends_with`, `exists`, `not_exists`, `regex`

### LogicalOperator

- `and` – all conditions must be true
- `or` – at least one condition must be true

### RuleCondition

```python
class RuleCondition(BaseModel):
    field: str
    operator: ConditionOperator
    value: Any
```

- `field`: the enrichment field key (e.g. `"mood"`, `"energy"`).
- `operator`: how to compare.
- `value`: the right-hand operand (string, number, list, depending on the operator).

### RuleGroup

```python
class RuleGroup(BaseModel):
    operator: LogicalOperator = LogicalOperator.AND
    conditions: List[RuleCondition]
```

- A group of conditions combined with a logical operator.
- Empty condition list:
  - `AND`: treated as `True`
  - `OR`: treated as `False`

### PlaylistRuleSet

```python
class PlaylistRuleSet(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    rules: RuleGroup
    target_playlist_id: Optional[str] = None
    enabled: bool = True
```

- `id`: stable identifier for the rule set.
- `name`: human-readable name.
- `rules`: the root RuleGroup.
- `target_playlist_id`: optional Spotify playlist id that the rule set applies to.
- `enabled`: feature flag (frontend can ignore disabled rule sets).

## Storage

Rules are stored as JSON in `rules.json` under the cache directory. The storage helpers
are located in `app/data/rules.py` and exposed via the `app.data` façade:

```python
from app.data import load_rules, save_rules
```

- `load_rules() -> List[PlaylistRuleSet]`
- `save_rules(rules: List[PlaylistRuleSet]) -> None`

## Endpoints

All rules-related endpoints live under the `data` API (`app/api/data/routes.py`).

### GET /data/rules

- **Method**: `GET`
- **Path**: `/data/rules`
- **Response**: a JSON list of rule objects, each containing at least `id` and `name`.

Example response:

```json
[
  {
    "id": "mood_happy",
    "name": "Happy tracks",
    "description": "All tracks with mood happy",
    "enabled": true,
    "rules": {
      "operator": "and",
      "conditions": [
        { "field": "mood", "operator": "eq", "value": "happy" }
      ]
    },
    "target_playlist_id": null
  }
]
```

If no rules exist, an empty list `[]` is returned.

### POST /data/rules

- **Method**: `POST`
- **Path**: `/data/rules`
- **Body**: a `PlaylistRuleSet`-compatible JSON object.
- **Semantics**: upsert (create or replace).

Logic:
- Load existing rules via `load_rules()`.
- If a rule with the same `id` exists, it is replaced.
- Otherwise, the new rule is appended.
- The updated list is saved with `save_rules()`.
- The saved rule is returned as a JSON object.

Example request body:

```json
{
  "id": "smoke_test_rule",
  "name": "Smoke Test Rule",
  "description": "Created by smoke test",
  "enabled": true,
  "target_playlist_id": null,
  "rules": {
    "operator": "and",
    "conditions": [
      { "field": "mood", "operator": "eq", "value": "smoke_test_mood" }
    ]
  }
}
```

### POST /data/rules/evaluate

- **Method**: `POST`
- **Path**: `/data/rules/evaluate`
- **Body**:

  ```json
  {
    "rules": {
      "operator": "and",
      "conditions": [
        { "field": "mood", "operator": "eq", "value": "happy" }
      ]
    },
    "enrichment": {
      "mood": "happy"
    }
  }
  ```

- **Response**:

  ```json
  { "matches": true }
  ```

The backend delegates to the pipeline rules engine:

```python
from app.pipeline import matches_rules

result = matches_rules(enrichment, rules)
return {"matches": bool(result)}
```

This endpoint is used both by the smoke test and future frontend rule builders to
perform quick “dry-run” evaluations without modifying any persistent data.

### (Future) POST /data/rules/validate

Planned endpoint to validate rules without evaluating them against any enrichment:

- **Method**: `POST`
- **Path**: `/data/rules/validate`
- **Body**: `{ "rules": RuleGroup }`
- **Response**:
  - On success: `{ "valid": true }`
  - On failure: HTTP 400 with `{ "errors": [...] }`

This will allow the UI to validate complex rule structures before saving them.
