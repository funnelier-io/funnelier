"""
Core Utilities Module
Common helper functions
"""

import re
from datetime import datetime
from typing import Any

import jdatetime


def normalize_phone_number(phone: str) -> str:
    """
    Normalize Iranian phone number to 10-digit format.

    Examples:
        +989123456789 -> 9123456789
        09123456789 -> 9123456789
        9123456789 -> 9123456789
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', str(phone))

    # Handle different formats
    if digits.startswith("98") and len(digits) == 12:
        return digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        return digits[1:]
    elif len(digits) == 10 and digits.startswith("9"):
        return digits
    elif len(digits) == 9:
        return "9" + digits

    return digits


def is_valid_iranian_phone(phone: str) -> bool:
    """Check if phone number is valid Iranian mobile."""
    normalized = normalize_phone_number(phone)

    if len(normalized) != 10:
        return False

    if not normalized.startswith("9"):
        return False

    # Valid Iranian mobile prefixes
    valid_prefixes = [
        "91",  # MCI
        "92",  # Rightel
        "93",  # Irancell
        "94",  # WiMax
        "99",  # Shatel, etc.
        "90",  # MCI, Irancell
    ]

    return any(normalized.startswith(prefix) for prefix in valid_prefixes)


def gregorian_to_jalali(date: datetime) -> str:
    """Convert Gregorian date to Jalali string."""
    jalali = jdatetime.datetime.fromgregorian(datetime=date)
    return jalali.strftime("%Y/%m/%d")


def jalali_to_gregorian(jalali_str: str) -> datetime | None:
    """Convert Jalali string to Gregorian datetime."""
    try:
        # Try different formats
        for fmt in ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"]:
            try:
                jalali = jdatetime.datetime.strptime(jalali_str, fmt)
                return jalali.togregorian()
            except ValueError:
                continue
        return None
    except Exception:
        return None


def format_rial(amount: int) -> str:
    """Format amount in Rial with thousand separators."""
    return f"{amount:,} ریال"


def format_toman(amount: int) -> str:
    """Format amount in Toman with thousand separators."""
    toman = amount // 10
    return f"{toman:,} تومان"


def parse_duration(duration_str: str) -> int:
    """
    Parse duration string to seconds.

    Examples:
        "90 sec" -> 90
        "1:30" -> 90
        "90" -> 90
    """
    if not duration_str:
        return 0

    duration_str = str(duration_str).strip().lower()

    # Remove "sec" suffix
    duration_str = duration_str.replace("sec", "").replace("seconds", "").strip()

    # Handle MM:SS format
    if ":" in duration_str:
        parts = duration_str.split(":")
        if len(parts) == 2:
            try:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            except ValueError:
                return 0

    # Handle plain number
    try:
        return int(float(duration_str))
    except ValueError:
        return 0


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

