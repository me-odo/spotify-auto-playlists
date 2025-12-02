# Rules Engine

This document describes the rules engine implemented in `app/pipeline/rules_engine.py`.

The rules engine evaluates whether a given track (or a simplified enrichment mapping)
matches a ruleset expressed as a `RuleGroup`.

## Overview

Core pieces:

- `RuleCondition`: a single condition on a specific enrichment field.
- `RuleGroup`: a logical combination (AND/OR) of multiple conditions.
- `PlaylistRuleSet`: wraps a `RuleGroup` plus metadata (id, name, etc.).
- `build_enrichment_view(entries)`:
  merges multiple `TrackEnrichment` entries into a flat mapping.
- `matches_rules(enrichment, rules)`:
  evaluates a `RuleGroup` against an enrichment mapping.

The engine is designed to be:

- **simple** (no deep nesting yet),
- **predictable** (clear semantics for empty lists, unknown fields, and type mismatch),
- **frontend-friendly** (can be fully configured from JSON),
- **extensible** (future operators like `between`, `contains`, etc.).

## Enrichment view

Before evaluating rules, all enrichments for a single track can be combined using:

```python
from app.pipeline import build_enrichment_view

view = build_enrichment_view(track_enrichments)
```

Implementation strategy:

- Start from an empty dict.
- For each `TrackEnrichment` in order:
  - if `entry.categories` is a dict, call `view.update(entry.categories)`.
- Later entries overwrite earlier keys.

Example:

```python
[
  TrackEnrichment(source="external_features", categories={"mood": "dark", "energy": 0.7}),
  TrackEnrichment(source="llm_v1", categories={"mood": "happy"}),
]
```

produces:

```python
{"mood": "happy", "energy": 0.7}
```

## Condition evaluation

The internal helper `_evaluate_condition(enrichment, condition)`:

- Reads `field`, `operator`, `value` from `condition`.
- Looks up `left = enrichment.get(field)`.
- Applies logic based on the `ConditionOperator`:

  - `EQ`: `left == value`
  - `NE`: `left != value`

  - `GT`, `LT`, `GTE`, `LTE`:
    - Only apply when both operands are numeric (int or float).
    - If types are not numeric, the condition returns `False`.

  - `IN`, `NOT_IN`:
    - `value` must be a collection (list, tuple, set).
    - `IN`: `left in value`
    - `NOT_IN`: `left not in value`
    - If `value` is not a collection, returns `False`.

Any unsupported operator or type mismatch yields `False` (fail-closed semantics).

## RuleGroup evaluation

```python
from app.core import RuleGroup, LogicalOperator

def matches_rules(enrichment: Dict[str, Any], rules: RuleGroup) -> bool:
    ...
```

Semantics:

- `results = [_evaluate_condition(enrichment, cond) for cond in rules.conditions]`

- If `rules.operator == LogicalOperator.AND`:
  - Returns `all(results)`.
  - Empty `conditions` → `True` (vacuously true).

- If `rules.operator == LogicalOperator.OR`:
  - Returns `any(results)`.
  - Empty `conditions` → `False` (no condition matched).

- Unknown logical operator → defaults to `False`.

These simple rules are enough to express typical playlist definitions such as:

- “All tracks with mood happy or calm”
- “Energy >= 0.8 and genre in [rock, metal]”

## Integration points

The rules engine is exposed via the pipeline façade:

```python
from app.pipeline import matches_rules, build_enrichment_view
```

and is used by:

- `/data/rules/evaluate`:
  accepts `{"rules": RuleGroup, "enrichment": {...}}` and returns `{"matches": bool}`.
- Future playlist-building logic:
  iterating over tracks and applying rule sets to decide membership in target playlists.

## Future extensions

Planned operator extensions (some may already be partially implemented):

- `BETWEEN` – numeric range checks.
- `CONTAINS` – substring match for strings.
- `STARTS_WITH`, `ENDS_WITH` – string prefix/suffix.
- `EXISTS`, `NOT_EXISTS` – presence/absence of a field in the enrichment view.
- `REGEX` – regular expression match.

Planned higher-level features:

- Nested RuleGroups (groups of groups).
- Per-rule-set weighting or priorities when multiple rules target the same playlist.
- Debug/trace mode: return which conditions matched or failed for a given track.
