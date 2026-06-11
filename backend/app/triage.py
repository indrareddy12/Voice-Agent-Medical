import re

# Red flag emergency keywords and patterns (UK centric, as EMMA serves NHS GPs)
EMERGENCY_PATTERNS = [
    # Cardiac / Heart Attack
    r"\bchest\s+(?:pain|pressure|tightness|heaviness)\b",
    r"\bheart\s+attack\b",
    r"\bpain\s+(?:in|radiating\s+to)\s+(?:left\s+)?arm\b",
    r"\bpain\s+in\s+jaw\b",
    # Stroke (FAST)
    r"\bface\s+(?:droop|drooping|dropped)\b",
    r"\barm\s+weakness\b",
    r"\bspeech\s+(?:slur|slurred|slurring)\b",
    r"\bsudden\s+numbness\b",
    r"\bstroke\b",
    # Respiratory / Anaphylaxis
    r"\b(?:severe\s+)?shortness\s+of\s+breath\b",
    r"\b(?:cannot|can't)\s+breathe\b",
    r"\bstrangling|choking\b",
    r"\banaphylaxis|anaphylactic\b",
    r"\bthroat\s+(?:closing|swelling)\b",
    # Trauma / Severe Bleeding / Unconscious
    r"\bheavy\s+bleeding\b",
    r"\bbleed\s+profusely\b",
    r"\bunconscious|passed\s+out|fainted\s+and\s+not\s+waking\b",
    r"\bhead\s+injury\s+(?:with\s+vomiting|and\s+unconscious)\b",
    r"\bpoison|poisoned|overdose\b",
    r"\bsuicid\w*\b" # Self harm risk
]

EMERGENCY_RESPONSE = (
    "I am interrupting our conversation because your symptoms could indicate a serious medical emergency. "
    "Please hang up immediately and call 999, or go to the nearest Accident and Emergency (A&E) department. "
    "Do not wait for a GP appointment. If you are with someone, let them know right away."
)

def check_emergency_triage(text: str) -> dict:
    """
    Checks if the input text contains clinical emergency red flags.
    Returns a dict indicating if it is an emergency and the response to give.
    """
    text_lower = text.lower()
    
    # Check regex patterns
    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, text_lower):
            return {
                "is_emergency": True,
                "reason": f"Matched safety rule: '{pattern}'",
                "response": EMERGENCY_RESPONSE
            }
            
    return {
        "is_emergency": False,
        "reason": None,
        "response": None
    }
