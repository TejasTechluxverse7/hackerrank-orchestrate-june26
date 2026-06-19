"""
decision_engine.py — Deterministic Evidence-First Decision Engine.

Evaluates the Evidence Graph to determine the final claim status
(supported, contradicted, not_enough_information) without directly
inspecting raw images. Relies entirely on the established graph topology.
"""

import logging
from enum import Enum
from typing import List, Tuple

from .claim_parser import ParsedClaim
from .evidence_graph import EvidenceGraph, EdgeType, EvidenceGraphBuilder
from .evidence_retriever import EvidenceRequirement
from .image_analyzer import ImageObservation

logger = logging.getLogger(__name__)


class DecisionStatus(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NOT_ENOUGH_INFO = "not_enough_information"


class DecisionEngine:
    """Evaluates the Evidence Graph to make final adjudications."""

    def decide(
        self,
        claim: ParsedClaim,
        observations: List[ImageObservation],
        graph: EvidenceGraph,
        requirements: List[EvidenceRequirement],
        risk_flags: List[str]
    ) -> Tuple[DecisionStatus, str]:
        """
        Determines the status of the claim using evidence-first reasoning.
        
        Args:
            claim: The parsed customer claim details.
            observations: Raw visual observations (unused directly; decisions rely on graph).
            graph: The constructed evidence graph topology.
            requirements: Applicable visual evidence requirements.
            risk_flags: Identified user history risk flags.
            
        Returns:
            Tuple of (DecisionStatus, reason_string)
        """
        # 1. Gather edge statistics from the graph
        contradicts_edges = graph.get_edges(EdgeType.CONTRADICTS)
        supports_edges = graph.get_edges(EdgeType.SUPPORTS)
        insufficient_edges = graph.get_edges(EdgeType.INSUFFICIENT)

        # 2. Hard Contradiction Check (Highest Priority)
        # If the visual evidence actively contradicts the claim (e.g. wrong object,
        # or clear visibility of the part with no damage), we reject the claim.
        if contradicts_edges:
            reason = f"Visual evidence actively contradicts the claim ({len(contradicts_edges)} contradiction edges found)."
            logger.info(f"Decision: {DecisionStatus.CONTRADICTED.value} - {reason}")
            return DecisionStatus.CONTRADICTED, reason

        # 3. Sufficiency Check
        # We leverage the graph scorer to weigh supports against insufficient edges.
        builder = EvidenceGraphBuilder()
        score_data = builder.score(graph)

        if not score_data["is_sufficient"]:
            reasons = " | ".join(score_data["reasons"]) if score_data["reasons"] else "Lack of sufficient supporting evidence."
            logger.info(f"Decision: {DecisionStatus.NOT_ENOUGH_INFO.value} - {reasons}")
            return DecisionStatus.NOT_ENOUGH_INFO, reasons

        # 4. Check Requirements
        # Ensure that every requirement node is supported by at least one image.
        for req in requirements:
            req_id = f"req_{req.requirement_id}"
            # Find if any image supports this requirement
            is_req_supported = any(
                target == req_id for source, edge_type, target in supports_edges
            )
            # If the requirement isn't explicitly supported, the evidence is insufficient
            if not is_req_supported:
                reason = f"Missing evidence for requirement: {req.requirement_id}"
                logger.info(f"Decision: {DecisionStatus.NOT_ENOUGH_INFO.value} - {reason}")
                return DecisionStatus.NOT_ENOUGH_INFO, reason

        # 5. Full Support
        reason = f"Evidence graph confirms claim with confidence score {score_data['confidence_score']}."
        logger.info(f"Decision: {DecisionStatus.SUPPORTED.value} - {reason}")
        return DecisionStatus.SUPPORTED, reason
