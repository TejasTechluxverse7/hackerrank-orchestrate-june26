"""
claim_parser.py — Module A: Conversation parsing and canonical claim extraction.

Segments a user_claim transcript into turns, walks them reverse-chronologically
to extract the canonical claim (suppressing distractors), detects multi-part
claims, and maps keywords to structured enums for downstream modules.
"""

import logging
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums — mirrors problem_statement.md allowed values
# ---------------------------------------------------------------------------

class ClaimObject(str, Enum):
    CAR = "car"
    LAPTOP = "laptop"
    PACKAGE = "package"


class IssueType(str, Enum):
    DENT = "dent"
    SCRATCH = "scratch"
    CRACK = "crack"
    GLASS_SHATTER = "glass_shatter"
    BROKEN_PART = "broken_part"
    MISSING_PART = "missing_part"
    TORN_PACKAGING = "torn_packaging"
    CRUSHED_PACKAGING = "crushed_packaging"
    WATER_DAMAGE = "water_damage"
    STAIN = "stain"
    NONE = "none"
    UNKNOWN = "unknown"


class CarPart(str, Enum):
    FRONT_BUMPER = "front_bumper"
    REAR_BUMPER = "rear_bumper"
    DOOR = "door"
    HOOD = "hood"
    WINDSHIELD = "windshield"
    SIDE_MIRROR = "side_mirror"
    HEADLIGHT = "headlight"
    TAILLIGHT = "taillight"
    FENDER = "fender"
    QUARTER_PANEL = "quarter_panel"
    BODY = "body"
    UNKNOWN = "unknown"


class LaptopPart(str, Enum):
    SCREEN = "screen"
    KEYBOARD = "keyboard"
    TRACKPAD = "trackpad"
    HINGE = "hinge"
    LID = "lid"
    CORNER = "corner"
    PORT = "port"
    BASE = "base"
    BODY = "body"
    UNKNOWN = "unknown"


class PackagePart(str, Enum):
    BOX = "box"
    PACKAGE_CORNER = "package_corner"
    PACKAGE_SIDE = "package_side"
    SEAL = "seal"
    LABEL = "label"
    CONTENTS = "contents"
    ITEM = "item"
    UNKNOWN = "unknown"


class IssueFamily(str, Enum):
    """Maps to evidence_requirements.csv `applies_to` column."""
    DENT_OR_SCRATCH = "dent or scratch"
    CRACK_BROKEN_MISSING = "crack, broken, or missing part"
    VEHICLE_IDENTITY = "vehicle identity or orientation"
    SCREEN_KEYBOARD_TRACKPAD = "screen, keyboard, or trackpad"
    HINGE_LID_CORNER_BODY = "hinge, lid, corner, body, or port"
    CRUSHED_TORN_SEAL = "crushed, torn, or seal damage"
    WATER_STAIN_LABEL = "water, stain, or label damage"
    CONTENTS_INNER = "contents or inner item"
    GENERAL = "general claim review"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    """A single turn in the claim conversation."""
    speaker: str = Field(description="'customer' or 'support'")
    text: str = Field(description="Raw text of this turn")


class ClaimAttributes(BaseModel):
    """Optional qualifiers extracted from the conversation."""
    color: Optional[str] = Field(default=None, description="Vehicle/object color if mentioned")
    side: Optional[str] = Field(default=None, description="'left' or 'right' if mentioned")
    severity_language: Optional[str] = Field(
        default=None,
        description="Severity phrasing used by customer, e.g. 'pretty bad', 'minor'",
    )


class ParsedClaim(BaseModel):
    """Structured output of the claim parser."""
    claim_object: ClaimObject
    claimed_parts: List[str] = Field(description="One or more object_part enum values")
    issue_hint: IssueType = Field(
        default=IssueType.UNKNOWN,
        description="Best-guess issue type from conversation keywords",
    )
    issue_family: IssueFamily = Field(description="Evidence-requirement family for lookup")
    damage_summary: str = Field(description="One-sentence natural-language summary of the claim")
    is_multi_part: bool = Field(default=False, description="True when ≥2 parts are claimed")
    attributes: ClaimAttributes = Field(default_factory=ClaimAttributes)
    canonical_turn: str = Field(description="The customer turn that defines the claim")
    turns: List[ConversationTurn] = Field(description="All parsed conversation turns")


# ---------------------------------------------------------------------------
# Keyword → enum mappings
# ---------------------------------------------------------------------------

_PART_KEYWORDS: dict[str, dict[str, str]] = {
    "car": {
        "front bumper": CarPart.FRONT_BUMPER,
        "rear bumper": CarPart.REAR_BUMPER,
        "back bumper": CarPart.REAR_BUMPER,
        "bumper": CarPart.REAR_BUMPER,          # ambiguous — context resolves later
        "door": CarPart.DOOR,
        "door panel": CarPart.DOOR,
        "hood": CarPart.HOOD,
        "top panel": CarPart.HOOD,
        "windshield": CarPart.WINDSHIELD,
        "front glass": CarPart.WINDSHIELD,
        "pantalla": CarPart.WINDSHIELD,         # Spanish
        "side mirror": CarPart.SIDE_MIRROR,
        "mirror": CarPart.SIDE_MIRROR,
        "headlight": CarPart.HEADLIGHT,
        "head light": CarPart.HEADLIGHT,
        "taillight": CarPart.TAILLIGHT,
        "tail light": CarPart.TAILLIGHT,
        "back light": CarPart.TAILLIGHT,
        "fender": CarPart.FENDER,
        "quarter panel": CarPart.QUARTER_PANEL,
        "body": CarPart.BODY,
        "body panel": CarPart.BODY,
        "parachoques": CarPart.REAR_BUMPER,     # Spanish: bumper
        "parachoques trasero": CarPart.REAR_BUMPER,
    },
    "laptop": {
        "screen": LaptopPart.SCREEN,
        "display": LaptopPart.SCREEN,
        "display glass": LaptopPart.SCREEN,
        "pantalla": LaptopPart.SCREEN,          # Spanish
        "keyboard": LaptopPart.KEYBOARD,
        "keys": LaptopPart.KEYBOARD,
        "keycaps": LaptopPart.KEYBOARD,
        "teclas": LaptopPart.KEYBOARD,          # Spanish
        "trackpad": LaptopPart.TRACKPAD,
        "palm-rest": LaptopPart.TRACKPAD,
        "hinge": LaptopPart.HINGE,
        "lid": LaptopPart.LID,
        "corner": LaptopPart.CORNER,
        "port": LaptopPart.PORT,
        "base": LaptopPart.BASE,
        "body": LaptopPart.BODY,
    },
    "package": {
        "box": PackagePart.BOX,
        "shipping box": PackagePart.BOX,
        "delivery box": PackagePart.BOX,
        "cardboard box": PackagePart.BOX,
        "corner": PackagePart.PACKAGE_CORNER,
        "package corner": PackagePart.PACKAGE_CORNER,
        "side": PackagePart.PACKAGE_SIDE,
        "package side": PackagePart.PACKAGE_SIDE,
        "surface": PackagePart.PACKAGE_SIDE,
        "seal": PackagePart.SEAL,
        "seal area": PackagePart.SEAL,
        "label": PackagePart.LABEL,
        "shipping label": PackagePart.LABEL,
        "contents": PackagePart.CONTENTS,
        "item": PackagePart.ITEM,
        "product": PackagePart.CONTENTS,
        "item inside": PackagePart.ITEM,
        "parcel": PackagePart.BOX,
    },
}

_ISSUE_KEYWORDS: dict[str, IssueType] = {
    "dent": IssueType.DENT,
    "dented": IssueType.DENT,
    "deformation": IssueType.DENT,
    "hail": IssueType.DENT,
    "scratch": IssueType.SCRATCH,
    "scratched": IssueType.SCRATCH,
    "scrape": IssueType.SCRATCH,
    "mark": IssueType.SCRATCH,
    "crack": IssueType.CRACK,
    "cracked": IssueType.CRACK,
    "shatter": IssueType.GLASS_SHATTER,
    "shattered": IssueType.GLASS_SHATTER,
    "broken": IssueType.BROKEN_PART,
    "broke": IssueType.BROKEN_PART,
    "missing": IssueType.MISSING_PART,
    "faltan": IssueType.MISSING_PART,           # Spanish
    "torn": IssueType.TORN_PACKAGING,
    "torn-open": IssueType.TORN_PACKAGING,
    "opened": IssueType.TORN_PACKAGING,
    "phati": IssueType.TORN_PACKAGING,          # Hindi
    "crushed": IssueType.CRUSHED_PACKAGING,
    "crush": IssueType.CRUSHED_PACKAGING,
    "dab gaya": IssueType.CRUSHED_PACKAGING,    # Hindi
    "water damage": IssueType.WATER_DAMAGE,
    "water damaged": IssueType.WATER_DAMAGE,
    "wet": IssueType.WATER_DAMAGE,
    "liquid damage": IssueType.WATER_DAMAGE,
    "liquid": IssueType.WATER_DAMAGE,
    "spill": IssueType.STAIN,
    "spilled": IssueType.STAIN,
    "stain": IssueType.STAIN,
    "oily": IssueType.STAIN,
    "oil stain": IssueType.STAIN,
    "sticky": IssueType.STAIN,
}

_COLOR_PATTERN = re.compile(
    r"\b(black|white|red|blue|green|silver|grey|gray|brown|yellow|orange)\b",
    re.IGNORECASE,
)
_SIDE_PATTERN = re.compile(r"\b(left|right)\b", re.IGNORECASE)
_SEVERITY_PHRASES = [
    "pretty bad", "badly", "severe", "major", "shattered",
    "minor", "small", "light", "little",
]

# Negation phrases that disqualify a part mentioned in the same turn.
_NEGATION_PATTERN = re.compile(
    r"\b(not the|not about|not\b.*\bclaim|nahi kar raha|nahi hai|nahi|no,? (?:only|just)|ignore)\b",
    re.IGNORECASE,
)

# Positive-anchor pattern: "sirf X" / "only X" means everything else is negated.
_ONLY_PATTERN = re.compile(
    r"\b(?:sirf|only|just)\s+(.{3,40?})\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _segment_turns(raw: str) -> List[ConversationTurn]:
    """Split a pipe-delimited transcript into labeled turns."""
    segments = [s.strip() for s in raw.split("|") if s.strip()]
    turns: List[ConversationTurn] = []
    for seg in segments:
        lower = seg.lower()
        if lower.startswith("customer:"):
            speaker = "customer"
            text = seg.split(":", 1)[1].strip()
        elif lower.startswith(("support:", "agent:", "soporte:")):
            speaker = "support"
            text = seg.split(":", 1)[1].strip()
        else:
            # Continuation of previous speaker or unlabeled — treat as customer.
            speaker = turns[-1].speaker if turns else "customer"
            text = seg
        turns.append(ConversationTurn(speaker=speaker, text=text))
    logger.debug("Segmented %d turns (%d customer)", len(turns),
                 sum(1 for t in turns if t.speaker == "customer"))
    return turns


# Keywords short enough to cause false positives inside compound words.
_SHORT_KW_THRESHOLD = 5


def _match_parts(text: str, object_type: str) -> List[str]:
    """Return all object_part enum values whose keywords appear in *text*.

    Short keywords (≤5 chars) use word-boundary regex to avoid false matches
    inside Hindi compound words (e.g. 'side' inside 'inside').
    """
    text_lower = text.lower()
    mapping = _PART_KEYWORDS.get(object_type, {})
    # Sort by descending keyword length so multi-word phrases match first.
    found: dict[str, int] = {}
    for keyword, part_val in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        if part_val in found:
            continue
        if len(keyword) <= _SHORT_KW_THRESHOLD:
            m = re.search(r'\b' + re.escape(keyword) + r'\b', text_lower)
            if m:
                found[part_val] = m.start()
        else:
            idx = text_lower.find(keyword)
            if idx != -1:
                found[part_val] = idx
    # Return parts sorted by position in text (earliest mention first).
    return [p for p, _ in sorted(found.items(), key=lambda kv: kv[1])]


def _match_issue(text: str) -> IssueType:
    """Return the best-matching issue type from keywords in *text*."""
    text_lower = text.lower()
    for keyword, issue in sorted(_ISSUE_KEYWORDS.items(), key=lambda kv: -len(kv[0])):
        if keyword in text_lower:
            return issue
    return IssueType.UNKNOWN


def _extract_attributes(text: str) -> ClaimAttributes:
    """Pull color, side, and severity language from text."""
    color_m = _COLOR_PATTERN.search(text)
    side_m = _SIDE_PATTERN.search(text)
    sev = None
    text_lower = text.lower()
    for phrase in _SEVERITY_PHRASES:
        if phrase in text_lower:
            sev = phrase
            break
    return ClaimAttributes(
        color=color_m.group(1).lower() if color_m else None,
        side=side_m.group(1).lower() if side_m else None,
        severity_language=sev,
    )


_POST_NEGATION_PATTERN = re.compile(
    r"\b(nahi kar raha|nahi hai|nahi|claim nahi)\b",
    re.IGNORECASE,
)


def _is_negated(text: str, part_keyword: str) -> bool:
    """Check if a part mention is explicitly negated in this turn.

    Uses sentence-level scoping: finds the clause (split by sentence-ending
    punctuation) containing the keyword, then checks for negation markers
    within that clause only. Also handles Hindi SOV post-position negation.
    """
    text_lower = text.lower()
    kw_lower = part_keyword.lower()
    idx = text_lower.find(kw_lower)
    if idx == -1:
        return False

    # Find the clause containing this keyword.
    # Split on sentence-ending punctuation: .  !  ?  ;  and also comma for
    # clauses like "Not the keyboard, the screen is the issue".
    clause_start = max(
        text_lower.rfind(".", 0, idx),
        text_lower.rfind("!", 0, idx),
        text_lower.rfind("?", 0, idx),
        -1,
    ) + 1
    clause_end_candidates = [
        text_lower.find(".", idx),
        text_lower.find("!", idx),
        text_lower.find("?", idx),
    ]
    clause_end = min((c for c in clause_end_candidates if c != -1), default=len(text_lower))
    clause = text_lower[clause_start:clause_end]
    kw_pos_in_clause = idx - clause_start

    # Check for pre-keyword negation within the clause.
    pre_window = clause[:kw_pos_in_clause]
    if _NEGATION_PATTERN.search(pre_window):
        return True

    # Check for Hindi post-position negation within the clause.
    post_window = clause[kw_pos_in_clause + len(kw_lower):]
    if _POST_NEGATION_PATTERN.search(post_window):
        return True

    # Check for "sirf/only X" where X is a DIFFERENT part — negates this one.
    only_m = _ONLY_PATTERN.search(text_lower)
    if only_m and kw_lower not in only_m.group(1).lower():
        return True
    return False


def _resolve_bumper_direction(turns: List[ConversationTurn]) -> Optional[str]:
    """Disambiguate bare 'bumper' to front or rear from conversation context."""
    full = " ".join(t.text.lower() for t in turns)
    front_signals = sum(1 for w in ["front", "frente", "forward"] if w in full)
    rear_signals = sum(1 for w in ["rear", "back", "behind", "trasero", "pichhe"] if w in full)
    if front_signals > rear_signals:
        return CarPart.FRONT_BUMPER
    if rear_signals > front_signals:
        return CarPart.REAR_BUMPER
    return None


def _resolve_issue_family(
    claim_object: ClaimObject,
    issue: IssueType,
    parts: List[str],
) -> IssueFamily:
    """Map (object, issue, parts) to the evidence-requirements family."""
    if claim_object == ClaimObject.CAR:
        if issue in (IssueType.DENT, IssueType.SCRATCH):
            return IssueFamily.DENT_OR_SCRATCH
        if issue in (IssueType.CRACK, IssueType.GLASS_SHATTER,
                     IssueType.BROKEN_PART, IssueType.MISSING_PART):
            return IssueFamily.CRACK_BROKEN_MISSING
        return IssueFamily.GENERAL

    if claim_object == ClaimObject.LAPTOP:
        surface_parts = {LaptopPart.SCREEN, LaptopPart.KEYBOARD, LaptopPart.TRACKPAD}
        if any(p in surface_parts for p in parts):
            return IssueFamily.SCREEN_KEYBOARD_TRACKPAD
        structural_parts = {LaptopPart.HINGE, LaptopPart.LID, LaptopPart.CORNER,
                            LaptopPart.BODY, LaptopPart.BASE, LaptopPart.PORT}
        if any(p in structural_parts for p in parts):
            return IssueFamily.HINGE_LID_CORNER_BODY
        return IssueFamily.GENERAL

    if claim_object == ClaimObject.PACKAGE:
        if issue in (IssueType.CRUSHED_PACKAGING, IssueType.TORN_PACKAGING):
            return IssueFamily.CRUSHED_TORN_SEAL
        if any(p in (PackagePart.SEAL,) for p in parts):
            return IssueFamily.CRUSHED_TORN_SEAL
        if issue in (IssueType.WATER_DAMAGE, IssueType.STAIN):
            return IssueFamily.WATER_STAIN_LABEL
        if any(p in (PackagePart.LABEL,) for p in parts):
            return IssueFamily.WATER_STAIN_LABEL
        if any(p in (PackagePart.CONTENTS, PackagePart.ITEM) for p in parts):
            return IssueFamily.CONTENTS_INNER
        return IssueFamily.GENERAL

    return IssueFamily.GENERAL


def _build_damage_summary(
    claim_object: ClaimObject,
    parts: List[str],
    issue: IssueType,
    attrs: ClaimAttributes,
) -> str:
    """Generate a concise natural-language damage summary."""
    parts_str = " and ".join(parts) if parts else "unknown part"
    obj = claim_object.value
    issue_str = issue.value.replace("_", " ") if issue != IssueType.UNKNOWN else "damage"

    qualifiers: List[str] = []
    if attrs.color:
        qualifiers.append(attrs.color)
    if attrs.side:
        qualifiers.append(f"{attrs.side}-side")
    qual_prefix = f"{' '.join(qualifiers)} " if qualifiers else ""

    return f"Claim: {issue_str} on {qual_prefix}{obj} {parts_str}."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_claim(user_claim: str, claim_object: str) -> ParsedClaim:
    """Parse a raw claim transcript into a structured claim record.

    This is the single public entry point for Module A.

    Args:
        user_claim: Pipe-delimited conversation transcript.
        claim_object: One of 'car', 'laptop', 'package'.

    Returns:
        A ``ParsedClaim`` with the canonical claim, parts, issue hint,
        issue family, damage summary, and extracted attributes.
    """
    obj = ClaimObject(claim_object)
    turns = _segment_turns(user_claim)
    customer_turns = [t for t in turns if t.speaker == "customer"]

    if not customer_turns:
        logger.warning("No customer turns found — returning unknown claim")
        return ParsedClaim(
            claim_object=obj,
            claimed_parts=["unknown"],
            issue_hint=IssueType.UNKNOWN,
            issue_family=IssueFamily.GENERAL,
            damage_summary=f"Claim: unknown damage on {obj.value}.",
            canonical_turn="",
            turns=turns,
        )

    # --- Reverse-walk: find canonical turn(s) --------------------------------
    canonical_turn: Optional[ConversationTurn] = None
    collected_parts: List[str] = []
    best_issue = IssueType.UNKNOWN

    # Track turns where all parts were negated but issue keywords exist.
    issue_only_turn: Optional[ConversationTurn] = None
    issue_only_issue: Optional[IssueType] = None

    for turn in reversed(customer_turns):
        parts_in_turn = _match_parts(turn.text, obj.value)

        # Filter out negated parts ("Not the keyboard").
        mapping = _PART_KEYWORDS.get(obj.value, {})
        non_negated: List[str] = []
        for p in parts_in_turn:
            negated = False
            for kw, val in mapping.items():
                if val == p and _is_negated(turn.text, kw):
                    negated = True
                    break
            if not negated:
                non_negated.append(p)

        if non_negated and canonical_turn is None:
            if issue_only_turn is not None:
                canonical_turn = issue_only_turn
                current_turn_issue = _match_issue(turn.text)
                best_issue = current_turn_issue if current_turn_issue != IssueType.UNKNOWN else (issue_only_issue or IssueType.UNKNOWN)
                # Pick only the most specific/primary part (first mentioned)
                collected_parts = [non_negated[0]]
                logger.debug("Part resolved from earlier turn for issue_only: %s", collected_parts)
                break
            else:
                canonical_turn = turn
                collected_parts = non_negated
                best_issue = _match_issue(turn.text)
                logger.debug("Canonical turn found: %s", turn.text[:80])
                break  # First (latest) turn with valid parts wins.

        # If this turn had parts but ALL were negated, and it carries an issue
        # keyword, remember it — the intent is here but parts come from earlier.
        if parts_in_turn and not non_negated and issue_only_turn is None:
            turn_issue = _match_issue(turn.text)
            if turn_issue != IssueType.UNKNOWN:
                issue_only_turn = turn
                issue_only_issue = turn_issue
                logger.debug("Issue-only turn (all parts negated): %s",
                             turn.text[:80])

    # Fallback: if no valid parts were found anywhere
    if canonical_turn is None:
        if issue_only_turn is not None:
            canonical_turn = issue_only_turn
            collected_parts = ["unknown"]
            best_issue = issue_only_issue or IssueType.UNKNOWN
            logger.debug("No valid parts found — falling back to issue_only_turn")
        else:
            canonical_turn = customer_turns[-1]
            collected_parts = ["unknown"]
            best_issue = _match_issue(canonical_turn.text)
            logger.debug("No explicit part found — falling back to last customer turn")

    # If issue still unknown, scan all customer turns for clues.
    if best_issue == IssueType.UNKNOWN:
        for turn in reversed(customer_turns):
            candidate = _match_issue(turn.text)
            if candidate != IssueType.UNKNOWN:
                best_issue = candidate
                logger.debug("Issue resolved from earlier turn: %s", best_issue)
                break

    # --- Disambiguate bare "bumper" for cars ----------------------------------
    if obj == ClaimObject.CAR and CarPart.REAR_BUMPER in collected_parts:
        # REAR_BUMPER is the default for bare "bumper" — check context.
        full_canonical = canonical_turn.text.lower()
        if "front" in full_canonical or "frente" in full_canonical:
            collected_parts = [
                CarPart.FRONT_BUMPER if p == CarPart.REAR_BUMPER else p
                for p in collected_parts
            ]
        elif "rear" not in full_canonical and "back" not in full_canonical:
            resolved = _resolve_bumper_direction(turns)
            if resolved:
                collected_parts = [
                    resolved if p == CarPart.REAR_BUMPER else p
                    for p in collected_parts
                ]

    # --- Deduplicate parts ----------------------------------------------------
    seen: set[str] = set()
    deduped: List[str] = []
    for p in collected_parts:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    collected_parts = deduped

    # --- Attributes -----------------------------------------------------------
    full_text = " ".join(t.text for t in customer_turns)
    attrs = _extract_attributes(full_text)

    # --- Issue family ---------------------------------------------------------
    family = _resolve_issue_family(obj, best_issue, collected_parts)

    # --- Multi-part detection -------------------------------------------------
    is_multi = len(set(collected_parts)) >= 2

    # --- Damage summary -------------------------------------------------------
    summary = _build_damage_summary(obj, collected_parts, best_issue, attrs)

    result = ParsedClaim(
        claim_object=obj,
        claimed_parts=collected_parts,
        issue_hint=best_issue,
        issue_family=family,
        damage_summary=summary,
        is_multi_part=is_multi,
        attributes=attrs,
        canonical_turn=canonical_turn.text,
        turns=turns,
    )
    logger.info("Parsed claim: parts=%s issue=%s family=%s multi=%s",
                collected_parts, best_issue.value, family.value, is_multi)
    return result
