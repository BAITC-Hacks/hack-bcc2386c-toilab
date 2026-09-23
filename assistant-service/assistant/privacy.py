"""Conservative rejection before history or LLM transmission; no request-body logging."""
import re

def contains_payment_data(text):
    return bool(re.search(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)",text) or
                re.search(r"\b(?:cvv|cvc|pin|пин)[ :‐-]*\d{3,6}\b",text,re.I) or
                re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{12,30}\b",text,re.I))
