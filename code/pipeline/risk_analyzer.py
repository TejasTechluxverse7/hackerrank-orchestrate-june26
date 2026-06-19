"""
risk_analyzer.py — User History and Risk Analyzer.

Loads user_history.csv to evaluate baseline risk profiles based solely
on historical data. Responsible for returning history_summary and
base risk_flags without influencing the visual claim_status.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

@dataclass
class UserRiskProfile:
    """Structured representation of a user's historical risk profile."""
    user_id: str
    history_summary: str
    risk_flags: List[str]


class RiskAnalyzer:
    """Evaluates user history to compute baseline risk flags."""

    def __init__(self, csv_path: str):
        self.user_profiles: Dict[str, UserRiskProfile] = {}
        self._load_csv(csv_path)

    def _load_csv(self, path: str) -> None:
        """Load user history and pre-compute risk profiles."""
        if not Path(path).exists():
            logger.error(f"User history file not found at: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = row["user_id"]
                raw_flags = row.get("history_flags", "none")
                
                # Compute list of valid flags (ignore 'none' as it means empty)
                flags = []
                if raw_flags and raw_flags.lower() != "none":
                    flags = [f.strip() for f in raw_flags.split(";") if f.strip()]

                # Note: Risk computation here explicitly does not affect claim_status.
                # It only informs the final risk_flags string.
                profile = UserRiskProfile(
                    user_id=user_id,
                    history_summary=row.get("history_summary", "No prior history found."),
                    risk_flags=flags
                )
                self.user_profiles[user_id] = profile

        logger.info(f"Loaded {len(self.user_profiles)} user risk profiles from {path}")

    def analyze(self, user_id: str) -> UserRiskProfile:
        """
        Retrieve the risk profile for a user. Returns a clean profile
        if the user is not found in the history database.
        """
        profile = self.user_profiles.get(user_id)
        
        if profile is None:
            logger.debug(f"User {user_id} not found in history. Returning clean profile.")
            return UserRiskProfile(
                user_id=user_id,
                history_summary="No prior history found.",
                risk_flags=[]
            )
            
        logger.debug(f"Analyzed risk for {user_id}: flags={profile.risk_flags}")
        return profile
