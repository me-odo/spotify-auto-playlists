import json
from pathlib import Path

from app.core import (
    ConditionOperator,
    LogicalOperator,
    PlaylistRuleSet,
    RuleCondition,
    RuleGroup,
)
from app.data import load_rules, save_rules


def test_rules_roundtrip(tmp_path: Path, monkeypatch) -> None:
    rules_path = tmp_path / "rules.json"
    monkeypatch.setattr(
        "app.data.rules.RULES_FILE",
        str(rules_path),
        raising=False,
    )

    rule1 = PlaylistRuleSet(
        id="rule1",
        name="Mood chill",
        description="chill mood only",
        rules=RuleGroup(
            operator=LogicalOperator.AND,
            conditions=[
                RuleCondition(
                    field="mood",
                    operator=ConditionOperator.EQ,
                    value="chill",
                )
            ],
        ),
    )
    rule2 = PlaylistRuleSet(
        id="rule2",
        name="High score",
        rules=RuleGroup(
            operator=LogicalOperator.AND,
            conditions=[
                RuleCondition(
                    field="score",
                    operator=ConditionOperator.GTE,
                    value=0.8,
                )
            ],
        ),
    )

    save_rules([rule1, rule2])
    loaded = load_rules()

    assert len(loaded) == 2

    loaded1 = loaded[0]
    loaded2 = loaded[1]

    assert loaded1.id == rule1.id
    assert loaded1.name == rule1.name
    assert loaded1.rules.operator == LogicalOperator.AND
    assert len(loaded1.rules.conditions) == 1
    cond1 = loaded1.rules.conditions[0]
    assert cond1.field == "mood"
    assert cond1.operator == ConditionOperator.EQ
    assert cond1.value == "chill"

    assert loaded2.id == rule2.id
    assert loaded2.name == rule2.name
    assert loaded2.rules.operator == LogicalOperator.AND
    assert len(loaded2.rules.conditions) == 1
    cond2 = loaded2.rules.conditions[0]
    assert cond2.field == "score"
    assert cond2.operator == ConditionOperator.GTE
    assert cond2.value == 0.8


def test_load_rules_skips_invalid_entries(tmp_path: Path, monkeypatch) -> None:
    rules_path = tmp_path / "rules_invalid.json"
    monkeypatch.setattr(
        "app.data.rules.RULES_FILE",
        str(rules_path),
        raising=False,
    )

    valid_rule_dict = {
        "id": "rule_valid",
        "name": "Valid rule",
        "description": "valid entry",
        "rules": {
            "operator": "and",
            "conditions": [
                {
                    "field": "mood",
                    "operator": "eq",
                    "value": "chill",
                }
            ],
        },
        "target_playlist_id": None,
        "enabled": True,
    }

    data = [
        valid_rule_dict,
        123,
        {
            "id": "rule_invalid_rules",
            "name": "Invalid rules field",
            "rules": "not-a-dict",
        },
    ]

    rules_path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_rules()

    assert len(loaded) == 1
    rule = loaded[0]
    assert isinstance(rule, PlaylistRuleSet)
    assert rule.id == "rule_valid"
    assert rule.name == "Valid rule"
    assert rule.rules.operator == LogicalOperator.AND
    assert len(rule.rules.conditions) == 1
    cond = rule.rules.conditions[0]
    assert cond.field == "mood"
    assert cond.operator == ConditionOperator.EQ
    assert cond.value == "chill"
