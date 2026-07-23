"""Business rules are never hard-coded. They are read once at startup from a
JSON configuration file (see src/config/rules.json) and injected into the
stage handlers that need them.

Changing a threshold (e.g. minimumCreditScore) only requires editing the
config file and restarting the container -- no source code change, no
recompilation of business logic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RulesConfig:
    minimum_credit_score: int
    manager_approval_threshold: int
    income_multiplier: int
    manual_review_min_score: int
    manual_review_max_score: int

    @staticmethod
    def load(path: str | Path) -> "RulesConfig":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        manual_review = raw.get("manualReview", {})
        return RulesConfig(
            minimum_credit_score=int(raw["minimumCreditScore"]),
            manager_approval_threshold=int(raw["managerApprovalThreshold"]),
            income_multiplier=int(raw["incomeMultiplier"]),
            manual_review_min_score=int(manual_review["minScore"]),
            manual_review_max_score=int(manual_review["maxScore"]),
        )
