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
