from typing import Any, Dict, List

from app.core import (
    ConditionOperator,
    LogicalOperator,
    RuleCondition,
    RuleGroup,
    TrackEnrichment,
)


def build_enrichment_view(entries: List[TrackEnrichment]) -> Dict[str, Any]:
    """
    Build a flattened view of all enrichment categories for a single track.

    The implementation:
      - starts from an empty dict
      - for each TrackEnrichment in order, updates the dict with entry.categories
      - later entries overwrite earlier keys
    """
    view: Dict[str, Any] = {}
    for entry in entries or []:
        categories = entry.categories or {}
        if isinstance(categories, dict):
            view.update(categories)
    return view


def _evaluate_condition(enrichment: Dict[str, Any], condition: RuleCondition) -> bool:
    """Evaluate a single RuleCondition against an enrichment mapping."""
    field = condition.field
    op = condition.operator
    value = condition.value

    left = enrichment.get(field)

    # EQ / NE
    if op == ConditionOperator.EQ:
        return left == value
    if op == ConditionOperator.NE:
        return left != value

    # Numeric comparisons
    if op in {
        ConditionOperator.GT,
        ConditionOperator.LT,
        ConditionOperator.GTE,
        ConditionOperator.LTE,
    }:
        if not isinstance(left, (int, float)) or not isinstance(value, (int, float)):
            return False

        if op == ConditionOperator.GT:
            return left > value
        if op == ConditionOperator.LT:
            return left < value
        if op == ConditionOperator.GTE:
            return left >= value
        if op == ConditionOperator.LTE:
            return left <= value

    # IN / NOT_IN
    if op in {ConditionOperator.IN, ConditionOperator.NOT_IN}:
        if isinstance(value, (list, tuple, set)):
            if op == ConditionOperator.IN:
                return left in value
            return left not in value
        # Unsupported value type for membership tests
        return False

    # Fallback: unsupported operator
    return False


def matches_rules(enrichment: Dict[str, Any], rules: RuleGroup) -> bool:
    """
    Return True if the given enrichment mapping satisfies the provided rules.

    Supported:
      - ConditionOperator.EQ / NE
      - GT / LT / GTE / LTE for numeric values
      - IN / NOT_IN for collection-valued 'value'
      - LogicalOperator.AND / OR across conditions

    Empty conditions:
      - AND: treated as True
      - OR: treated as False
    """
    conditions = rules.conditions or []
    results: List[bool] = [_evaluate_condition(enrichment, cond) for cond in conditions]

    if rules.operator == LogicalOperator.AND:
        # Empty list -> True (vacuously true)
        return all(results)
    if rules.operator == LogicalOperator.OR:
        # Empty list -> False (no condition matched)
        return any(results)

    # Fallback: unknown logical operator -> default to False
    return False
