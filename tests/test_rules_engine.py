from datetime import datetime
from typing import List

from app.core import (
    ConditionOperator,
    LogicalOperator,
    RuleCondition,
    RuleGroup,
    TrackEnrichment,
)
from app.pipeline import build_enrichment_view, matches_rules


def test_build_enrichment_view_last_wins_and_preserves_other_keys():
    entries: List[TrackEnrichment] = [
        TrackEnrichment(
            source="s1",
            version="v1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            categories={"mood": "first", "energy": "low"},
        ),
        TrackEnrichment(
            source="s2",
            version="v2",
            timestamp=datetime(2025, 1, 2, 12, 0, 0),
            categories={"mood": "second", "tempo": "fast"},
        ),
    ]

    view = build_enrichment_view(entries)

    assert view["mood"] == "second"
    assert view["energy"] == "low"
    assert view["tempo"] == "fast"


def test_matches_rules_and_empty_conditions_returns_true():
    enrichment = {"any": "thing"}
    rules = RuleGroup(operator=LogicalOperator.AND, conditions=[])

    assert matches_rules(enrichment, rules) is True


def test_matches_rules_or_empty_conditions_returns_false():
    enrichment = {"any": "thing"}
    rules = RuleGroup(operator=LogicalOperator.OR, conditions=[])

    assert matches_rules(enrichment, rules) is False


def test_matches_rules_numeric_gt_and_lte():
    enrichment = {"score": 0.75}
    rules = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="score",
                operator=ConditionOperator.GT,
                value=0.5,
            ),
            RuleCondition(
                field="score",
                operator=ConditionOperator.LTE,
                value=1.0,
            ),
        ],
    )

    assert matches_rules(enrichment, rules) is True


def test_matches_rules_regex_invalid_pattern_returns_false():
    enrichment = {"title": "some title"}
    rules = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="title",
                operator=ConditionOperator.REGEX,
                value="(",
            )
        ],
    )

    assert matches_rules(enrichment, rules) is False


def test_matches_rules_in_and_not_in() -> None:
    enrichment = {"mood": "chill"}

    rules_in = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="mood",
                operator=ConditionOperator.IN,
                value=["chill", "happy"],
            )
        ],
    )
    assert matches_rules(enrichment, rules_in) is True

    rules_not_in = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="mood",
                operator=ConditionOperator.NOT_IN,
                value=["sad", "angry"],
            )
        ],
    )
    assert matches_rules(enrichment, rules_not_in) is True

    # Negative case: mood in excluded set
    rules_not_in_fail = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="mood",
                operator=ConditionOperator.NOT_IN,
                value=["chill", "sad"],
            )
        ],
    )
    assert matches_rules(enrichment, rules_not_in_fail) is False


def test_matches_rules_between_inclusive_bounds() -> None:
    enrichment = {"tempo": 120}

    rules = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="tempo",
                operator=ConditionOperator.BETWEEN,
                value=[100, 130],
            )
        ],
    )

    assert matches_rules(enrichment, rules) is True

    rules_outside = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="tempo",
                operator=ConditionOperator.BETWEEN,
                value=[121, 130],
            )
        ],
    )

    assert matches_rules(enrichment, rules_outside) is False


def test_matches_rules_string_contains_starts_ends() -> None:
    enrichment = {"title": "My Happy Song"}

    rules = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="title",
                operator=ConditionOperator.CONTAINS,
                value="Happy",
            ),
            RuleCondition(
                field="title",
                operator=ConditionOperator.STARTS_WITH,
                value="My",
            ),
            RuleCondition(
                field="title",
                operator=ConditionOperator.ENDS_WITH,
                value="Song",
            ),
        ],
    )

    assert matches_rules(enrichment, rules) is True


def test_matches_rules_exists_and_not_exists() -> None:
    enrichment = {
        "present": 1,
        "none_value": None,
    }

    rules = RuleGroup(
        operator=LogicalOperator.AND,
        conditions=[
            RuleCondition(
                field="present",
                operator=ConditionOperator.EXISTS,
                value=True,
            ),
            RuleCondition(
                field="missing",
                operator=ConditionOperator.NOT_EXISTS,
                value=True,
            ),
            RuleCondition(
                field="none_value",
                operator=ConditionOperator.NOT_EXISTS,
                value=True,
            ),
        ],
    )

    assert matches_rules(enrichment, rules) is True
