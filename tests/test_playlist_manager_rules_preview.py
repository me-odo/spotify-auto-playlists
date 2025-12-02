from app.core import (
    ConditionOperator,
    LogicalOperator,
    PlaylistRuleSet,
    RuleCondition,
    RuleGroup,
)
from app.pipeline import build_rule_based_playlists


def test_build_rule_based_playlists_single_rule_one_match() -> None:
    rule = PlaylistRuleSet(
        id="rule1",
        name="Mood smoke test",
        rules=RuleGroup(
            operator=LogicalOperator.AND,
            conditions=[
                RuleCondition(
                    field="mood",
                    operator=ConditionOperator.EQ,
                    value="smoke_test_mood",
                )
            ],
        ),
    )

    tracks = [
        {
            "track_id": "t1",
            "enrichment": {"mood": "smoke_test_mood"},
        },
        {
            "track_id": "t2",
            "enrichment": {"mood": "other"},
        },
    ]

    playlists = build_rule_based_playlists([rule], tracks)

    assert len(playlists) == 1
    playlist = playlists[0]

    assert playlist["rule_id"] == "rule1"
    assert playlist["rule_name"] == "Mood smoke test"
    assert playlist["track_ids"] == ["t1"]
    assert playlist["track_count"] == 1


def test_build_rule_based_playlists_no_rules_returns_empty() -> None:
    tracks = [
        {
            "track_id": "t1",
            "enrichment": {"mood": "smoke_test_mood"},
        },
        {
            "track_id": "t2",
            "enrichment": {"mood": "other"},
        },
    ]

    playlists = build_rule_based_playlists([], tracks)

    assert playlists == []
