"""
Lead Transformer

Transforms lead data from Excel files into standardized format
with category tagging and enrichment.
"""

from datetime import datetime
from typing import Any

from src.core.interfaces import DataRecord

from .base import BaseTransformer, TransformerRegistry
from .phone_normalizer import PhoneNormalizer


@TransformerRegistry.register("lead")
class LeadTransformer(BaseTransformer):
    """
    Transformer for lead data from Excel files.
    Normalizes lead records with category tagging.
    """

    # Field mappings for common variations
    PHONE_FIELDS = [
        "شماره",
        "تلفن",
        "موبایل",
        "شماره تماس",
        "شماره موبایل",
        "phone",
        "mobile",
        "number",
        "tel",
    ]
    NAME_FIELDS = [
        "نام",
        "نام و نام خانوادگی",
        "name",
        "full_name",
        "contact_name",
        "اسم",
    ]
    COMPANY_FIELDS = [
        "شرکت",
        "نام شرکت",
        "company",
        "organization",
        "سازمان",
    ]
    CITY_FIELDS = [
        "شهر",
        "استان",
        "city",
        "province",
        "region",
        "منطقه",
    ]
    EMAIL_FIELDS = [
        "ایمیل",
        "email",
        "پست الکترونیک",
    ]

    # Category normalization based on filename patterns
    CATEGORY_PATTERNS = {
        "سازنده": "constructor",
        "پیمانکار": "contractor",
        "سیمان": "cement_buyer",
        "کاشی": "tile_buyer",
        "سرامیک": "tile_buyer",
        "بتن": "concrete",
        "نمایشگاه": "exhibition",
        "مشتری": "customer",
        "لید": "lead",
        "سرنخ": "lead",
        "شهرداری": "municipality_contractor",
        "انبوه‌ساز": "mass_builder",
        "فروشنده": "seller",
        "راننده": "driver",
        "پزشک": "doctor",
    }

    # Region mapping
    REGION_MAPPING = {
        "تهران": "Tehran",
        "شیراز": "Shiraz",
        "اصفهان": "Isfahan",
        "مشهد": "Mashhad",
        "تبریز": "Tabriz",
        "گیلان": "Gilan",
        "مازندران": "Mazandaran",
        "کرمان": "Kerman",
        "کرمانشاه": "Kermanshah",
        "قم": "Qom",
        "بوشهر": "Bushehr",
        "سیستان": "Sistan",
        "بلوچستان": "Sistan",
    }

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply lead normalization."""
        result = []

        for record in records:
            data = record.data
            normalized = self._normalize_lead(data)

            result.append(
                DataRecord(
                    data=normalized,
                    source_name=record.source_name,
                    source_type=record.source_type,
                    extracted_at=record.extracted_at,
                    raw_data=record.raw_data,
                )
            )

        return result

    def _normalize_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize a single lead record."""
        # Find and normalize phone number
        phone = self._find_field(data, self.PHONE_FIELDS)
        phone_result = PhoneNormalizer.normalize(phone)

        # Find name
        name = self._find_field(data, self.NAME_FIELDS)

        # Find company
        company = self._find_field(data, self.COMPANY_FIELDS)

        # Find city/region
        city = self._find_field(data, self.CITY_FIELDS)
        region = self._normalize_region(city)

        # Find email
        email = self._find_field(data, self.EMAIL_FIELDS)

        # Extract category from source file
        source_file = data.get("_source_file", "") or data.get("source_file", "")
        category = data.get("_category") or self._extract_category(source_file)
        category_normalized = self._normalize_category(category)

        # Determine lead quality indicators
        has_name = bool(name)
        has_company = bool(company)
        has_email = bool(email)
        quality_score = self._calculate_quality_score(
            phone_result.is_valid,
            phone_result.is_mobile,
            has_name,
            has_company,
            has_email,
        )

        return {
            "phone_number": phone_result.normalized,
            "phone_valid": phone_result.is_valid,
            "phone_carrier": phone_result.carrier,
            "is_mobile": phone_result.is_mobile,
            "name": self._clean_name(name),
            "company": company,
            "city": city,
            "region": region,
            "email": self._normalize_email(email),
            "category": category_normalized,
            "category_raw": category,
            "source_file": source_file,
            "source_sheet": data.get("_source_sheet") or data.get("source_sheet"),
            "quality_score": quality_score,
            "has_name": has_name,
            "has_company": has_company,
            "has_email": has_email,
            "imported_at": datetime.utcnow().isoformat(),
            "raw_data": data,
        }

    def _find_field(self, data: dict[str, Any], field_names: list[str]) -> Any:
        """Find a field value from a list of possible field names."""
        for field in field_names:
            if field in data and data[field] is not None:
                value = data[field]
                if isinstance(value, str) and value.strip():
                    return value.strip()
                elif value:
                    return value
            # Check case-insensitive
            for key in data:
                if key.lower() == field.lower() and data[key] is not None:
                    value = data[key]
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    elif value:
                        return value
        return None

    def _clean_name(self, name: Any) -> str | None:
        """Clean and normalize name."""
        if not name:
            return None

        name_str = str(name).strip()

        # Remove common prefixes/suffixes
        prefixes = ["آقای", "خانم", "جناب", "سرکار", "Mr.", "Mrs.", "Ms."]
        for prefix in prefixes:
            if name_str.startswith(prefix):
                name_str = name_str[len(prefix):].strip()

        return name_str if name_str else None

    def _normalize_email(self, email: Any) -> str | None:
        """Normalize email address."""
        if not email:
            return None

        email_str = str(email).strip().lower()

        # Basic validation
        if "@" not in email_str or "." not in email_str:
            return None

        return email_str

    def _extract_category(self, filename: str) -> str:
        """Extract category from filename."""
        if not filename:
            return "unknown"

        # Remove extension
        name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # Clean up filename
        for char in ["«", "»", "(", ")", "-", "_", "."]:
            name = name.replace(char, " ")

        return name.strip()

    def _normalize_category(self, category: str) -> str:
        """Normalize category to standard value."""
        if not category:
            return "unknown"

        category_lower = category.lower()

        for pattern, normalized in self.CATEGORY_PATTERNS.items():
            if pattern in category_lower or pattern in category:
                return normalized

        return "other"

    def _normalize_region(self, city: Any) -> str | None:
        """Normalize city/region to standard value."""
        if not city:
            return None

        city_str = str(city).strip()

        for pattern, region in self.REGION_MAPPING.items():
            if pattern in city_str:
                return region

        return city_str

    def _calculate_quality_score(
        self,
        phone_valid: bool,
        is_mobile: bool,
        has_name: bool,
        has_company: bool,
        has_email: bool,
    ) -> int:
        """Calculate lead quality score (0-100)."""
        score = 0

        # Phone is essential
        if phone_valid:
            score += 40
            if is_mobile:
                score += 10  # Mobile is preferred for SMS

        # Additional info
        if has_name:
            score += 20
        if has_company:
            score += 20
        if has_email:
            score += 10

        return score

    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate a lead record."""
        data = record.data

        # Phone number is required
        if not data.get("phone_number"):
            return False, "Missing or invalid phone number"

        # Mobile phone is preferred for SMS marketing
        if not data.get("is_mobile"):
            # Not an error, but a warning
            pass

        return True, None

    async def _apply_enrich(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Enrich lead data with additional information."""
        enrichment_sources = config.get("enrichment_sources", {})
        result = []

        for record in records:
            data = dict(record.data)

            # Enrich with existing customer data if available
            phone = data.get("phone_number")
            if phone and "customer_data" in enrichment_sources:
                customer_info = enrichment_sources["customer_data"].get(phone, {})
                data["is_existing_customer"] = bool(customer_info)
                data["customer_info"] = customer_info

            # Enrich with previous interaction data
            if phone and "interaction_data" in enrichment_sources:
                interactions = enrichment_sources["interaction_data"].get(phone, {})
                data["previous_calls"] = interactions.get("call_count", 0)
                data["previous_sms"] = interactions.get("sms_count", 0)
                data["last_interaction"] = interactions.get("last_interaction")

            result.append(
                DataRecord(
                    data=data,
                    source_name=record.source_name,
                    source_type=record.source_type,
                    extracted_at=record.extracted_at,
                    raw_data=record.raw_data,
                )
            )

        return result

