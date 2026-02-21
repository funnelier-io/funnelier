"""
Phone Number Normalizer

Provides phone number normalization and validation utilities.
Supports Iranian phone numbers with international format.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class PhoneValidationResult:
    """Result of phone number validation."""

    is_valid: bool
    normalized: str | None
    original: str
    error: str | None = None
    carrier: str | None = None
    is_mobile: bool = False


class PhoneNormalizer:
    """
    Phone number normalizer for Iranian numbers.
    Handles various input formats and normalizes to international format.
    """

    # Iranian mobile prefixes by carrier
    MOBILE_PREFIXES = {
        # MCI (Hamrah Aval)
        "910": "MCI",
        "911": "MCI",
        "912": "MCI",
        "913": "MCI",
        "914": "MCI",
        "915": "MCI",
        "916": "MCI",
        "917": "MCI",
        "918": "MCI",
        "919": "MCI",
        # Irancell
        "901": "Irancell",
        "902": "Irancell",
        "903": "Irancell",
        "930": "Irancell",
        "933": "Irancell",
        "935": "Irancell",
        "936": "Irancell",
        "937": "Irancell",
        "938": "Irancell",
        "939": "Irancell",
        # Rightel
        "920": "Rightel",
        "921": "Rightel",
        "922": "Rightel",
        # Shatel Mobile
        "998": "Shatel",
        # Talia
        "932": "Talia",
        # Aptel
        "999": "Aptel",
    }

    # Landline area codes (major cities)
    AREA_CODES = {
        "21": "Tehran",
        "26": "Karaj",
        "31": "Isfahan",
        "41": "Tabriz",
        "51": "Mashhad",
        "71": "Shiraz",
        "44": "Urmia",
        "34": "Kerman",
        "35": "Yazd",
        "38": "Shahrekord",
        "45": "Ardabil",
        "66": "Khorramabad",
        "74": "Bushehr",
        "76": "Bandar Abbas",
        "77": "Zahedan",
        "81": "Hamadan",
        "83": "Kermanshah",
        "84": "Ilam",
        "86": "Arak",
        "87": "Sanandaj",
        "13": "Rasht",
        "11": "Sari",
        "17": "Gorgan",
        "23": "Semnan",
        "24": "Zanjan",
        "25": "Qom",
        "28": "Qazvin",
        "61": "Ahvaz",
        "54": "Birjand",
        "56": "Bojnurd",
    }

    COUNTRY_CODE = "98"

    @classmethod
    def normalize(cls, phone: Any) -> PhoneValidationResult:
        """
        Normalize a phone number to international format (98XXXXXXXXXX).

        Args:
            phone: Phone number in any format

        Returns:
            PhoneValidationResult with normalized number
        """
        if phone is None:
            return PhoneValidationResult(
                is_valid=False,
                normalized=None,
                original="",
                error="Phone number is empty",
            )

        original = str(phone).strip()

        # Handle scientific notation from Excel
        if "e" in original.lower() or "E" in original:
            try:
                original = str(int(float(original)))
            except (ValueError, TypeError):
                pass

        # Extract digits only
        digits = "".join(c for c in original if c.isdigit())

        if not digits:
            return PhoneValidationResult(
                is_valid=False,
                normalized=None,
                original=original,
                error="No digits found in phone number",
            )

        # Remove leading + if present
        if original.startswith("+"):
            pass  # digits already extracted

        # Normalize to international format
        if digits.startswith("00"):
            # International format with 00
            digits = digits[2:]
        elif digits.startswith("0"):
            # National format - remove leading 0 and add country code
            digits = cls.COUNTRY_CODE + digits[1:]
        elif not digits.startswith(cls.COUNTRY_CODE):
            # Assume national format without leading 0
            digits = cls.COUNTRY_CODE + digits

        # Validate length
        if len(digits) < 10:
            return PhoneValidationResult(
                is_valid=False,
                normalized=None,
                original=original,
                error="Phone number too short",
            )

        if len(digits) > 12:
            return PhoneValidationResult(
                is_valid=False,
                normalized=None,
                original=original,
                error="Phone number too long",
            )

        # Validate it's an Iranian number
        if not digits.startswith(cls.COUNTRY_CODE):
            return PhoneValidationResult(
                is_valid=False,
                normalized=None,
                original=original,
                error="Not an Iranian phone number",
            )

        # Extract the national part (without country code)
        national = digits[2:]

        # Check if mobile
        is_mobile = False
        carrier = None
        prefix = national[:3]
        if prefix in cls.MOBILE_PREFIXES:
            is_mobile = True
            carrier = cls.MOBILE_PREFIXES[prefix]
            # Mobile numbers should be 10 digits (without country code)
            if len(national) != 10:
                return PhoneValidationResult(
                    is_valid=False,
                    normalized=None,
                    original=original,
                    error=f"Invalid mobile number length: {len(national)} digits",
                )
        else:
            # Check if landline
            area_code = national[:2]
            if area_code in cls.AREA_CODES:
                carrier = f"Landline ({cls.AREA_CODES[area_code]})"
            # Landline numbers vary in length (8-10 digits without country code)
            if len(national) < 8:
                return PhoneValidationResult(
                    is_valid=False,
                    normalized=None,
                    original=original,
                    error="Invalid landline number length",
                )

        return PhoneValidationResult(
            is_valid=True,
            normalized=digits,
            original=original,
            carrier=carrier,
            is_mobile=is_mobile,
        )

    @classmethod
    def normalize_batch(cls, phones: list[Any]) -> list[PhoneValidationResult]:
        """Normalize a batch of phone numbers."""
        return [cls.normalize(phone) for phone in phones]

    @classmethod
    def extract_phone_from_text(cls, text: str) -> list[str]:
        """
        Extract all phone numbers from text.

        Args:
            text: Text that may contain phone numbers

        Returns:
            List of normalized phone numbers
        """
        # Pattern for Iranian phone numbers
        patterns = [
            r"\+98\d{10}",  # International format
            r"0098\d{10}",  # International with 00
            r"09\d{9}",  # National mobile
            r"0\d{2,3}[-\s]?\d{7,8}",  # National landline
        ]

        found = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            found.extend(matches)

        # Normalize and deduplicate
        normalized = []
        seen = set()
        for phone in found:
            result = cls.normalize(phone)
            if result.is_valid and result.normalized not in seen:
                seen.add(result.normalized)
                normalized.append(result.normalized)

        return normalized

    @classmethod
    def format_display(cls, phone: str, format_type: str = "international") -> str:
        """
        Format phone number for display.

        Args:
            phone: Normalized phone number
            format_type: One of 'international', 'national', 'local'

        Returns:
            Formatted phone number
        """
        result = cls.normalize(phone)
        if not result.is_valid or not result.normalized:
            return phone

        normalized = result.normalized
        national = normalized[2:]  # Remove country code

        if format_type == "international":
            return f"+{normalized[:2]} {national[:3]} {national[3:6]} {national[6:]}"
        elif format_type == "national":
            return f"0{national[:3]} {national[3:6]} {national[6:]}"
        elif format_type == "local":
            return f"0{national}"
        else:
            return normalized

    @classmethod
    def is_same_number(cls, phone1: Any, phone2: Any) -> bool:
        """Check if two phone numbers are the same."""
        result1 = cls.normalize(phone1)
        result2 = cls.normalize(phone2)

        if not result1.is_valid or not result2.is_valid:
            return False

        return result1.normalized == result2.normalized

