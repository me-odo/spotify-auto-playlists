from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel


class ConditionOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"


class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"


class RuleCondition(BaseModel):
    field: str
    operator: ConditionOperator
    value: Any


class RuleGroup(BaseModel):
    operator: LogicalOperator = LogicalOperator.AND
    conditions: List[RuleCondition]


class PlaylistRuleSet(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    rules: RuleGroup
    target_playlist_id: Optional[str] = None
    enabled: bool = True
