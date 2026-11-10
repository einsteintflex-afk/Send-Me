import re
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException

TWO = Decimal("0.01")


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(TWO, rounding=ROUND_HALF_UP)


def normalize_gh_phone(raw: str) -> str:
    """Accept 024xxxxxxx, +23324xxxxxxx or 23324xxxxxxx. Return +233XXXXXXXXX."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+233"):
        rest = digits[4:]
    elif digits.startswith("233"):
        rest = digits[3:]
    elif digits.startswith("0"):
        rest = digits[1:]
    else:
        raise HTTPException(422, "Enter a Ghana phone number, for example 024 123 4567.")
    if not re.fullmatch(r"[235]\d{8}", rest):
        raise HTTPException(422, "Enter a valid Ghana phone number, for example 024 123 4567.")
    return "+233" + rest
