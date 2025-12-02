import json
import os
from typing import Any, Dict, List

from app.config import CACHE_DIR
from app.core import PlaylistRuleSet, read_json, write_json

RULES_FILE = os.path.join(CACHE_DIR, "rules.json")


def load_rules() -> List[PlaylistRuleSet]:
    """
    Load playlist rules from the JSON-backed cache.

    The on-disk structure is expected to be a list of objects compatible with
    PlaylistRuleSet. Malformed entries are skipped.
    """
    data = read_json(RULES_FILE, default=[])
    if not isinstance(data, list):
        return []

    rules: List[PlaylistRuleSet] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            rules.append(PlaylistRuleSet(**item))
        except Exception:
            # Ignore malformed entries instead of failing the whole load.
            continue

    return rules


def save_rules(rules: List[PlaylistRuleSet]) -> None:
    """
    Persist playlist rules to the JSON-backed cache as plain dicts.
    """
    serialised: List[Dict[str, Any]] = []
    for rule in rules:
        if isinstance(rule, PlaylistRuleSet):
            if hasattr(rule, "model_dump"):
                serialised.append(rule.model_dump(mode="json"))
            else:
                serialised.append(json.loads(rule.json()))
        elif isinstance(rule, dict):
            serialised.append(dict(rule))
        else:
            # Best-effort: skip unsupported types.
            continue

    write_json(RULES_FILE, serialised)
