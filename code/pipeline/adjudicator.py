"""
adjudicator.py — Module E: Claim Adjudicator.

Evaluates the Evidence Graph to make deterministic decisions
about the claim status (accept, manual_review, reject).
"""

import logging
from enum import Enum
from typing import List

from .evidence_graph import EvidenceGraph, EdgeType

logger = logging.getLogger(__name__)


class ClaimStatus(str, Enum):
    ACCEPT = "accept"
    MANUAL_REVIEW = "manual_review"
    REJECT = "reject"
    NOT_ENOUGH_INFO = "not_enough_information"


class AdjudicationResult:
    def __init__(self, status: ClaimStatus, reason: str):
        self.status = status
        self.reason = reason


class Adjudicator:
    """Evaluates the Evidence Graph to determine final claim status."""

    def adjudicate(self, graph: EvidenceGraph) -> AdjudicationResult:
        """
        Runs rules against the graph to determine claim status.
        Priority: Reject > Manual Review > Accept
        """
        # 1. Gather edge sets
        covers_edges = graph.get_edges(EdgeType.COVERS)
        matches_issue_edges = graph.get_edges(EdgeType.MATCHES_ISSUE)
        contradicts_edges = graph.get_edges(EdgeType.CONTRADICTS)
        quality_edges = graph.get_edges(EdgeType.QUALITY_ISSUE)
        satisfies_edges = graph.get_edges(EdgeType.SATISFIES)

        # 2. Reject conditions
        # If any image actively contradicts the claim (wrong object, or clear image with no damage)
        if contradicts_edges:
            reasons = [tgt for _, tgt in contradicts_edges]
            if "no_damage_visible" in reasons:
                return AdjudicationResult(ClaimStatus.REJECT, "Clear image shows no damage on the claimed part.")
            if "wrong_object" in reasons and len(graph.image_nodes) == len(contradicts_edges):
                return AdjudicationResult(ClaimStatus.REJECT, "Images do not show the claimed object.")

        # 3. Manual Review conditions (Quality issues or missing requirements)
        # If there are widespread quality issues preventing assessment
        if quality_edges:
            return AdjudicationResult(ClaimStatus.MANUAL_REVIEW, "Images have quality issues (blurry, glare, etc) requiring manual review.")
            
        # Check if all requirements are satisfied
        satisfied_reqs = {tgt for _, tgt in satisfies_edges}
        required_reqs = set(graph.requirement_nodes.keys())
        missing_reqs = required_reqs - satisfied_reqs
        
        if missing_reqs:
            # We don't reject right away for missing requirements, we send to manual review
            return AdjudicationResult(ClaimStatus.MANUAL_REVIEW, f"Missing evidence requirements: {', '.join(missing_reqs)}")

        # 4. Accept conditions
        # Must have at least one image showing the part AND matching the issue
        if covers_edges and matches_issue_edges:
            return AdjudicationResult(ClaimStatus.ACCEPT, "Images clearly show the claimed object, part, and matching damage.")

        # 5. Fallback
        return AdjudicationResult(ClaimStatus.MANUAL_REVIEW, "Insufficient clear evidence to accept or reject automatically.")
