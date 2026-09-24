"""
agent/salary_analysis.py
Analyzes salary history, detects trends, calculates month-over-month salary changes,
evaluates 3-month trajectories, and dynamically computes INR budget allocations.
Part of the PEAS Reasoning / Knowledge Processing stage.
"""

from typing import Dict, List, Optional, Tuple, Any


def analyze_salary_change(
    current_salary: float,
    previous_salary: Optional[float]
) -> Tuple[float, float]:
    """
    Computes absolute change in INR and percentage change compared to the previous month.
    Returns (change_inr, change_percent).
    """
    if previous_salary is None or previous_salary <= 0:
        return 0.0, 0.0

    change_inr = round(current_salary - previous_salary, 2)
    change_pct = round(((current_salary - previous_salary) / previous_salary) * 100.0, 2)
    return change_inr, change_pct


def detect_salary_trend(salary_history: List[float]) -> str:
    """
    Determines the trend ('rising', 'falling', 'stable') over recent months (up to 3).
    salary_history should be sorted chronologically (oldest to newest).
    """
    if not salary_history or len(salary_history) < 2:
        return "stable"

    recent = salary_history[-3:]
    if len(recent) == 2:
        diff = recent[1] - recent[0]
        if diff > 0:
            return "rising"
        elif diff < 0:
            return "falling"
        return "stable"

    # For 3 months: recent[0], recent[1], recent[2]
    s0, s1, s2 = recent[0], recent[1], recent[2]
    if s2 > s1 and s1 >= s0:
        return "rising"
    if s2 >= s1 and s1 > s0:
        return "rising"
    if s2 < s1 and s1 <= s0:
        return "falling"
    if s2 <= s1 and s1 < s0:
        return "falling"

    # Overall net movement
    if s2 > s1:
        return "rising"
    elif s2 < s1:
        return "falling"
    return "stable"


def calculate_category_budgets_inr(
    salary: float,
    category_percentages: Dict[str, float]
) -> Dict[str, float]:
    """
    Recalculates budget limits in INR for each category based on current month's salary.
    """
    budgets_inr: Dict[str, float] = {}
    for category, pct in category_percentages.items():
        budgets_inr[category] = round((salary * (pct / 100.0)), 2)
    return budgets_inr


def check_large_salary_change(
    current_salary: float,
    previous_salary: Optional[float],
    change_type: Optional[str]
) -> Dict[str, Any]:
    """
    Special Case Checker:
    If salary changes by more than 25% versus the previous month,
    determines if user confirmation is required (hike, bonus, or deduction).
    """
    if previous_salary is None or previous_salary <= 0:
        return {"large_change": False, "change_pct": 0.0, "needs_confirmation": False}

    _, change_pct = analyze_salary_change(current_salary, previous_salary)
    large_change = abs(change_pct) > 25.0
    needs_confirmation = large_change and (not change_type or not change_type.strip())

    return {
        "large_change": large_change,
        "change_pct": change_pct,
        "needs_confirmation": needs_confirmation,
        "change_type": change_type,
    }


def perform_salary_analysis(
    current_month: str,
    current_salary: float,
    past_salaries: List[Dict[str, Any]],  # list of {"month": "YYYY-MM", "salary": float}
    category_percentages: Dict[str, float],
    change_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Full salary analysis coordinator for the given month against historical records.
    """
    # Sort past records chronologically before current_month
    prior_records = [r for r in past_salaries if r["month"] < current_month]
    prior_records.sort(key=lambda r: r["month"])

    previous_record = prior_records[-1] if prior_records else None
    previous_salary = previous_record["salary"] if previous_record else None

    change_inr, change_pct = analyze_salary_change(current_salary, previous_salary)

    # History including current
    full_history = [r["salary"] for r in prior_records] + [current_salary]
    trend = detect_salary_trend(full_history)

    budgets_inr = calculate_category_budgets_inr(current_salary, category_percentages)
    large_change_info = check_large_salary_change(current_salary, previous_salary, change_type)

    return {
        "current_month": current_month,
        "current_salary": current_salary,
        "previous_month": previous_record["month"] if previous_record else None,
        "previous_salary": previous_salary,
        "change_inr": change_inr,
        "change_percent": change_pct,
        "trend": trend,
        "budgets_inr": budgets_inr,
        "has_previous": previous_salary is not None,
        "large_change_info": large_change_info,
        "salary_history": full_history,
    }
