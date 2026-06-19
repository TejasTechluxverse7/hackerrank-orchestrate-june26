"""
run.py — Main Execution Pipeline for HackerRank Orchestrate.

Integrates all modules to process claims.csv and generate output.csv.
Validates output schema and logs failures gracefully.
"""

import csv
import logging
from pathlib import Path

# Fix module imports by adding 'code' dir to sys.path
import sys
code_dir = Path(__file__).parent / "code"
sys.path.insert(0, str(code_dir.resolve()))

from pipeline.claim_parser import parse_claim
from pipeline.context_assembler import ContextAssembler
from pipeline.image_analyzer import ImageAnalyzer
from pipeline.evidence_graph import EvidenceGraphBuilder
from pipeline.decision_engine import DecisionEngine
from pipeline.self_verifier import SelfVerifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Standard expected schema for output.csv
OUTPUT_SCHEMA = [
    "user_id", "image_paths", "user_claim", "claim_object",
    "evidence_standard_met", "evidence_standard_met_reason",
    "risk_flags", "issue_type", "object_part", "claim_status",
    "claim_status_justification", "supporting_image_ids",
    "valid_image", "severity"
]


def process_claims():
    # 1. Initialize Pipeline Modules
    dataset_dir = Path("dataset")
    history_path = str(dataset_dir / "user_history.csv")
    req_path = str(dataset_dir / "evidence_requirements.csv")
    
    context_assembler = ContextAssembler(history_path, req_path)
    image_analyzer = ImageAnalyzer()  # Uses mock without live model_client
    graph_builder = EvidenceGraphBuilder()
    decision_engine = DecisionEngine()
    self_verifier = SelfVerifier()

    input_file = dataset_dir / "claims.csv"
    output_file = Path("output.csv")
    
    if not input_file.exists():
        logger.error(f"Input file not found at {input_file}")
        return

    out_records = []
    
    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = row.get("user_id", "unknown")
            try:
                # 1. Parse Input
                claim_text = row.get("user_claim", "")
                claim_object = row.get("claim_object", "")
                image_paths = [p.strip() for p in row.get("image_paths", "").split(";") if p.strip()]
                
                parsed_claim = parse_claim(claim_text, claim_object)
                
                # 2. Assemble Context
                bundle = context_assembler.assemble(parsed_claim, user_id)
                
                # 3. Probe Images (VLM)
                observations = []
                claim_ctx_dict = {
                    "claim_object": parsed_claim.claim_object.value,
                    "claimed_parts": parsed_claim.claimed_parts,
                    "issue_hint": parsed_claim.issue_hint.value
                }
                for path in image_paths:
                    obs = image_analyzer.analyze(path, claim_ctx_dict)
                    observations.append(obs)
                
                # 4. Build Evidence Graph
                graph = graph_builder.build(bundle, observations)
                
                # Extract risk flags for engine
                risk_flags_str = bundle.user_history.history_flags
                risk_flags_list = [f.strip() for f in risk_flags_str.split(";") if f.strip() and f.strip().lower() != "none"]
                
                # 5. Adjudicate
                status, reason = decision_engine.decide(
                    claim=parsed_claim,
                    observations=observations,
                    graph=graph,
                    requirements=bundle.applicable_requirements,
                    risk_flags=risk_flags_list
                )
                
                # 6. Self-Verification
                # Proposed supporting images are any images mapped via SUPPORTS edges
                # We let the verifier check them all for validity
                proposed_images = [Path(p).stem for p in image_paths]
                verify_result = self_verifier.verify(status, graph, parsed_claim, proposed_images)
                
                # Combine risk flags
                final_flags = set(risk_flags_list)
                final_flags.update(verify_result.additional_flags)
                final_flags_str = ";".join(sorted(list(final_flags))) if final_flags else "none"
                
                # Determine justification
                justification = reason
                if not verify_result.is_consistent:
                    justification += " | Verification failures: " + " ; ".join(verify_result.contradictions_found)

                # 7. Map to Output Schema
                out_row = {
                    "user_id": user_id,
                    "image_paths": row.get("image_paths", ""),
                    "user_claim": claim_text,
                    "claim_object": claim_object,
                    "evidence_standard_met": "true" if status.value == "supported" else "false",
                    "evidence_standard_met_reason": reason,
                    "risk_flags": final_flags_str,
                    "issue_type": parsed_claim.issue_hint.value,
                    "object_part": ";".join(parsed_claim.claimed_parts),
                    "claim_status": status.value,
                    "claim_status_justification": justification,
                    "supporting_image_ids": ";".join(verify_result.supporting_image_ids),
                    "valid_image": "true" if verify_result.supporting_image_ids else "false",
                    "severity": parsed_claim.attributes.severity_language or "unknown"
                }
                
                # Validate schema
                for col in OUTPUT_SCHEMA:
                    if col not in out_row:
                        logger.error(f"Schema validation failed: missing column '{col}' for user {user_id}")
                
                out_records.append(out_row)
                logger.info(f"Processed user {user_id}: {status.value}")

            except Exception as e:
                logger.exception(f"Failed to process claim for user {user_id}: {e}")
                # Log failure but continue processing others
                
    # Write Output
    if out_records:
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_SCHEMA)
            writer.writeheader()
            writer.writerows(out_records)
        logger.info(f"Pipeline complete. Generated {output_file} with {len(out_records)} records.")
    else:
        logger.warning("No records processed successfully.")


if __name__ == "__main__":
    process_claims()
