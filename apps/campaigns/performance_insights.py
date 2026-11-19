"""Portfolio campaign performance insights — explainable winners per lens."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from apps.campaigns.metrics import CampaignListRow


MIN_IMPRESSIONS_ELIGIBLE = 50
MIN_IMPRESSIONS_CTR = 200
MIN_CLICKS_CONVERSION = 10
MIN_ACTIONS_EFFICIENCY = 3


@dataclass(frozen=True)
class LensSpec:
    key: str
    label: str
    short_label: str


LENSES: tuple[LensSpec, ...] = (
    LensSpec("reach", "بیشترین نمایش", "نمایش"),
    LensSpec("engagement", "بیشترین نرخ کلیک", "کلیک"),
    LensSpec("conversion", "بیشترین نرخ اقدام", "اقدام"),
    LensSpec("efficiency", "کمترین هزینه هر اقدام", "هر اقدام"),
)

CHAMPION_LENS_LABEL = "کمپین با امتیاز بالاتر"
CHAMPION_BADGE_TITLE = "کمپین با امتیاز بالاتر"


@dataclass(frozen=True)
class CampaignInsightPick:
    lens_key: str
    lens_label: str
    campaign_id: int
    campaign_name: str
    status: str
    placement_label: str
    impressions: int
    clicks: int
    actions: int
    ctr: float
    conversion_rate: float
    spent_ton: Decimal | None
    cost_per_action: Decimal | None
    score: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioPerformanceInsights:
    champion: CampaignInsightPick | None
    lens_winners: tuple[CampaignInsightPick, ...]
    eligible_count: int
    portfolio_avg_ctr: float
    portfolio_avg_conversion: float | None
    note: str | None = None


def _conversion_rate(row: CampaignListRow) -> float:
    if not row.metrics.has_actions or not row.metrics.clicks:
        return 0.0
    return round(row.metrics.actions * 100.0 / row.metrics.clicks, 2)


def _cost_per_action(row: CampaignListRow) -> Decimal | None:
    if (
        row.metrics.has_actions and row.metrics.actions
        and row.metrics.spent_ton is not None
        and row.metrics.spent_ton > 0
    ):
        return (row.metrics.spent_ton / Decimal(row.metrics.actions)).quantize(Decimal("0.0001"))
    return None


def _eligible_rows(rows: list[CampaignListRow]) -> list[CampaignListRow]:
    return [
        r
        for r in rows
        if r.metrics.has_ctr and not r.metrics.stats_stale and r.metrics.impressions >= MIN_IMPRESSIONS_ELIGIBLE
    ]


def _normalize(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return 0.5
    return (value - lo) / (hi - lo)


def _compare_to_average(value: float, baseline: float, *, higher_is_better: bool = True) -> str | None:
    """یک جملهٔ ساده دربارهٔ مقایسه با میانگین بقیهٔ کمپین‌ها."""
    if baseline <= 0 or value <= 0:
        return None
    ratio = value / baseline
    if not higher_is_better:
        ratio = baseline / value
    if ratio < 1.05:
        return None
    mult = round(ratio, 1)
    if mult == 1.0:
        return None
    if higher_is_better:
        if mult >= 2:
            return f"حدود {mult} برابر بهتر از میانگین بقیهٔ کمپین‌ها"
        return "بهتر از میانگین بقیهٔ کمپین‌ها"
    if mult >= 2:
        return f"حدود {mult} برابر ارزان‌تر از میانگین بقیهٔ کمپین‌ها"
    return "ارزان‌تر از میانگین بقیهٔ کمپین‌ها"


def _pick_to_insight(
    row: CampaignListRow,
    *,
    lens_key: str,
    lens_label: str,
    reasons: list[str],
    score: float | None = None,
) -> CampaignInsightPick:
    return CampaignInsightPick(
        lens_key=lens_key,
        lens_label=lens_label,
        campaign_id=row.campaign.id,
        campaign_name=row.campaign.name or "بدون نام",
        status=row.campaign.status,
        placement_label=row.placement_label,
        impressions=row.metrics.impressions,
        clicks=row.metrics.clicks,
        actions=row.metrics.actions,
        ctr=row.ctr,
        conversion_rate=_conversion_rate(row),
        spent_ton=row.metrics.spent_ton,
        cost_per_action=_cost_per_action(row),
        score=score,
        reasons=tuple(reasons),
    )


def _reasons_for_row(
    row: CampaignListRow,
    *,
    lens_key: str,
    avg_ctr: float,
    avg_conv: float | None,
    avg_cpa: float | None,
) -> list[str]:
    reasons: list[str] = []
    conv = _conversion_rate(row)
    cpa = _cost_per_action(row)

    if lens_key == "reach":
        reasons.append(
            f"تبلیغ {row.metrics.impressions} بار دیده شده — بیشتر از بقیهٔ کمپین‌ها"
        )
    elif lens_key == "engagement":
        extra = _compare_to_average(row.ctr, avg_ctr)
        if extra:
            reasons.append(f"کلیک روی تبلیغ بیشتر بوده ({row.ctr}٪) — {extra}")
        else:
            reasons.append(f"از هر ۱۰۰ نمایش، حدود {row.ctr}٪ روی تبلیغ کلیک شده")
    elif lens_key == "conversion" and row.metrics.clicks >= MIN_CLICKS_CONVERSION:
        extra = _compare_to_average(conv, avg_conv or 0) if avg_conv else None
        if extra:
            reasons.append(
                f"از {row.metrics.clicks} کلیک، {row.metrics.actions} اقدام ({conv}٪) — {extra}"
            )
        else:
            reasons.append(
                f"از {row.metrics.clicks} کلیک، {row.metrics.actions} اقدام ثبت شده ({conv}٪)"
            )
    elif lens_key == "efficiency" and cpa is not None and row.metrics.actions:
        extra = _compare_to_average(float(cpa), avg_cpa or 0, higher_is_better=False) if avg_cpa else None
        if extra:
            reasons.append(f"هر اقدام کم‌هزینه‌تر بوده — {extra}")
        else:
            reasons.append("برای هر اقدام، کمتر از بقیهٔ کمپین‌ها هزینه شده")
    elif lens_key == "overall":
        extra_ctr = _compare_to_average(row.ctr, avg_ctr)
        if extra_ctr:
            reasons.append(f"کلیک روی تبلیغ قوی بوده ({row.ctr}٪) — {extra_ctr}")
        elif row.ctr:
            reasons.append(f"نرخ کلیک {row.ctr}٪")
        if row.metrics.clicks >= MIN_CLICKS_CONVERSION:
            extra_conv = _compare_to_average(conv, avg_conv or 0) if avg_conv else None
            if extra_conv:
                reasons.append(
                    f"بعد از کلیک هم خوب جواب داده ({conv}٪ اقدام) — {extra_conv}"
                )
        if row.metrics.impressions >= 1000 and len(reasons) < 2:
            reasons.append(f"تعداد نمایش بالا ({row.metrics.impressions} بار)")
    if row.placement_label and row.placement_label != "—" and len(reasons) < 3:
        reasons.append(f"جایگاه تبلیغ: {row.placement_label}")
    if not reasons:
        reasons.append("نسبت به بقیهٔ کمپین‌های شما، نتیجهٔ بهتری گرفته")
    return reasons[:3]


def build_portfolio_performance_insights(rows: list[CampaignListRow]) -> PortfolioPerformanceInsights:
    eligible = _eligible_rows(rows)
    if not eligible:
        return PortfolioPerformanceInsights(
            champion=None,
            lens_winners=(),
            eligible_count=0,
            portfolio_avg_ctr=0.0,
            portfolio_avg_conversion=None,
            note="وقتی آمار تبلیغ از تلگرام بیاید، اینجا می‌بینید کدام کمپین بهتر جواب داده.",
        )
    if len(eligible) == 1:
        only = eligible[0]
        reasons = _reasons_for_row(
            only,
            lens_key="overall",
            avg_ctr=only.ctr,
            avg_conv=_conversion_rate(only),
            avg_cpa=float(_cost_per_action(only) or 0) or None,
        )
        pick = _pick_to_insight(
            only,
            lens_key="overall",
            lens_label="فعلاً فقط همین کمپین آمار کافی دارد",
            reasons=reasons,
            score=1.0,
        )
        return PortfolioPerformanceInsights(
            champion=pick,
            lens_winners=(pick,),
            eligible_count=1,
            portfolio_avg_ctr=only.ctr,
            portfolio_avg_conversion=_conversion_rate(only) if only.metrics.clicks else None,
            note="با دو کمپین یا بیشتر، مقایسه دقیق‌تر و منصفانه‌تر می‌شود.",
        )

    avg_ctr = round(
        sum(r.ctr for r in eligible) / len(eligible),
        2,
    )
    # Conversion comparisons only make sense for the same explicitly known event.
    action_types = {r.metrics.action_type for r in eligible}
    same_action = len(action_types) == 1 and bool(next(iter(action_types))) and all(r.metrics.has_actions for r in eligible)
    conv_rows = [r for r in eligible if same_action and r.metrics.clicks >= MIN_CLICKS_CONVERSION]
    avg_conv = (
        round(sum(_conversion_rate(r) for r in conv_rows) / len(conv_rows), 2)
        if conv_rows
        else None
    )
    cpa_values = [
        float(c)
        for r in eligible
        if same_action and (c := _cost_per_action(r)) is not None and r.metrics.actions >= MIN_ACTIONS_EFFICIENCY
    ]
    avg_cpa = round(sum(cpa_values) / len(cpa_values), 4) if cpa_values else None

    impressions_list = [float(r.metrics.impressions) for r in eligible]
    ctr_list = [r.ctr for r in eligible]
    conv_list = [_conversion_rate(r) for r in eligible]
    cpa_list = [float(_cost_per_action(r) or 0) for r in eligible]

    def overall_score(row: CampaignListRow) -> float:
        parts = [
            0.28 * _normalize(impressions_list, float(row.metrics.impressions)),
            0.32 * _normalize(ctr_list, row.ctr),
            0.25 * _normalize(conv_list, _conversion_rate(row)) if same_action else 0.125,
        ]
        cpa = _cost_per_action(row)
        if same_action and cpa is not None and float(cpa) > 0 and max(cpa_list) > 0:
            parts.append(0.15 * (1.0 - _normalize(cpa_list, float(cpa))))
        else:
            parts.append(0.15 * 0.35)
        return round(sum(parts), 4)

    scored = sorted(
        ((overall_score(r), r) for r in eligible),
        key=lambda t: t[0],
        reverse=True,
    )
    champion_row = scored[0][1]
    champion = _pick_to_insight(
        champion_row,
        lens_key="overall",
        lens_label=CHAMPION_LENS_LABEL,
        reasons=_reasons_for_row(
            champion_row,
            lens_key="overall",
            avg_ctr=avg_ctr,
            avg_conv=avg_conv,
            avg_cpa=avg_cpa,
        ),
        score=scored[0][0],
    )

    lens_winners: list[CampaignInsightPick] = []

    reach_row = max(eligible, key=lambda r: r.metrics.impressions)
    lens_winners.append(
        _pick_to_insight(
            reach_row,
            lens_key="reach",
            lens_label=LENSES[0].label,
            reasons=_reasons_for_row(
                reach_row, lens_key="reach", avg_ctr=avg_ctr, avg_conv=avg_conv, avg_cpa=avg_cpa
            ),
        )
    )

    ctr_pool = [r for r in eligible if r.metrics.impressions >= MIN_IMPRESSIONS_CTR]
    if ctr_pool:
        eng_row = max(ctr_pool, key=lambda r: r.ctr)
        lens_winners.append(
            _pick_to_insight(
                eng_row,
                lens_key="engagement",
                lens_label=LENSES[1].label,
                reasons=_reasons_for_row(
                    eng_row,
                    lens_key="engagement",
                    avg_ctr=avg_ctr,
                    avg_conv=avg_conv,
                    avg_cpa=avg_cpa,
                ),
            )
        )

    conv_pool = conv_rows
    if conv_pool:
        conv_row = max(conv_pool, key=_conversion_rate)
        lens_winners.append(
            _pick_to_insight(
                conv_row,
                lens_key="conversion",
                lens_label=LENSES[2].label,
                reasons=_reasons_for_row(
                    conv_row,
                    lens_key="conversion",
                    avg_ctr=avg_ctr,
                    avg_conv=avg_conv,
                    avg_cpa=avg_cpa,
                ),
            )
        )

    eff_pool = [
        r
        for r in eligible
        if same_action and r.metrics.actions >= MIN_ACTIONS_EFFICIENCY and _cost_per_action(r) is not None
    ]
    if eff_pool:
        eff_row = min(eff_pool, key=lambda r: float(_cost_per_action(r) or 0))
        lens_winners.append(
            _pick_to_insight(
                eff_row,
                lens_key="efficiency",
                lens_label=LENSES[3].label,
                reasons=_reasons_for_row(
                    eff_row,
                    lens_key="efficiency",
                    avg_ctr=avg_ctr,
                    avg_conv=avg_conv,
                    avg_cpa=avg_cpa,
                ),
            )
        )

    return PortfolioPerformanceInsights(
        champion=champion,
        lens_winners=tuple(lens_winners),
        eligible_count=len(eligible),
        portfolio_avg_ctr=avg_ctr,
        portfolio_avg_conversion=avg_conv,
        note=None,
    )


def insight_badges_for_campaign(
    insights: PortfolioPerformanceInsights,
    campaign_id: int,
) -> list[dict[str, Any]]:
    """Labels to show on campaign detail when this ad won a lens."""
    badges: list[dict[str, Any]] = []
    if insights.champion and insights.champion.campaign_id == campaign_id:
        badges.append(
            {
                "kind": "champion",
                "title": CHAMPION_BADGE_TITLE,
                "reasons": insights.champion.reasons,
            }
        )
    for pick in insights.lens_winners:
        if pick.campaign_id == campaign_id and pick.lens_key != "overall":
            if any(b.get("title") == pick.lens_label for b in badges):
                continue
            badges.append(
                {
                    "kind": pick.lens_key,
                    "title": pick.lens_label,
                    "reasons": pick.reasons,
                }
            )
    return badges
