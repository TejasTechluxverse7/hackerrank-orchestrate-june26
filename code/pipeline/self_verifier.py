"""
self_verifier.py — Output Verification and Guardrails.

Final post-processing step that verifies the logical consistency of the
adjudicated decision against the raw graph topologies. Checks supporting
image IDs, claim status, issue type, and object part.

If internal contradictions are found between the decision and the evidence,
it appends 'manual_review_required' to the risk flags.
"""

import logging
from dataclasses import dataclass, field
from typing import List

from .claim_parser import ParsedClaim
from .decision_engine import DecisionStatus
from .evidence_graph import EvidenceGraph, EdgeType

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """The result of the self-verification guardrail pass."""
    is_consistent: bool
    supporting_image_ids: List[str]
    additional_flags: List[str] = field(default_factory=list)
    contradictions_found: List[str] = field(default_factory=list)


class SelfVerifier:
    """Verifies pipeline decisions to prevent hallucinated or illogical outputs."""

    def verify(
        self,
        decision: DecisionStatus,
        graph: EvidenceGraph,
        claim: ParsedClaim,
        proposed_supporting_images: List[str]
    ) -> VerificationResult:
        """
        Runs consistency checks across the decision output.
        
        Args:
            decision: The decision rendered by the Decision Engine.
            graph: The scored Evidence Graph.
            claim: The parsed customer claim.
            proposed_supporting_images: Image IDs proposed to support the claim.
            
        Returns:
            VerificationResult containing final valid images and any forced flags.
        """
        contradictions = []
        valid_image_ids = set()

        # 1. Verify Supporting Image IDs
        # An image is only valid if it actually has SUPPORTS edges connecting it to the claim parts/issues.
        supports_edges = graph.get_edges(EdgeType.SUPPORTS)
        actual_supporting_images = {src for src, _, _ in supports_edges if src.startswith("img_")}
        
        for img_id in proposed_supporting_images:
            if img_id not in actual_supporting_images:
                contradictions.append(f"Image {img_id} claimed as supporting, but graph shows no SUPPORTS edge.")
            else:
                valid_image_ids.add(img_id)

        # Ensure we capture all actually supporting images even if omitted
        valid_image_ids.update(actual_supporting_images)

        # 2. Verify Claim Status Consistency
        contradicts_edges = graph.get_edges(EdgeType.CONTRADICTS)
        if decision == DecisionStatus.SUPPORTED and contradicts_edges:
            contradictions.append(f"Decision is {DecisionStatus.SUPPORTED.value} but graph contains {len(contradicts_edges)} CONTRADICTS edges.")
            
        if decision == DecisionStatus.CONTRADICTED and not contradicts_edges:
            contradictions.append(f"Decision is {DecisionStatus.CONTRADICTED.value} but graph contains no CONTRADICTS edges.")

        # 3. Verify Issue Type
        # Ensure the graph has an image SUPPORTS edge specifically for the claimed issue
        issue_id = f"issue_{claim.issue_hint.value}"
        issue_supported = any(tgt == issue_id and src.startswith("img_") for src, _, tgt in supports_edges)
        
        if decision == DecisionStatus.SUPPORTED and not issue_supported:
            contradictions.append(f"Decision is {DecisionStatus.SUPPORTED.value} but issue '{claim.issue_hint.value}' lacks visual support.")

        # 4. Verify Object Part
        # Ensure the graph has an image SUPPORTS edge specifically for the claimed part
        parts_supported = []
        for part in claim.claimed_parts:
            part_id = f"part_{part}"
            if any(tgt == part_id and src.startswith("img_") for src, _, tgt in supports_edges):
                parts_supported.append(part)
                
        if decision == DecisionStatus.SUPPORTED and not parts_supported:
            contradictions.append(f"Decision is {DecisionStatus.SUPPORTED.value} but no claimed parts have visual support.")

        # 5. Resolve Output
        additional_flags = []
        if contradictions:
            logger.warning(f"Self-verifier found {len(contradictions)} logical contradictions. Forcing manual review.")
            additional_flags.append("manual_review_required")
            
        return VerificationResult(
            is_consistent=len(contradictions) == 0,
            supporting_image_ids=sorted(list(valid_image_ids)),
            additional_flags=additional_flags,
            contradictions_found=contradictions
        )
