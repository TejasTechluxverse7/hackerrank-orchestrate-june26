"""
evaluate.py — Evaluation pipeline for HackerRank Orchestrate.

Compares predictions (output.csv) against ground truth (sample_claims.csv).
Calculates Accuracy, Macro Precision, Macro Recall, and Macro F1 score
for four key target columns: claim_status, issue_type, object_part, severity.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_csv(path: str, key_col: str = "user_id") -> Dict[str, dict]:
    """Loads a CSV into a dictionary keyed by `key_col`."""
    if not Path(path).exists():
        logger.error(f"File not found: {path}")
        return {}

    data = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if key_col in row:
                data[row[key_col]] = row
    return data


def compute_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, float]:
    """
    Computes Accuracy and Macro-Averaged Precision, Recall, and F1-score
    using a pure Python implementation to avoid external dependencies.
    """
    if not y_true:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Normalize casing and stripping spaces just in case
    y_true = [str(y).strip().lower() for y in y_true]
    y_pred = [str(y).strip().lower() for y in y_pred]

    classes = set(y_true) | set(y_pred)
    
    # 1. Accuracy
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    acc = correct / len(y_true)

    # 2. Macro Precision, Recall, F1
    precisions = []
    recalls = []
    f1s = []

    for c in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp == c)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != c and yp == c)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp != c)

        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

        # To match standard macro averaging, we compute metrics for all classes
        # present in either y_true or y_pred.
        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    macro_p = sum(precisions) / len(precisions) if precisions else 0.0
    macro_r = sum(recalls) / len(recalls) if recalls else 0.0
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0

    return {
        "accuracy": acc,
        "precision": macro_p,
        "recall": macro_r,
        "f1": macro_f1
    }


def evaluate(predictions_path: str, ground_truth_path: str):
    """Evaluates the predictions against the ground truth dataset."""
    logger.info("Loading Ground Truth dataset...")
    truth = load_csv(ground_truth_path)
    
    if not truth:
        logger.error("Evaluation aborted: Ground truth missing or empty.")
        return

    logger.info("Loading Predictions...")
    preds = load_csv(predictions_path)
    
    if not preds:
        logger.error(f"Evaluation aborted: Predictions missing at {predictions_path}.")
        return

    # Find common keys
    common_users = set(truth.keys()).intersection(set(preds.keys()))
    logger.info(f"Evaluating on {len(common_users)} overlapping records out of {len(truth)} ground truth records.")

    if not common_users:
        logger.error("No overlapping user_ids found between truth and predictions.")
        return

    target_columns = ["claim_status", "issue_type", "object_part", "severity"]
    results = {}

    for col in target_columns:
        y_true = []
        y_pred = []
        
        for user_id in common_users:
            # We enforce fallback to 'unknown' or empty if column is missing from predictions
            t_val = truth[user_id].get(col, "unknown")
            p_val = preds[user_id].get(col, "unknown")
            
            y_true.append(t_val)
            y_pred.append(p_val)
            
        metrics = compute_metrics(y_true, y_pred)
        results[col] = metrics

    # Print Results nicely
    print("\n" + "="*50)
    print("EVALUATION RESULTS")
    print("="*50)
    for col, metrics in results.items():
        print(f"\n--- {col.upper()} ---")
        print(f"Accuracy  : {metrics['accuracy']:.4f}")
        print(f"Precision : {metrics['precision']:.4f}")
        print(f"Recall    : {metrics['recall']:.4f}")
        print(f"F1 Score  : {metrics['f1']:.4f}")
    print("\n" + "="*50)


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    
    # Anchor to the project root (parent of the 'evaluation' directory)
    project_root = Path(__file__).resolve().parent.parent
    
    parser = argparse.ArgumentParser(description="Evaluate pipeline predictions.")
    parser.add_argument("--preds", default=str(project_root / "output.csv"), help="Path to predictions CSV")
    parser.add_argument("--truth", default=str(project_root / "dataset/sample_claims.csv"), help="Path to ground truth CSV")
    
    args = parser.parse_args()
    evaluate(args.preds, args.truth)
