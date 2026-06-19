"""
evidence_retriever.py — Evidence Requirements Loader and Retriever.

Loads the evidence_requirements.csv file and provides a retrieval
interface to fetch applicable rules by object and issue, with
automatic fallback to general "all" object requirements.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

@dataclass
class EvidenceRequirement:
    """Structured representation of a single evidence requirement."""
    requirement_id: str
    claim_object: str
    applies_to: str
    minimum_image_evidence: str


class EvidenceRetriever:
    """Loads and retrieves evidence requirements."""

    def __init__(self, csv_path: str):
        self.requirements: List[EvidenceRequirement] = []
        self._load_csv(csv_path)

    def _load_csv(self, path: str) -> None:
        """Load requirements from the CSV file into dataclass instances."""
        if not Path(path).exists():
            logger.error(f"Evidence requirements file not found at: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                req = EvidenceRequirement(
                    requirement_id=row["requirement_id"],
                    claim_object=row["claim_object"],
                    applies_to=row["applies_to"],
                    minimum_image_evidence=row["minimum_image_evidence"]
                )
                self.requirements.append(req)
        
        logger.info(f"Loaded {len(self.requirements)} evidence requirements from {path}")

    def retrieve(self, claim_object: str, issue_family: str) -> List[EvidenceRequirement]:
        """
        Retrieve all evidence requirements applicable to the given claim object
        and issue family.
        
        Automatically includes:
        - Requirements that apply to "all" objects (general fallback).
        - Requirements specific to the object AND the specific issue family.
        - Requirements for multi-image rows (if applicable to all).
        """
        applicable = []
        claim_obj_lower = claim_object.lower()
        issue_family_lower = issue_family.lower()

        for req in self.requirements:
            req_obj = req.claim_object.lower()
            req_applies = req.applies_to.lower()

            # 1. Fallback / General rules applicable to "all" objects
            if req_obj == "all":
                applicable.append(req)
                continue
            
            # 2. Object-specific rules matching the issue family
            if req_obj == claim_obj_lower and req_applies == issue_family_lower:
                applicable.append(req)
                continue

        logger.debug(f"Retrieved {len(applicable)} requirements for object='{claim_object}', issue='{issue_family}'")
        return applicable
