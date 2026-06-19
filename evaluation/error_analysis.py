"""
error_analysis.py — Error Analysis and Markdown Report Generator.

Compares output.csv to sample_claims.csv and categorizes prediction
errors into specific qualitative buckets (damage detection, part detection, 
severity, evidence sufficiency, risk flags) to assist with debugging.
Generates a markdown report.
"""

import csv
import logging
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_csv(path: str, key_col: str = "user_id") -> dict:
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


def normalize(val: str) -> str:
    """Helper to normalize strings for comparison."""
    if not val:
        return "unknown"
    # We strip and sort elements for fields like risk_flags which might be semicolon-separated
    items = [i.strip().lower() for i in val.split(";")]
    items = [i for i in items if i and i != "none"]
    if not items:
        return "none"
    return ";".join(sorted(items))


def analyze_errors(preds_path: str, truth_path: str, report_out_path: str = "evaluation/error_report.md"):
    logger.info("Loading ground truth and predictions...")
    truth = load_csv(truth_path)
    preds = load_csv(preds_path)

    if not truth or not preds:
        logger.error("Cannot perform error analysis due to missing data.")
        return

    common_users = set(truth.keys()).intersection(set(preds.keys()))
    if not common_users:
        logger.error("No overlapping user_ids found.")
        return

    # Categorize errors
    errors = {
        "damage detection": [],
        "part detection": [],
        "severity": [],
        "evidence sufficiency": [],
        "risk flags": []
    }

    for user_id in sorted(common_users):
        t_row = truth[user_id]
        p_row = preds[user_id]

        # 1. Damage Detection (issue_type)
        if normalize(t_row.get("issue_type")) != normalize(p_row.get("issue_type")):
            errors["damage detection"].append((user_id, t_row.get("issue_type"), p_row.get("issue_type")))

        # 2. Part Detection (object_part)
        if normalize(t_row.get("object_part")) != normalize(p_row.get("object_part")):
            errors["part detection"].append((user_id, t_row.get("object_part"), p_row.get("object_part")))

        # 3. Severity (severity)
        if normalize(t_row.get("severity")) != normalize(p_row.get("severity")):
            errors["severity"].append((user_id, t_row.get("severity"), p_row.get("severity")))

        # 4. Evidence Sufficiency (claim_status)
        if normalize(t_row.get("claim_status")) != normalize(p_row.get("claim_status")):
            errors["evidence sufficiency"].append((user_id, t_row.get("claim_status"), p_row.get("claim_status")))

        # 5. Risk Flags (risk_flags)
        if normalize(t_row.get("risk_flags")) != normalize(p_row.get("risk_flags")):
            errors["risk flags"].append((user_id, t_row.get("risk_flags"), p_row.get("risk_flags")))

    # Generate Markdown Report
    md_lines = [
        "# Error Analysis Report\n",
        f"**Total Records Evaluated:** {len(common_users)}\n",
        "## Summary of Errors\n"
    ]

    for category, err_list in errors.items():
        md_lines.append(f"- **{category.title()}**: {len(err_list)} errors")
    
    md_lines.append("\n---\n")

    for category, err_list in errors.items():
        md_lines.append(f"## {category.title()} Errors ({len(err_list)})\n")
        if not err_list:
            md_lines.append("*No errors found in this category.*\n")
            continue
            
        md_lines.append("| User ID | Ground Truth | Prediction |")
        md_lines.append("|---|---|---|")
        for err in err_list:
            u_id, t_val, p_val = err
            # Sanitize for markdown tables (remove pipes, newlines, and carriage returns)
            t_val = str(t_val).replace('|', '-').replace('\n', ' ').replace('\r', '') if t_val else "None"
            p_val = str(p_val).replace('|', '-').replace('\n', ' ').replace('\r', '') if p_val else "None"
            md_lines.append(f"| {u_id} | `{t_val}` | `{p_val}` |")
        md_lines.append("\n")

    report_text = "\n".join(md_lines)
    
    # Write to file
    out_path = Path(report_out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info(f"Markdown report generated successfully at: {out_path}")
    print("\n" + report_text)


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    
    project_root = Path(__file__).resolve().parent.parent
    
    parser = argparse.ArgumentParser(description="Generate Error Analysis Markdown Report.")
    parser.add_argument("--preds", default=str(project_root / "output.csv"), help="Path to predictions CSV")
    parser.add_argument("--truth", default=str(project_root / "dataset/sample_claims.csv"), help="Path to ground truth CSV")
    parser.add_argument("--out", default=str(project_root / "evaluation/error_report.md"), help="Path to save markdown report")
    
    args = parser.parse_args()
    analyze_errors(args.preds, args.truth, args.out)
