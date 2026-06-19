"""
evidence_graph.py — Evidence Graph Builder and Scorer.

Constructs an evidence graph with explicit entities (Claim, Image, Part, Issue, 
Requirement, Risk) and evaluates relationship edges (supports, contradicts, insufficient).
Includes confidence scoring logic to determine evidence sufficiency.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple, Any

from .claim_parser import ParsedClaim
from .context_assembler import ContextBundle
from .image_analyzer import ImageObservation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"


# ---------------------------------------------------------------------------
# Graph Entities
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GraphNode:
    """Base class for all graph nodes."""
    node_id: str


@dataclass(frozen=True)
class ClaimNode(GraphNode):
    object_type: str


@dataclass(frozen=True)
class ImageNode(GraphNode):
    path: str
    is_original: bool


@dataclass(frozen=True)
class PartNode(GraphNode):
    part_name: str


@dataclass(frozen=True)
class IssueNode(GraphNode):
    issue_type: str


@dataclass(frozen=True)
class RequirementNode(GraphNode):
    description: str


@dataclass(frozen=True)
class RiskNode(GraphNode):
    risk_flag: str


# ---------------------------------------------------------------------------
# Evidence Graph
# ---------------------------------------------------------------------------

class EvidenceGraph:
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        # List of (source_id, EdgeType, target_id)
        self.edges: List[Tuple[str, EdgeType, str]] = []

    def add_node(self, node: GraphNode):
        self.nodes[node.node_id] = node

    def add_edge(self, source_id: str, edge_type: EdgeType, target_id: str):
        if source_id in self.nodes and target_id in self.nodes:
            self.edges.append((source_id, edge_type, target_id))
        else:
            logger.warning(f"Failed to add edge: missing node {source_id} or {target_id}")

    def get_edges(self, edge_type: EdgeType = None) -> List[Tuple[str, EdgeType, str]]:
        if edge_type:
            return [e for e in self.edges if e[1] == edge_type]
        return self.edges


# ---------------------------------------------------------------------------
# Graph Builder & Scorer
# ---------------------------------------------------------------------------

class EvidenceGraphBuilder:
    """Builds the Evidence Graph and computes an evidence confidence score."""

    def build(self, context: ContextBundle, observations: List[ImageObservation]) -> EvidenceGraph:
        graph = EvidenceGraph()

        # 1. Instantiate Core Nodes
        claim_id = "claim_root"
        graph.add_node(ClaimNode(node_id=claim_id, object_type=context.parsed_claim.claim_object.value))

        # Add parts and issues from the claim
        for part in context.parsed_claim.claimed_parts:
            part_id = f"part_{part}"
            graph.add_node(PartNode(node_id=part_id, part_name=part))
            graph.add_edge(claim_id, EdgeType.SUPPORTS, part_id)

        issue_id = f"issue_{context.parsed_claim.issue_hint.value}"
        graph.add_node(IssueNode(node_id=issue_id, issue_type=context.parsed_claim.issue_hint.value))
        graph.add_edge(claim_id, EdgeType.SUPPORTS, issue_id)

        # Add requirements
        for req in context.applicable_requirements:
            req_id = f"req_{req.requirement_id}"
            graph.add_node(RequirementNode(node_id=req_id, description=req.minimum_image_evidence))

        # Add risk flags
        flags_str = context.user_history.history_flags
        flags = [f.strip() for f in flags_str.split(";") if f.strip() and f.strip().lower() != "none"]
        for flag in flags:
            risk_id = f"risk_{flag}"
            graph.add_node(RiskNode(node_id=risk_id, risk_flag=flag))
            graph.add_edge(claim_id, EdgeType.INSUFFICIENT, risk_id)  # Risk makes claim context inherently weaker

        # 2. Process Image Observations
        for i, obs in enumerate(observations):
            img_id = f"img_{i}"
            graph.add_node(ImageNode(node_id=img_id, path=obs.image_path, is_original=obs.is_original))

            # Evaluate against claim object
            if obs.visible_object != context.parsed_claim.claim_object.value and obs.visible_object != "unknown":
                graph.add_edge(img_id, EdgeType.CONTRADICTS, claim_id)
            
            # Evaluate against parts
            obs_part_id = f"part_{obs.object_part}"
            if obs_part_id in graph.nodes:
                graph.add_edge(img_id, EdgeType.SUPPORTS, obs_part_id)
            elif obs.object_part != "unknown":
                graph.add_edge(img_id, EdgeType.CONTRADICTS, claim_id) # Wrong part entirely
                
            # Evaluate against issues
            obs_issue_id = f"issue_{obs.issue_type}"
            if obs_issue_id in graph.nodes and obs.issue_type != "unknown":
                graph.add_edge(img_id, EdgeType.SUPPORTS, obs_issue_id)
            elif obs.issue_type == "none":
                graph.add_edge(img_id, EdgeType.CONTRADICTS, issue_id) # Shows clear part but no damage

            # Quality Assessment
            if obs.quality_issues:
                # Quality issues mean the image provides insufficient evidence
                for req in context.applicable_requirements:
                    graph.add_edge(img_id, EdgeType.INSUFFICIENT, f"req_{req.requirement_id}")
            else:
                # Basic heuristic: if part/issue is supported and no quality issues, it satisfies reqs
                for req in context.applicable_requirements:
                    if (img_id, EdgeType.SUPPORTS, obs_part_id) in graph.edges:
                        graph.add_edge(img_id, EdgeType.SUPPORTS, f"req_{req.requirement_id}")

        return graph

    def score(self, graph: EvidenceGraph) -> Dict[str, Any]:
        """
        Computes a confidence score based on the graph's edge topologies.
        Returns a dictionary with 'confidence_score' and 'flagged_reasons'.
        """
        score = 100
        reasons = []

        supports = len(graph.get_edges(EdgeType.SUPPORTS))
        contradicts = len(graph.get_edges(EdgeType.CONTRADICTS))
        insufficient = len(graph.get_edges(EdgeType.INSUFFICIENT))

        # Base scoring logic
        score += (supports * 10)
        score -= (contradicts * 40)
        score -= (insufficient * 15)

        # Cap score
        score = max(0, min(100, score))

        if contradicts > 0:
            reasons.append(f"Found {contradicts} direct contradictions in visual evidence.")
        if insufficient > 0:
            reasons.append(f"Found {insufficient} instances of insufficient evidence (e.g. blur, risk flags).")

        return {
            "confidence_score": score,
            "reasons": reasons,
            "is_sufficient": score >= 70
        }
