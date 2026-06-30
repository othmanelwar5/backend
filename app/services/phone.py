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


def phone_to_sheet_digits(phone_e164: str) -> str:
    """Format stored E.164 phone for Google Sheets (9665XXXXXXXX, no plus)."""
    digits = "".join(char for char in phone_e164.strip() if char.isdigit())
    if digits.startswith("966"):
        return digits
    if len(digits) == 9 and digits.startswith("5"):
        return f"966{digits}"
    return digits
