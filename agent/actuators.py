"""
agent/actuators.py
Builds presentation data for the user interface:
- Alerts list with colored badges and rule IDs
- Up to 3 prioritized, specific recommendations with INR amounts
- Chart.js chart payloads (bar, line, doughnut)
- Formatting helpers for the PEAS Actuator stage
"""

from typing import Any, Dict, List, Optional

SEVERITY_BADGE_CLASS = {
    "CRITICAL": "danger",
    "WARNING": "warning",
    "INFO": "info",
    "POSITIVE": "success",
}

CHART_COLORS = [
    "#4f46e5",  # Indigo
    "#06b6d4",  # Cyan
    "#10b981",  # Emerald
    "#f59e0b",  # Amber
    "#ef4444",  # Rose
    "#8b5cf6",  # Violet
    "#ec4899",  # Pink
    "#64748b",  # Slate
    "#14b8a6",  # Teal
    "#f97316",  # Orange
]


def build_alerts_view(alerts: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Formats alerts with UI badge classes and rule identifiers.
    """
    view_alerts: List[Dict[str, Any]] = []
    for a in alerts:
        sev = a.get("severity", "INFO")
        view_alerts.append({
            "id": a.get("id", "R0"),
            "severity": sev,
            "badge_class": SEVERITY_BADGE_CLASS.get(sev, "secondary"),
            "category": a.get("category", "General"),
            "message": a.get("message", ""),
        })
    return view_alerts


def build_recommendations(
    salary: float,
    salary_change_inr: float,
    salary_change_pct: float,
    category_metrics: List[Dict[str, Any]],
    summary_metrics: Dict[str, Any],
    alerts: List[Dict[str, str]],
    currency: str = "₹"
) -> List[Dict[str, Any]]:
    """
    Generates up to 3 specific recommendations based on user's actual numbers,
    each with an estimated monthly saving or allocation in INR.
    """
    recs: List[Dict[str, Any]] = []

    # 1. Critical Salary Drop (>10% drop - S4)
    if any(a["id"] == "S4" for a in alerts):
        flexible_spent = sum(
            c["spent"] for c in category_metrics
            if c["category"] in ["Entertainment", "Shopping", "Miscellaneous"]
        )
        target_cut = round(max(500.0, flexible_spent * 0.40), 2)
        recs.append({
            "title": "Enact Lean Budget on Non-Essentials",
            "body": (
                f"Your income dropped by {abs(salary_change_pct):.1f}%. "
                f"Cap flexible categories (Shopping, Entertainment, Misc) to save an estimated "
                f"{currency}{target_cut:,.2f} this month and protect essential living costs."
            ),
            "amount": target_cut,
            "action_type": "Save",
        })

    # 2. Moderate Salary Drop (1-10% drop - S3)
    elif any(a["id"] == "S3" for a in alerts):
        over_cats = [c for c in category_metrics if c["used_pct"] >= 100.0]
        if over_cats:
            top_over = max(over_cats, key=lambda c: c["spent"] - c["budget"])
            excess = round(top_over["spent"] - top_over["budget"], 2)
            recs.append({
                "title": f"Rebalance {top_over['category']} Spending",
                "body": (
                    f"Under your adjusted income, {top_over['category']} is over budget by "
                    f"{currency}{excess:,.2f}. Pause new purchases here for the rest of the month."
                ),
                "amount": excess,
                "action_type": "Save",
            })

    # 3. Salary Hike (S2)
    if any(a["id"] == "S2" for a in alerts) and salary_change_inr > 0:
        recommended_save = round(salary_change_inr * 0.50, 2)
        recs.append({
            "title": "Lock in 50% of Salary Increment",
            "body": (
                f"Your salary increased by {currency}{salary_change_inr:,.2f}. "
                f"Automate a direct transfer of {currency}{recommended_save:,.2f} into savings "
                f"or emergency reserves before adjusting lifestyle expenses."
            ),
            "amount": recommended_save,
            "action_type": "Allocate",
        })

    # 4. Over-Budget Category Check (R2)
    over_budget_cats = [c for c in category_metrics if c["spent"] > c["budget"]]
    if over_budget_cats and len(recs) < 3:
        worst_cat = max(over_budget_cats, key=lambda c: c["spent"] - c["budget"])
        diff = round(worst_cat["spent"] - worst_cat["budget"], 2)
        # Avoid duplicate recommendation
        if not any(worst_cat["category"] in r["title"] for r in recs):
            recs.append({
                "title": f"Halt Overspend in {worst_cat['category']}",
                "body": (
                    f"{worst_cat['category']} has exceeded its limit by {currency}{diff:,.2f}. "
                    f"Delay non-critical purchases until next month's fresh budget allocation."
                ),
                "amount": diff,
                "action_type": "Save",
            })

    # 5. High Discretionary Spending (R6)
    if any(a["id"] == "R6" for a in alerts) and len(recs) < 3:
        disc_total = sum(
            c["spent"] for c in category_metrics
            if c["category"] in ["Entertainment", "Shopping"]
        )
        potential_saving = round(disc_total * 0.20, 2)
        recs.append({
            "title": "Trim Discretionary Outflows",
            "body": (
                f"Shopping and entertainment currently absorb {currency}{disc_total:,.2f}. "
                f"Implementing a 20% reduction target will preserve {currency}{potential_saving:,.2f}."
            ),
            "amount": potential_saving,
            "action_type": "Save",
        })

    # 6. Savings Goal at Risk (R3)
    if any(a["id"] == "R3" for a in alerts) and len(recs) < 3:
        safe_spend_ceiling = salary - summary_metrics["savings_goal_inr"]
        deficit = round(summary_metrics["total_spent"] - safe_spend_ceiling, 2)
        recs.append({
            "title": "Recover Target Savings Deficit",
            "body": (
                f"Total spend is {currency}{deficit:,.2f} above the ceiling needed for your "
                f"{summary_metrics['savings_goal_percent']}% savings target. Curtail miscellaneous expenses."
            ),
            "amount": deficit,
            "action_type": "Save",
        })

    # 7. Positive Discipline Fallback (R7 or high savings rate)
    if len(recs) < 3:
        rem = summary_metrics["remaining_balance"]
        if rem > 0:
            surplus_investment = round(rem * 0.50, 2)
            recs.append({
                "title": "Invest Month-End Surplus",
                "body": (
                    f"You have a healthy surplus of {currency}{rem:,.2f}. "
                    f"Deploy {currency}{surplus_investment:,.2f} into recurring deposits, mutual funds, or debt paydown."
                ),
                "amount": surplus_investment,
                "action_type": "Allocate",
            })
        else:
            recs.append({
                "title": "Maintain Strict Daily Expense Logging",
                "body": "Keep logging daily expenses to identify unbudgeted micro-spends early in the month.",
                "amount": 0.0,
                "action_type": "Action",
            })

    return recs[:3]


def build_chart_payloads(
    category_metrics: List[Dict[str, Any]],
    historical_months: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Builds data structures ready for Chart.js rendering:
    a) bar_chart: budget vs spent per category
    b) line_chart: salary vs spending vs savings across months
    c) doughnut_chart: spending share by category
    """
    # 1. Bar Chart: Budget vs Spent
    bar_labels = [c["category"] for c in category_metrics]
    bar_budgets = [c["budget"] for c in category_metrics]
    bar_spent = [c["spent"] for c in category_metrics]

    bar_chart = {
        "labels": bar_labels,
        "datasets": [
            {
                "label": "Budget",
                "data": bar_budgets,
                "backgroundColor": "rgba(99, 102, 241, 0.7)",
                "borderColor": "#6366f1",
                "borderWidth": 1.5,
                "borderRadius": 4,
            },
            {
                "label": "Spent",
                "data": bar_spent,
                "backgroundColor": [
                    "rgba(239, 68, 68, 0.75)" if c["used_pct"] >= 100.0
                    else "rgba(245, 158, 11, 0.75)" if c["used_pct"] >= 80.0
                    else "rgba(16, 185, 129, 0.75)"
                    for c in category_metrics
                ],
                "borderColor": [
                    "#ef4444" if c["used_pct"] >= 100.0
                    else "#f59e0b" if c["used_pct"] >= 80.0
                    else "#10b981"
                    for c in category_metrics
                ],
                "borderWidth": 1.5,
                "borderRadius": 4,
            },
        ],
    }

    # 2. Line Chart: Across Months
    sorted_history = sorted(historical_months, key=lambda m: m["month"])
    line_labels = [m["month"] for m in sorted_history]
    line_salaries = [m.get("salary", 0.0) for m in sorted_history]
    line_spending = [m.get("total_spent", 0.0) for m in sorted_history]
    line_savings = [
        round(m.get("salary", 0.0) + m.get("other_income", 0.0) - m.get("total_spent", 0.0), 2)
        for m in sorted_history
    ]

    line_chart = {
        "labels": line_labels,
        "datasets": [
            {
                "label": "Salary",
                "data": line_salaries,
                "borderColor": "#3b82f6",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "tension": 0.3,
                "fill": False,
                "borderWidth": 2.5,
            },
            {
                "label": "Spending",
                "data": line_spending,
                "borderColor": "#ef4444",
                "backgroundColor": "rgba(239, 68, 68, 0.1)",
                "tension": 0.3,
                "fill": False,
                "borderWidth": 2.5,
            },
            {
                "label": "Savings / Net",
                "data": line_savings,
                "borderColor": "#10b981",
                "backgroundColor": "rgba(16, 185, 129, 0.1)",
                "tension": 0.3,
                "fill": False,
                "borderWidth": 2.5,
            },
        ],
    }

    # 3. Doughnut Chart: Spend Share
    active_cats = [c for c in category_metrics if c["spent"] > 0]
    doughnut_chart = {
        "labels": [c["category"] for c in active_cats],
        "datasets": [
            {
                "data": [c["spent"] for c in active_cats],
                "backgroundColor": CHART_COLORS[:len(active_cats)],
                "borderWidth": 2,
                "borderColor": "#ffffff",
            }
        ],
    }

    return {
        "bar_chart": bar_chart,
        "line_chart": line_chart,
        "doughnut_chart": doughnut_chart,
    }
