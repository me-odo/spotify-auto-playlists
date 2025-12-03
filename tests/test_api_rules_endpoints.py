from pathlib import Path

from fastapi.testclient import TestClient

from api_main import app
from app.core import (
    ConditionOperator,
    LogicalOperator,
    PlaylistRuleSet,
    RuleCondition,
    RuleGroup,
)
from app.data import load_rules

client = TestClient(app)


def test_rules_evaluate_endpoint_matches() -> None:
    body = {
        "rules": {
            "operator": "and",
            "conditions": [
                {
                    "field": "mood",
                    "operator": "eq",
                    "value": "happy",
                }
            ],
        },
        "enrichment": {"mood": "happy"},
    }

    response = client.post("/data/rules/evaluate", json=body)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "matches" in data
    assert data["matches"] is True


def test_rules_evaluate_endpoint_non_match() -> None:
    body = {
        "rules": {
            "operator": "and",
            "conditions": [
                {
                    "field": "mood",
                    "operator": "eq",
                    "value": "happy",
                }
            ],
        },
        "enrichment": {"mood": "sad"},
    }

    response = client.post("/data/rules/evaluate", json=body)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "matches" in data
    assert data["matches"] is False


def test_rules_validate_endpoint(tmp_path: Path, monkeypatch) -> None:
    # This endpoint does not depend on RULES_FILE, but we keep test style consistent.
    body = {
        "rules": {
            "operator": "and",
            "conditions": [
                {
                    "field": "mood",
                    "operator": "eq",
                    "value": "happy",
                }
            ],
        }
    }

    response = client.post("/data/rules/validate", json=body)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "valid" in data
    assert isinstance(data["valid"], bool)
    assert data["valid"] is True


def test_rules_get_and_post_roundtrip(tmp_path: Path, monkeypatch) -> None:
    rules_path = tmp_path / "rules.json"
    monkeypatch.setattr(
        "app.data.rules.RULES_FILE",
        str(rules_path),
        raising=False,
    )

    rule = PlaylistRuleSet(
        id="api_rule",
        name="API Rule",
        description="Rule created via API",
        rules=RuleGroup(
            operator=LogicalOperator.AND,
            conditions=[
                RuleCondition(
                    field="mood",
                    operator=ConditionOperator.EQ,
                    value="happy",
                )
            ],
        ),
        enabled=True,
        target_playlist_id=None,
    )

    if hasattr(rule, "model_dump"):
        payload = rule.model_dump(mode="json")
    else:
        payload = rule.dict()
    response = client.post("/data/rules", json=payload)
    assert response.status_code == 200

    saved = response.json()
    assert saved["id"] == "api_rule"
    assert saved["name"] == "API Rule"
    assert saved["enabled"] is True

    # GET /data/rules should see the same rule using the patched RULES_FILE.
    response_get = client.get("/data/rules")
    assert response_get.status_code == 200

    rules_list = response_get.json()
    assert isinstance(rules_list, list)
    assert len(rules_list) == 1

    item = rules_list[0]
    assert item["id"] == "api_rule"
    assert item["name"] == "API Rule"

    # And load_rules() should also respect the patched RULES_FILE.
    loaded = load_rules()
    assert len(loaded) == 1
    assert loaded[0].id == "api_rule"
