"""
PoliBrief Backend — Political News Classification Engine
Rule-based weighted keyword and institution classifier for political news.
Classifies articles into one of 7 standardized categories:
  1. Government and Policy
  2. Parliament
  3. Elections
  4. International Politics
  5. Economy and Policy
  6. Political Analysis
  7. Other / Needs Review
"""
import re
from typing import Optional, Tuple

CONFIDENCE_THRESHOLD = 2.5

# Weighted keyword dictionaries for each category
CATEGORY_RULES: dict[str, dict[str, float]] = {
    "Parliament": {
        # High-weight parliamentary / legislative terms
        r"\bparliament\b": 3.0,
        r"\bparliamentary\b": 3.0,
        r"\bcongress\b": 2.5,
        r"\bcongressional\b": 2.5,
        r"\bsenate\b": 3.0,
        r"\bsenator\b": 2.5,
        r"\bhouse of representatives\b": 3.0,
        r"\blawmakers?\b": 2.0,
        r"\blegislation\b": 2.5,
        r"\blegislators?\b": 2.0,
        r"\blegislative\b": 2.0,
        r"\bbill\b": 1.5,
        r"\bcommittee hearing\b": 2.5,
        r"\bfilibuster\b": 3.0,
        r"\bconfirmation vote\b": 3.0,
        r"\bveto\b": 2.0,
        r"\bstatute\b": 2.0,
    },
    "Elections": {
        # High-weight election & campaign terms
        r"\belection\b": 3.5,
        r"\belections\b": 3.5,
        r"\belectoral\b": 3.0,
        r"\bvoter\b": 2.5,
        r"\bvoters\b": 2.5,
        r"\bvoting\b": 2.5,
        r"\bballot\b": 3.0,
        r"\bballots\b": 3.0,
        r"\bpolls?\b": 2.0,
        r"\bpolling\b": 2.5,
        r"\bprimary\b": 2.0,
        r"\bcaucus\b": 3.0,
        r"\bcandidate\b": 2.5,
        r"\bcandidates\b": 2.5,
        r"\bcampaign\b": 2.0,
        r"\brunning mate\b": 3.0,
        r"\bdebates?\b": 1.5,
        r"\bturnout\b": 2.0,
        r"\belection day\b": 3.5,
        r"\bmidterms?\b": 3.0,
    },
    "International Politics": {
        # Diplomacy, foreign policy, geopolitical terms
        r"\bdiplomacy\b": 3.0,
        r"\bdiplomatic\b": 3.0,
        r"\bdiplomats?\b": 2.5,
        r"\bforeign minister\b": 3.0,
        r"\bforeign policy\b": 3.0,
        r"\bstate department\b": 2.5,
        r"\bunited nations\b": 3.0,
        r"\bsecurity council\b": 3.0,
        r"\bnato\b": 3.0,
        r"\beuropean union\b": 3.0,
        r"\bsummit\b": 2.0,
        r"\btreaty\b": 3.0,
        r"\btreaties\b": 3.0,
        r"\bsanctions?\b": 2.5,
        r"\bambassador\b": 2.5,
        r"\bbilateral\b": 2.0,
        r"\bgeopolitical\b": 2.5,
        r"\bpeace talks\b": 3.0,
        r"\bceasefire\b": 2.5,
    },
    "Economy and Policy": {
        # Fiscal policy, treasury, budget, taxation
        r"\bfiscal\b": 3.0,
        r"\bbudget\b": 2.5,
        r"\btax cut\b": 3.0,
        r"\btax reform\b": 3.0,
        r"\btaxation\b": 2.5,
        r"\btariffs?\b": 3.0,
        r"\btreasury\b": 2.5,
        r"\bfederal reserve\b": 3.0,
        r"\binterest rates?\b": 2.0,
        r"\binflation\b": 2.0,
        r"\bdebt ceiling\b": 3.5,
        r"\beconomic stimulus\b": 3.0,
        r"\bappropriations\b": 3.0,
        r"\btrade agreement\b": 3.0,
        r"\bgovernment spending\b": 3.0,
    },
    "Political Analysis": {
        # Commentary, op-ed, strategy, party dynamics
        r"\bpolitical analysis\b": 3.5,
        r"\bstrategy\b": 1.5,
        r"\bopinion\b": 2.0,
        r"\bop-ed\b": 3.0,
        r"\beditorial\b": 2.5,
        r"\bpartisan\b": 2.0,
        r"\bpartisanship\b": 2.5,
        r"\bpolarization\b": 2.5,
        r"\bthink tank\b": 2.5,
        r"\bcoalition\b": 2.0,
        r"\bideology\b": 2.0,
        r"\bapproval rating\b": 2.5,
    },
    "Government and Policy": {
        # Executive, cabinet, federal agencies, supreme court
        r"\bpresident\b": 2.0,
        r"\bpresidential\b": 2.0,
        r"\bprime minister\b": 3.0,
        r"\bwhite house\b": 2.5,
        r"\bcabinet\b": 2.5,
        r"\bexecutive order\b": 3.5,
        r"\bgovernment\b": 1.5,
        r"\bgovernor\b": 2.0,
        r"\bsupreme court\b": 3.0,
        r"\bjustices?\b": 1.5,
        r"\bfederal court\b": 2.5,
        r"\bjudiciary\b": 2.5,
        r"\bregulatory\b": 2.0,
        r"\bregulation\b": 2.0,
        r"\bpublic policy\b": 2.5,
        r"\badministration\b": 1.5,
        r"\bofficial\b": 1.0,
    },
}


def classify_article(
    headline: str,
    description: Optional[str] = None,
    source_category: Optional[str] = None,
) -> Tuple[str, float]:
    """
    Classify an article into a political category based on weighted keyword signals.
    Headline matches receive a 2.0x multiplier because headlines carry primary editorial context.
    Returns: (category_name, confidence_score)
    """
    if not headline:
        return "Other / Needs Review", 0.0

    headline_text = headline.lower()
    body_text = (description or "").lower()

    scores: dict[str, float] = {cat: 0.0 for cat in CATEGORY_RULES}

    # If the source feed explicitly provided a category hint, add slight weight
    if source_category:
        source_cat_lower = source_category.lower()
        for cat in CATEGORY_RULES:
            if cat.lower() in source_cat_lower or source_cat_lower in cat.lower():
                scores[cat] += 1.5

    for category, rules in CATEGORY_RULES.items():
        for pattern, weight in rules.items():
            # Headline match (2.0x weight)
            if re.search(pattern, headline_text, re.IGNORECASE):
                scores[category] += weight * 2.0
            # Description match (1.0x weight)
            elif body_text and re.search(pattern, body_text, re.IGNORECASE):
                scores[category] += weight

    best_category, best_score = max(scores.items(), key=lambda item: item[1])

    if best_score >= CONFIDENCE_THRESHOLD:
        return best_category, round(best_score, 2)

    return "Other / Needs Review", round(best_score, 2)
