from __future__ import annotations

def normalize_phone(raw: str) -> str:
    """Normalize KSA mobile numbers to E.164 (+9665XXXXXXXX)."""
    digits = "".join(char for char in raw.strip() if char.isdigit())
    if digits.startswith("966"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 9 or not digits.startswith("5"):
        raise ValueError("invalid_ksa_phone")

    return f"+966{digits}"
