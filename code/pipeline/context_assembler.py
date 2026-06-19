"""
context_assembler.py — Module B: Context Assembler.

Loads user history and evidence requirements, and packages them with the parsed claim
into a unified ContextBundle that provides necessary context for VLM analysis.
"""

import csv
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .claim_parser import ClaimObject, IssueFamily, ParsedClaim

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums and Data Models
# ---------------------------------------------------------------------------

class RiskTier(str, Enum):
    CLEAN = "clean"
    LOW_RISK = "low_risk"
    HIGH_RISK = "high_risk"
    REVIEW_ONLY = "review_only"


class UserHistory(BaseModel):
    user_id: str
    past_claim_count: int
    accept_claim: int
    manual_review_claim: int
    rejected_claim: int
    last_90_days_claim_count: int
    history_flags: str
    history_summary: str
    risk_tier: RiskTier


class EvidenceRequirement(BaseModel):
    requirement_id: str
    applies_to: str
    minimum_image_evidence: str


class ContextBundle(BaseModel):
    parsed_claim: ParsedClaim
    user_history: UserHistory
    applicable_requirements: List[EvidenceRequirement]


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------

class ContextAssembler:
    """Loads CSV databases and assembles context bundles for claims."""

    def __init__(self, user_history_path: str, evidence_req_path: str):
        self.user_history_db: Dict[str, UserHistory] = {}
        self.evidence_reqs: List[EvidenceRequirement] = []
        self._load_user_history(user_history_path)
        self._load_evidence_reqs(evidence_req_path)

    def _determine_risk_tier(self, row: dict) -> RiskTier:
        """Calculate risk tier based on history flags and rejection ratio."""
        flags = row.get("history_flags", "").lower()
        if "manual_review_required" in flags:
            return RiskTier.REVIEW_ONLY

        past_claims = int(row.get("past_claim_count", 0))
        rejected = int(row.get("rejected_claim", 0))
        rejection_ratio = rejected / past_claims if past_claims > 0 else 0.0

        if "user_history_risk" in flags or rejection_ratio > 0.3:
            return RiskTier.HIGH_RISK
        if rejected > 0:
            return RiskTier.LOW_RISK
        return RiskTier.CLEAN

    def _load_user_history(self, path: str):
        if not Path(path).exists():
            logger.warning(f"User history file not found at {path}")
            return
        
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tier = self._determine_risk_tier(row)
                history = UserHistory(
                    user_id=row["user_id"],
                    past_claim_count=int(row.get("past_claim_count", 0)),
                    accept_claim=int(row.get("accept_claim", 0)),
                    manual_review_claim=int(row.get("manual_review_claim", 0)),
                    rejected_claim=int(row.get("rejected_claim", 0)),
                    last_90_days_claim_count=int(row.get("last_90_days_claim_count", 0)),
                    history_flags=row.get("history_flags", "none"),
                    history_summary=row.get("history_summary", ""),
                    risk_tier=tier
                )
                self.user_history_db[history.user_id] = history
        logger.info(f"Loaded {len(self.user_history_db)} user history records.")

    def _load_evidence_reqs(self, path: str):
        if not Path(path).exists():
            logger.warning(f"Evidence requirements file not found at {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.evidence_reqs.append(
                    EvidenceRequirement(
                        requirement_id=row["requirement_id"],
                        applies_to=row["applies_to"],  # Corresponds to IssueFamily or general
                        minimum_image_evidence=row["minimum_image_evidence"]
                    )
                )
        logger.info(f"Loaded {len(self.evidence_reqs)} evidence requirements.")

    def assemble(self, parsed_claim: ParsedClaim, user_id: str) -> ContextBundle:
        """Package claim, user history, and applicable evidence requirements."""
        # 1. Fetch user history (fallback to clean slate if not found)
        history = self.user_history_db.get(
            user_id,
            UserHistory(
                user_id=user_id,
                past_claim_count=0,
                accept_claim=0,
                manual_review_claim=0,
                rejected_claim=0,
                last_90_days_claim_count=0,
                history_flags="none",
                history_summary="No prior history found.",
                risk_tier=RiskTier.CLEAN
            )
        )

        # 2. Select evidence requirements
        applicable_reqs = []
        for req in self.evidence_reqs:
            # Applies if it's a general requirement for all
            if req.applies_to == "general claim review":
                applicable_reqs.append(req)
                continue
            
            # Applies if it's multi-image and we have multiple images (VLM probe will handle image count, 
            # but we include it if the claim is multi-part or we generally include it for all)
            if req.applies_to == "multi-image rows":
                applicable_reqs.append(req)
                continue
                
            # Applies if the requirement specifically targets this issue family
            if req.applies_to == parsed_claim.issue_family.value:
                applicable_reqs.append(req)
                continue

        logger.debug(f"Assembled context for user {user_id}. Found {len(applicable_reqs)} applicable requirements.")
        
        return ContextBundle(
            parsed_claim=parsed_claim,
            user_history=history,
            applicable_requirements=applicable_reqs
        )
