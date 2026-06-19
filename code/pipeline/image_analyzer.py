"""
image_analyzer.py — Module C: Per-Image VLM Probe.

Analyzes a single image independently using a Vision-Language Model (VLM).
Extracts raw visual observations (object, part, damage type, image quality)
without making final adjudication decisions.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

@dataclass
class ImageObservation:
    """Structured raw visual observations from a single image."""
    image_path: str
    visible_object: str
    object_part: str
    issue_type: str
    quality_issues: List[str] = field(default_factory=list)
    is_original: bool = True
    text_overlay_present: bool = False
    raw_severity_observation: str = "unknown"


class ImageAnalyzer:
    """Probes a single image to extract visual evidence."""

    def __init__(self, model_client=None):
        """
        Initializes the image analyzer.
        
        Args:
            model_client: The initialized VLM client (e.g., OpenAI, Anthropic, Gemini).
                          If None, operates in mock/stub mode for testing.
        """
        self.model_client = model_client

    def _build_prompt(self, claim_context: dict) -> str:
        """Constructs the structured prompt for the VLM."""
        return f"""
        Analyze this image for a damage claim review.
        Context: The user claims {claim_context.get('issue_hint', 'damage')} on a {claim_context.get('claim_object', 'object')} ({claim_context.get('claimed_parts', 'unknown part')}).
        
        Please identify:
        1. What object is clearly visible?
        2. What specific part is visible?
        3. Is there visible damage? If so, what type?
        4. Are there any image quality issues (e.g., blurry, low light, glare, cropped)?
        5. Does the image appear to be an original photo, or a screenshot/download?
        6. Is there any instruction text overlaying the image?
        7. What is the severity of the visible damage?

        Return only structured JSON matching the requested fields.
        """

    def analyze(self, image_path: str, claim_context: dict = None) -> ImageObservation:
        """
        Analyze a single image and return structured visual observations.
        
        Note: This module strictly observes the visual evidence present in the 
        image and does not cross-reference or adjudicate the claim status.
        """
        if not Path(image_path).exists():
            logger.error(f"Image not found at: {image_path}")
            return ImageObservation(
                image_path=image_path,
                visible_object="unknown",
                object_part="unknown",
                issue_type="unknown",
                quality_issues=["file_not_found"]
            )

        claim_context = claim_context or {}
        logger.debug(f"Analyzing image: {image_path}")

        if self.model_client is None:
            # Fallback/Mock mode for local testing without API keys
            logger.warning("No VLM client provided. Using mock visual observation.")
            return self._mock_analysis(image_path, claim_context)

        # ------------------------------------------------------------------
        # ACTUAL VLM INVOCATION GOES HERE
        # e.g., response = self.model_client.generate_content(...)
        # parsed = json.loads(response.text)
        # return ImageObservation(**parsed)
        # ------------------------------------------------------------------
        
        raise NotImplementedError("Live VLM integration must be wired up to a specific provider.")

    def _mock_analysis(self, image_path: str, claim_context: dict) -> ImageObservation:
        """Mock analysis for pipeline testing."""
        # Simple heuristics for testing purposes based on file path or context
        issue = claim_context.get("issue_hint", "unknown")
        
        quality = []
        if "blurry" in image_path:
            quality.append("blurry_image")
            
        return ImageObservation(
            image_path=image_path,
            visible_object=claim_context.get("claim_object", "unknown"),
            object_part=claim_context.get("claimed_parts", ["unknown"])[0],
            issue_type=issue,
            quality_issues=quality,
            is_original=True,
            text_overlay_present=False,
            raw_severity_observation="medium"
        )
