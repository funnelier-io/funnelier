"""
Predictive Analytics Service
Churn prediction, lead scoring, campaign ROI, A/B test significance
Uses statistical methods — no heavy ML dependencies required.
"""

import math
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Data Models ──────────────────────────────────────


class ChurnPrediction(BaseModel):
    """Churn risk for a single contact."""
    contact_id: UUID
    phone_number: str
    name: str | None = None
    segment: str | None = None
    churn_probability: float  # 0.0 – 1.0
    risk_level: str  # low, medium, high, critical
    risk_factors: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    days_since_last_activity: int | None = None
    last_activity_date: datetime | None = None


class ChurnSummary(BaseModel):
    """Aggregate churn risk report."""
    analysis_date: datetime
    total_contacts: int
    at_risk_count: int
    at_risk_percentage: float
    risk_distribution: dict[str, int]  # {low: N, medium: N, high: N, critical: N}
    top_risk_contacts: list[ChurnPrediction]
    estimated_revenue_at_risk: int = 0
    recommendations: list[str] = Field(default_factory=list)


class LeadScore(BaseModel):
    """Score for a single lead."""
    contact_id: UUID
    phone_number: str
    name: str | None = None
    category: str | None = None
    score: float  # 0 – 100
    grade: str  # A, B, C, D, F
    scoring_factors: dict[str, float] = Field(default_factory=dict)
    recommended_action: str = ""


class LeadScoringResult(BaseModel):
    """Batch lead scoring result."""
    analysis_date: datetime
    total_scored: int
    grade_distribution: dict[str, int]  # {A: N, B: N, ...}
    average_score: float
    top_leads: list[LeadScore]


class CampaignROI(BaseModel):
    """ROI analysis for a campaign."""
    campaign_id: UUID | None = None
    campaign_name: str = ""
    total_cost: float = 0
    total_revenue: float = 0
    roi_percent: float = 0
    cost_per_lead: float = 0
    cost_per_conversion: float = 0
    leads_generated: int = 0
    conversions: int = 0
    conversion_rate: float = 0
    revenue_per_lead: float = 0
    break_even_conversions: int = 0


class ABTestResult(BaseModel):
    """A/B test statistical significance result."""
    test_name: str = ""
    variant_a_name: str = "A"
    variant_b_name: str = "B"
    variant_a_conversions: int = 0
    variant_a_total: int = 0
    variant_b_conversions: int = 0
    variant_b_total: int = 0
    variant_a_rate: float = 0
    variant_b_rate: float = 0
    absolute_difference: float = 0
    relative_improvement: float = 0
    z_score: float = 0
    p_value: float = 0
    confidence_level: float = 0
    is_significant: bool = False
    winner: str | None = None
    required_sample_size: int = 0
    recommendation: str = ""


class RetentionCohort(BaseModel):
    """Single cohort in retention analysis."""
    cohort_label: str
    cohort_start: datetime
    cohort_size: int
    retention_by_period: dict[int, float]  # {period_num: retention_rate}


class RetentionAnalysis(BaseModel):
    """Full retention curve analysis."""
    analysis_date: datetime
    period_type: str  # weekly, monthly
    cohorts: list[RetentionCohort]
    average_retention_by_period: dict[int, float]
    overall_churn_rate: float = 0
    average_lifetime_value: float = 0


# ── Service ──────────────────────────────────────────


class PredictiveAnalyticsService:
    """
    Statistical predictive analytics — no sklearn required.
    Uses weighted scoring, z-tests, and survival-style analysis.
    """

    # ── Churn Prediction ─────────────────────────────

    def predict_churn(
        self,
        contacts: list[dict[str, Any]],
        *,
        recency_weight: float = 0.35,
        frequency_weight: float = 0.25,
        monetary_weight: float = 0.15,
        engagement_weight: float = 0.25,
        high_threshold: float = 0.7,
        critical_threshold: float = 0.85,
    ) -> ChurnSummary:
        """
        Predict churn probability for each contact using weighted scoring.

        Each contact dict should have:
          - id, phone_number, name (optional)
          - days_since_last_activity (int or None)
          - total_calls, answered_calls
          - total_sms_received
          - purchase_count, total_spend
          - current_stage, rfm_segment
          - last_activity_date (datetime or None)
        """
        predictions: list[ChurnPrediction] = []
        risk_dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        revenue_at_risk = 0

        for c in contacts:
            prob, factors = self._calculate_churn_probability(
                c, recency_weight, frequency_weight, monetary_weight, engagement_weight,
            )
            risk = (
                "critical" if prob >= critical_threshold
                else "high" if prob >= high_threshold
                else "medium" if prob >= 0.4
                else "low"
            )

            action = self._churn_action(risk, c.get("rfm_segment"))

            pred = ChurnPrediction(
                contact_id=c["id"],
                phone_number=c.get("phone_number", ""),
                name=c.get("name"),
                segment=c.get("rfm_segment"),
                churn_probability=round(prob, 3),
                risk_level=risk,
                risk_factors=factors,
                recommended_action=action,
                days_since_last_activity=c.get("days_since_last_activity"),
                last_activity_date=c.get("last_activity_date"),
            )
            predictions.append(pred)
            risk_dist[risk] += 1

            if risk in ("high", "critical"):
                revenue_at_risk += c.get("total_spend", 0)

        at_risk = risk_dist["high"] + risk_dist["critical"]
        total = len(predictions) or 1

        # Top-risk contacts
        predictions.sort(key=lambda p: p.churn_probability, reverse=True)
        top_risk = predictions[:20]

        recs = self._churn_recommendations(risk_dist, total)

        return ChurnSummary(
            analysis_date=datetime.utcnow(),
            total_contacts=len(predictions),
            at_risk_count=at_risk,
            at_risk_percentage=round(at_risk / total * 100, 1),
            risk_distribution=risk_dist,
            top_risk_contacts=top_risk,
            estimated_revenue_at_risk=revenue_at_risk,
            recommendations=recs,
        )

    def _calculate_churn_probability(
        self, c: dict, rw: float, fw: float, mw: float, ew: float,
    ) -> tuple[float, list[str]]:
        factors: list[str] = []
        scores: list[tuple[float, float]] = []  # (score 0-1, weight)

        # Recency score (higher = more likely to churn)
        days = c.get("days_since_last_activity")
        if days is None or days > 180:
            r_score = 1.0
            factors.append("بدون فعالیت اخیر")
        elif days > 90:
            r_score = 0.85
            factors.append("بیش از ۹۰ روز بدون فعالیت")
        elif days > 60:
            r_score = 0.7
            factors.append("بیش از ۶۰ روز بدون فعالیت")
        elif days > 30:
            r_score = 0.5
            factors.append("بیش از ۳۰ روز بدون فعالیت")
        elif days > 14:
            r_score = 0.3
        else:
            r_score = 0.1
        scores.append((r_score, rw))

        # Frequency score (low frequency = higher churn)
        purchases = c.get("purchase_count", 0)
        if purchases == 0:
            f_score = 0.8
            factors.append("بدون خرید")
        elif purchases == 1:
            f_score = 0.6
            factors.append("فقط یک خرید")
        elif purchases <= 3:
            f_score = 0.3
        else:
            f_score = 0.1
        scores.append((f_score, fw))

        # Monetary score (low spend = higher churn)
        spend = c.get("total_spend", 0)
        if spend == 0:
            m_score = 0.7
        elif spend < 50_000_000:
            m_score = 0.5
        elif spend < 500_000_000:
            m_score = 0.3
        else:
            m_score = 0.1
        scores.append((m_score, mw))

        # Engagement score (low engagement = higher churn)
        calls = c.get("total_calls", 0)
        answered = c.get("answered_calls", 0)
        sms = c.get("total_sms_received", 0)

        engagement = calls + answered * 2 + sms
        if engagement == 0:
            e_score = 0.9
            factors.append("بدون تعامل")
        elif engagement < 3:
            e_score = 0.6
        elif engagement < 10:
            e_score = 0.3
        else:
            e_score = 0.1
        scores.append((e_score, ew))

        # Stage penalty
        stage = c.get("current_stage", "lead_acquired")
        if stage == "lead_acquired":
            stage_penalty = 0.15
            factors.append("هنوز در مرحله سرنخ")
        elif stage in ("sms_sent", "sms_delivered"):
            stage_penalty = 0.05
        else:
            stage_penalty = 0.0

        # Weighted sum
        prob = sum(s * w for s, w in scores) + stage_penalty
        prob = min(max(prob, 0.0), 1.0)  # clamp

        return round(prob, 4), factors

    def _churn_action(self, risk: str, segment: str | None) -> str:
        actions = {
            "critical": "تماس فوری توسط تیم فروش — پیشنهاد ویژه",
            "high": "ارسال پیامک بازگشت با تخفیف ویژه",
            "medium": "ارسال پیامک یادآوری و معرفی محصول جدید",
            "low": "حفظ ارتباط منظم — پیامک خبرنامه",
        }
        return actions.get(risk, "")

    def _churn_recommendations(self, dist: dict, total: int) -> list[str]:
        recs = []
        crit_pct = dist["critical"] / total * 100 if total else 0
        high_pct = dist["high"] / total * 100 if total else 0

        if crit_pct > 10:
            recs.append(f"⚠️ {crit_pct:.0f}% مشتریان در خطر بحرانی — کمپین بازگشت فوری پیشنهاد می‌شود")
        if high_pct > 20:
            recs.append(f"📞 {high_pct:.0f}% مشتریان در خطر بالا — افزایش تماس‌های پیگیری")
        if dist["low"] / total * 100 > 60 if total else False:
            recs.append("✅ اکثر مشتریان فعال هستند — تمرکز بر حفظ و ارتقا")

        recs.append("💡 ارسال پیامک هدفمند بر اساس سطح ریسک هر مشتری")
        recs.append("📊 بررسی هفتگی تغییرات ریسک ریزش مشتریان")
        return recs

    # ── Lead Scoring ─────────────────────────────────

    def score_leads(
        self,
        leads: list[dict[str, Any]],
    ) -> LeadScoringResult:
        """
        Score leads based on engagement, demographics, and behavior.

        Each lead dict should have:
          - id, phone_number, name, category_name
          - total_calls, answered_calls, total_sms_received
          - current_stage, days_since_created
          - purchase_count, total_spend
        """
        scored: list[LeadScore] = []

        for lead in leads:
            score, factors = self._calculate_lead_score(lead)
            grade = self._score_to_grade(score)
            action = self._lead_action(grade)

            scored.append(LeadScore(
                contact_id=lead["id"],
                phone_number=lead.get("phone_number", ""),
                name=lead.get("name"),
                category=lead.get("category_name"),
                score=round(score, 1),
                grade=grade,
                scoring_factors=factors,
                recommended_action=action,
            ))

        scored.sort(key=lambda s: s.score, reverse=True)

        grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for s in scored:
            grades[s.grade] = grades.get(s.grade, 0) + 1

        avg = sum(s.score for s in scored) / len(scored) if scored else 0

        return LeadScoringResult(
            analysis_date=datetime.utcnow(),
            total_scored=len(scored),
            grade_distribution=grades,
            average_score=round(avg, 1),
            top_leads=scored[:20],
        )

    def _calculate_lead_score(self, lead: dict) -> tuple[float, dict[str, float]]:
        factors: dict[str, float] = {}

        # Stage progression (0-30 points)
        stage_scores = {
            "lead_acquired": 5, "sms_sent": 10, "sms_delivered": 15,
            "call_attempted": 20, "call_answered": 25,
            "invoice_issued": 28, "payment_received": 30,
        }
        stage = lead.get("current_stage", "lead_acquired")
        stage_pts = stage_scores.get(stage, 5)
        factors["stage_progression"] = stage_pts

        # Engagement (0-25 points)
        calls = lead.get("total_calls", 0)
        answered = lead.get("answered_calls", 0)
        sms = lead.get("total_sms_received", 0)
        eng_pts = min(calls * 2 + answered * 5 + sms * 1, 25)
        factors["engagement"] = eng_pts

        # Recency (0-20 points)
        days = lead.get("days_since_created", 999)
        if days <= 7:
            rec_pts = 20
        elif days <= 14:
            rec_pts = 15
        elif days <= 30:
            rec_pts = 10
        elif days <= 60:
            rec_pts = 5
        else:
            rec_pts = 2
        factors["recency"] = rec_pts

        # Purchase history (0-15 points)
        purchases = lead.get("purchase_count", 0)
        spend = lead.get("total_spend", 0)
        if purchases > 3:
            pur_pts = 15
        elif purchases > 1:
            pur_pts = 10
        elif purchases == 1:
            pur_pts = 7
        elif spend > 0:
            pur_pts = 5
        else:
            pur_pts = 0
        factors["purchase_history"] = pur_pts

        # Call quality (0-10 points)
        if answered > 0:
            call_q = min(answered * 3, 10)
        elif calls > 0:
            call_q = 2
        else:
            call_q = 0
        factors["call_quality"] = call_q

        total = sum(factors.values())
        return min(total, 100), factors

    def _score_to_grade(self, score: float) -> str:
        if score >= 80:
            return "A"
        if score >= 60:
            return "B"
        if score >= 40:
            return "C"
        if score >= 20:
            return "D"
        return "F"

    def _lead_action(self, grade: str) -> str:
        return {
            "A": "اولویت بالا — تماس فوری و ارائه پیشنهاد ویژه",
            "B": "پیگیری سریع — ارسال پیامک شخصی‌سازی شده",
            "C": "ارسال محتوای آموزشی و معرفی محصول",
            "D": "ارسال پیامک عمومی و پیگیری دوره‌ای",
            "F": "کمپین بازاریابی مجدد — بررسی کیفیت سرنخ",
        }.get(grade, "")

    # ── Campaign ROI ─────────────────────────────────

    def calculate_campaign_roi(
        self,
        campaign_name: str,
        campaign_id: UUID | None,
        total_cost: float,
        leads_generated: int,
        conversions: int,
        total_revenue: float,
        average_product_margin: float = 0.3,  # 30% default margin
    ) -> CampaignROI:
        """Calculate ROI metrics for a campaign."""
        roi_pct = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        cpl = total_cost / leads_generated if leads_generated > 0 else 0
        cpc = total_cost / conversions if conversions > 0 else 0
        conv_rate = conversions / leads_generated if leads_generated > 0 else 0
        rpl = total_revenue / leads_generated if leads_generated > 0 else 0

        # Break-even: how many conversions to cover cost
        avg_revenue_per_conv = total_revenue / conversions if conversions > 0 else 0
        margin_per_conv = avg_revenue_per_conv * average_product_margin
        break_even = math.ceil(total_cost / margin_per_conv) if margin_per_conv > 0 else 0

        return CampaignROI(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            total_cost=total_cost,
            total_revenue=total_revenue,
            roi_percent=round(roi_pct, 1),
            cost_per_lead=round(cpl, 0),
            cost_per_conversion=round(cpc, 0),
            leads_generated=leads_generated,
            conversions=conversions,
            conversion_rate=round(conv_rate, 4),
            revenue_per_lead=round(rpl, 0),
            break_even_conversions=break_even,
        )

    # ── A/B Test Significance ────────────────────────

    def ab_test_significance(
        self,
        test_name: str,
        variant_a_conversions: int,
        variant_a_total: int,
        variant_b_conversions: int,
        variant_b_total: int,
        confidence_threshold: float = 0.95,
        variant_a_name: str = "کنترل (A)",
        variant_b_name: str = "آزمایشی (B)",
    ) -> ABTestResult:
        """
        Calculate statistical significance of A/B test using two-proportion z-test.
        """
        n_a = variant_a_total or 1
        n_b = variant_b_total or 1
        p_a = variant_a_conversions / n_a
        p_b = variant_b_conversions / n_b

        # Pooled proportion
        p_pool = (variant_a_conversions + variant_b_conversions) / (n_a + n_b)

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b)) if p_pool > 0 and p_pool < 1 else 0.0001

        # Z-score
        z = (p_b - p_a) / se if se > 0 else 0

        # P-value (two-tailed) using approximation of normal CDF
        p_value = 2 * (1 - self._normal_cdf(abs(z)))
        confidence = 1 - p_value

        is_sig = confidence >= confidence_threshold

        # Relative improvement
        rel_imp = ((p_b - p_a) / p_a * 100) if p_a > 0 else 0

        # Winner
        winner = None
        if is_sig:
            winner = variant_b_name if p_b > p_a else variant_a_name

        # Required sample size for 80% power, 5% significance
        req_n = self._required_sample_size(p_a, abs(p_b - p_a) or 0.01)

        rec = self._ab_recommendation(is_sig, p_a, p_b, confidence, n_a + n_b, req_n * 2)

        return ABTestResult(
            test_name=test_name,
            variant_a_name=variant_a_name,
            variant_b_name=variant_b_name,
            variant_a_conversions=variant_a_conversions,
            variant_a_total=variant_a_total,
            variant_b_conversions=variant_b_conversions,
            variant_b_total=variant_b_total,
            variant_a_rate=round(p_a, 4),
            variant_b_rate=round(p_b, 4),
            absolute_difference=round(p_b - p_a, 4),
            relative_improvement=round(rel_imp, 1),
            z_score=round(z, 3),
            p_value=round(p_value, 4),
            confidence_level=round(confidence, 4),
            is_significant=is_sig,
            winner=winner,
            required_sample_size=req_n * 2,
            recommendation=rec,
        )

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF using Abramowitz & Stegun formula."""
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        return 0.5 * (1.0 + sign * y)

    def _required_sample_size(
        self, baseline_rate: float, mde: float, alpha: float = 0.05, power: float = 0.8,
    ) -> int:
        """Estimate required sample size per group for a two-proportion z-test."""
        if mde <= 0 or baseline_rate <= 0 or baseline_rate >= 1:
            return 1000  # fallback
        z_alpha = 1.96  # ~0.05 two-tailed
        z_beta = 0.84   # ~80% power
        p1 = baseline_rate
        p2 = baseline_rate + mde
        p_avg = (p1 + p2) / 2
        n = ((z_alpha * math.sqrt(2 * p_avg * (1 - p_avg))
              + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (mde ** 2)
        return max(int(math.ceil(n)), 30)

    def _ab_recommendation(
        self, is_sig: bool, p_a: float, p_b: float, conf: float, current_n: int, req_n: int,
    ) -> str:
        if is_sig and p_b > p_a:
            return f"✅ نسخه B با اطمینان {conf*100:.1f}% بهتر است — پیشنهاد: استفاده از نسخه B"
        if is_sig and p_a > p_b:
            return f"✅ نسخه A با اطمینان {conf*100:.1f}% بهتر است — پیشنهاد: حفظ نسخه A"
        if current_n < req_n:
            return f"⏳ داده کافی نیست — حداقل {req_n:,} نمونه لازم است (فعلی: {current_n:,})"
        return "🔄 تفاوت معنادار نیست — ادامه آزمایش یا بررسی متغیرهای دیگر"

    # ── Retention Curves ─────────────────────────────

    def calculate_retention(
        self,
        cohorts_data: list[dict[str, Any]],
        period_type: str = "weekly",
        num_periods: int = 8,
    ) -> RetentionAnalysis:
        """
        Calculate retention curves from cohort data.

        Each cohort dict:
          - cohort_label: str
          - cohort_start: datetime
          - contacts: list of {created_at, last_activity_date, is_active}
        """
        cohorts: list[RetentionCohort] = []

        for cd in cohorts_data:
            contacts = cd.get("contacts", [])
            size = len(contacts)
            if size == 0:
                continue

            retention: dict[int, float] = {}
            cohort_start = cd["cohort_start"]
            period_days = 7 if period_type == "weekly" else 30

            for p in range(num_periods + 1):
                period_end = cohort_start + timedelta(days=period_days * p)
                active = sum(
                    1 for c in contacts
                    if c.get("last_activity_date") and c["last_activity_date"] >= period_end
                )
                retention[p] = round(active / size, 4)

            cohorts.append(RetentionCohort(
                cohort_label=cd.get("cohort_label", ""),
                cohort_start=cohort_start,
                cohort_size=size,
                retention_by_period=retention,
            ))

        # Average retention
        avg_retention: dict[int, float] = {}
        if cohorts:
            for p in range(num_periods + 1):
                rates = [c.retention_by_period.get(p, 0) for c in cohorts if p in c.retention_by_period]
                avg_retention[p] = round(sum(rates) / len(rates), 4) if rates else 0

        # Overall churn = 1 - last-period average retention
        overall_churn = 1 - avg_retention.get(num_periods, 0) if avg_retention else 0

        return RetentionAnalysis(
            analysis_date=datetime.utcnow(),
            period_type=period_type,
            cohorts=cohorts,
            average_retention_by_period=avg_retention,
            overall_churn_rate=round(overall_churn, 4),
        )

