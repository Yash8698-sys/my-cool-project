"""
agent/expense_calculation.py
Performs mathematical calculations on expenses, categories, pacing, and savings goals.
Part of the PEAS Reasoning / Knowledge Processing stage.
"""

import calendar
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple


def get_month_day_metrics(month_str: str) -> Tuple[int, int, bool]:
    """
    Computes (days_in_month, days_elapsed, is_month_complete) for a given YYYY-MM.
    """
    year, month_num = map(int, month_str.split("-"))
    days_in_month = calendar.monthrange(year, month_num)[1]

    now = datetime.now()
    current_year_month = f"{now.year:04d}-{now.month:02d}"

    if month_str < current_year_month:
        # Month is in the past, completely elapsed
        days_elapsed = days_in_month
        is_complete = True
    elif month_str > current_year_month:
        # Future month
        days_elapsed = 1
        is_complete = False
    else:
        # Current active month
        days_elapsed = max(1, min(now.day, days_in_month))
        is_complete = (days_elapsed >= days_in_month)

    return days_in_month, days_elapsed, is_complete


def normalize_category(category: str, known_categories: Set[str]) -> str:
    """
    Rule R8 helper:
    Categories not in the configured budget list are mapped to 'Miscellaneous'.
    """
    clean = category.strip()
    if clean in known_categories:
        return clean
    return "Miscellaneous"


def calculate_category_metrics(
    expenses: List[Dict[str, Any]],
    budgets_inr: Dict[str, float],
    days_in_month: int,
    days_elapsed: int,
    is_month_complete: bool
) -> List[Dict[str, Any]]:
    """
    Computes spent, budget, remaining, % used, pacing, and status for each category.
    """
    known_categories = set(budgets_inr.keys())
    spend_by_category: Dict[str, float] = {cat: 0.0 for cat in budgets_inr.keys()}

    for exp in expenses:
        cat = normalize_category(exp.get("category", "Miscellaneous"), known_categories)
        spend_by_category[cat] = round(spend_by_category.get(cat, 0.0) + float(exp.get("amount", 0.0)), 2)

    categories_result: List[Dict[str, Any]] = []

    for cat_name, budget in budgets_inr.items():
        spent = round(spend_by_category.get(cat_name, 0.0), 2)
        remaining = round(budget - spent, 2)
        used_pct = round((spent / budget) * 100.0, 1) if budget > 0 else (100.0 if spent > 0 else 0.0)

        # Status determination: green under 80%, yellow 80-99%, red 100%+
        if used_pct >= 100.0:
            status = "critical"
            color_class = "danger"
            status_label = "Exceeded"
        elif used_pct >= 80.0:
            status = "warning"
            color_class = "warning"
            status_label = "Approaching Limit"
        else:
            status = "healthy"
            color_class = "success"
            status_label = "On Track"

        # Pacing calculation
        if is_month_complete:
            projected_spend = spent
            on_pace_to_exceed = False
        else:
            projected_spend = round((spent / days_elapsed) * days_in_month, 2) if days_elapsed > 0 else spent
            on_pace_to_exceed = (projected_spend > budget) and (spent > 0) and (used_pct < 100.0)

        categories_result.append({
            "category": cat_name,
            "spent": spent,
            "budget": budget,
            "remaining": remaining,
            "used_pct": used_pct,
            "status": status,
            "color_class": color_class,
            "status_label": status_label,
            "projected_spend": projected_spend,
            "on_pace_to_exceed": on_pace_to_exceed,
        })

    return categories_result


def calculate_summary_metrics(
    salary: float,
    other_income: float,
    expenses: List[Dict[str, Any]],
    savings_goal_percent: float,
    currency: str = "₹"
) -> Dict[str, Any]:
    """
    Computes total expenses, remaining balance, savings rate, and savings goal status.
    """
    total_income = round(salary + other_income, 2)
    total_spent = round(sum(float(exp.get("amount", 0.0)) for exp in expenses), 2)
    remaining_balance = round(total_income - total_spent, 2)

    savings_goal_inr = round((salary * (savings_goal_percent / 100.0)), 2)
    savings_rate = round(((salary - total_spent) / salary) * 100.0, 1) if salary > 0 else 0.0

    # Savings goal status
    if remaining_balance < 0:
        savings_goal_status = "exceeded"
        savings_goal_status_label = "Deficit"
        savings_goal_color = "danger"
    elif remaining_balance < savings_goal_inr:
        savings_goal_status = "at-risk"
        savings_goal_status_label = "At Risk"
        savings_goal_color = "warning"
    else:
        savings_goal_status = "on-track"
        savings_goal_status_label = "On Track"
        savings_goal_color = "success"

    return {
        "salary": salary,
        "other_income": other_income,
        "total_income": total_income,
        "total_spent": total_spent,
        "remaining_balance": remaining_balance,
        "savings_goal_percent": savings_goal_percent,
        "savings_goal_inr": savings_goal_inr,
        "savings_rate": savings_rate,
        "savings_goal_status": savings_goal_status,
        "savings_goal_status_label": savings_goal_status_label,
        "savings_goal_color": savings_goal_color,
        "expense_count": len(expenses),
    }


def generate_calculation_explanations(
    month: str,
    salary: float,
    other_income: float,
    summary: Dict[str, Any],
    categories: List[Dict[str, Any]],
    days_in_month: int,
    days_elapsed: int,
    is_complete: bool,
    salary_change_inr: float,
    salary_change_pct: float,
    has_previous: bool,
    currency: str = "₹"
) -> List[str]:
    """
    Generates step-by-step mathematical explanations for the "Show calculations" collapsible section.
    """
    steps = [
        f"1. Total Income: Base Salary ({currency}{salary:,.2f}) + Other Income ({currency}{other_income:,.2f}) = {currency}{summary['total_income']:,.2f}.",
        f"2. Total Expenses: Sum of {summary['expense_count']} expense items = {currency}{summary['total_spent']:,.2f}.",
        f"3. Remaining Balance: Total Income ({currency}{summary['total_income']:,.2f}) − Total Expenses ({currency}{summary['total_spent']:,.2f}) = {currency}{summary['remaining_balance']:,.2f}.",
        f"4. Savings Goal ({summary['savings_goal_percent']}%): ({salary:,.2f} × {summary['savings_goal_percent']}%) = {currency}{summary['savings_goal_inr']:,.2f}.",
        f"5. Actual Savings Rate: ((Salary {currency}{salary:,.2f} − Spent {currency}{summary['total_spent']:,.2f}) ÷ Salary {currency}{salary:,.2f}) × 100 = {summary['savings_rate']}%.",
    ]

    if has_previous:
        sign = "+" if salary_change_inr >= 0 else "-"
        steps.append(
            f"6. Salary Comparison: Current ({currency}{salary:,.2f}) − Previous = {sign}{currency}{abs(salary_change_inr):,.2f} ({sign}{abs(salary_change_pct):.2f}%)."
        )
    else:
        steps.append("6. Salary Comparison: First recorded month — no prior baseline available (Rule S8).")

    if is_complete:
        steps.append(f"7. Month Timeline: Month {month} has ended ({days_in_month}/{days_in_month} days elapsed). Actual month-end figures final.")
    else:
        steps.append(
            f"7. Month Timeline & Pacing: {days_elapsed} of {days_in_month} days elapsed. Projected spend = (Spend So Far ÷ {days_elapsed}) × {days_in_month}."
        )

    top_cat = max(categories, key=lambda c: c["spent"]) if categories else None
    if top_cat and top_cat["spent"] > 0:
        steps.append(
            f"8. Category Spend Lead: '{top_cat['category']}' utilized {currency}{top_cat['spent']:,.2f} ({top_cat['used_pct']}% of its {currency}{top_cat['budget']:,.2f} budget)."
        )

    return steps
