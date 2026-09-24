"""
agent/rules.py
Knowledge Base Rules for the Knowledge-Based Personal Expense Monitoring Agent.
Every rule is implemented as a standalone function returning a dict:
{ "id": str, "severity": "CRITICAL" | "WARNING" | "INFO" | "POSITIVE", "category": str, "message": str }
or None if the rule condition is not met.
"""

from typing import Dict, List, Optional, Any


# ============================================================================
# BUDGET RULES (R1 - R8)
# ============================================================================

def rule_r1(
    category_name: str,
    spent: float,
    budget: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R1: category spend >= 80% and < 100% of its budget -> WARNING
    """
    if budget <= 0:
        return None
    used_pct = (spent / budget) * 100.0
    if 80.0 <= used_pct < 100.0:
        remaining = round(budget - spent, 2)
        return {
            "id": "R1",
            "severity": "WARNING",
            "category": category_name,
            "message": (
                f"{category_name} spending has reached {used_pct:.1f}% of its budget "
                f"({currency}{spent:,.2f} of {currency}{budget:,.2f}). "
                f"You have {currency}{remaining:,.2f} left for the month."
            ),
        }
    return None


def rule_r2(
    category_name: str,
    spent: float,
    budget: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R2: category spend >= 100% of its budget -> CRITICAL
    """
    if budget <= 0:
        if spent > 0:
            return {
                "id": "R2",
                "severity": "CRITICAL",
                "category": category_name,
                "message": (
                    f"{category_name} has no allocated budget but {currency}{spent:,.2f} "
                    f"has been spent."
                ),
            }
        return None

    used_pct = (spent / budget) * 100.0
    if used_pct >= 100.0:
        over = round(spent - budget, 2)
        return {
            "id": "R2",
            "severity": "CRITICAL",
            "category": category_name,
            "message": (
                f"{category_name} budget exceeded! Utilized {used_pct:.1f}% "
                f"({currency}{spent:,.2f} spent vs {currency}{budget:,.2f} budget). "
                f"Over by {currency}{over:,.2f}."
            ),
        }
    return None


def rule_r3(
    total_spent: float,
    salary: float,
    savings_goal_inr: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R3: total spend > (salary - savings goal) -> CRITICAL, savings goal at risk
    """
    spending_ceiling = salary - savings_goal_inr
    if total_spent > spending_ceiling:
        deficit = round(total_spent - spending_ceiling, 2)
        return {
            "id": "R3",
            "severity": "CRITICAL",
            "category": "Savings Goal",
            "message": (
                f"Savings goal is at risk! Total spending ({currency}{total_spent:,.2f}) "
                f"exceeds the max allowable spend limit ({currency}{spending_ceiling:,.2f}) "
                f"by {currency}{deficit:,.2f}."
            ),
        }
    return None


def rule_r4(
    expense_desc: str,
    expense_amount: float,
    category_name: str,
    category_budget: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R4: single expense > 30% of its category budget -> INFO, large expense
    """
    if category_budget <= 0:
        return None
    pct_of_cat = (expense_amount / category_budget) * 100.0
    if pct_of_cat > 30.0:
        label = expense_desc if expense_desc else f"Expense in {category_name}"
        return {
            "id": "R4",
            "severity": "INFO",
            "category": category_name,
            "message": (
                f"Noticeable single transaction: '{label}' of {currency}{expense_amount:,.2f} "
                f"accounts for {pct_of_cat:.1f}% of the monthly {category_name} budget."
            ),
        }
    return None


def rule_r5(
    category_name: str,
    spent: float,
    budget: float,
    days_elapsed: int,
    days_in_month: int,
    is_month_complete: bool,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R5: category on pace to exceed budget by month-end
        (spend so far / days elapsed x days in month) -> WARNING;
        skip if the month is already complete
    """
    if is_month_complete or days_elapsed <= 0 or budget <= 0 or spent <= 0:
        return None

    # If already exceeded, R2 covers it
    if spent >= budget:
        return None

    projected_spend = (spent / days_elapsed) * days_in_month
    if projected_spend > budget:
        projected_over = round(projected_spend - budget, 2)
        return {
            "id": "R5",
            "severity": "WARNING",
            "category": category_name,
            "message": (
                f"{category_name} is on pace to exceed its budget by month-end! "
                f"Current burn rate projects {currency}{projected_spend:,.2f} total spend "
                f"({currency}{projected_over:,.2f} over the {currency}{budget:,.2f} budget)."
            ),
        }
    return None


def rule_r6(
    entertainment_spent: float,
    shopping_spent: float,
    salary: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R6: Entertainment + Shopping > 25% of salary -> WARNING, reduce discretionary spending
    """
    if salary <= 0:
        return None
    discretionary_total = entertainment_spent + shopping_spent
    pct_of_salary = (discretionary_total / salary) * 100.0
    if pct_of_salary > 25.0:
        return {
            "id": "R6",
            "severity": "WARNING",
            "category": "Discretionary Spending",
            "message": (
                f"Discretionary spending (Shopping + Entertainment) is {pct_of_salary:.1f}% "
                f"of salary ({currency}{discretionary_total:,.2f}). "
                f"Consider reducing non-essential spending to preserve savings."
            ),
        }
    return None


def rule_r7(
    total_spent: float,
    salary: float,
    savings_goal_inr: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    R7: total spend <= 70% of (salary - savings goal) -> POSITIVE, on track
    """
    if salary <= 0:
        return None
    spending_ceiling = salary - savings_goal_inr
    if spending_ceiling <= 0:
        return None

    threshold = 0.70 * spending_ceiling
    if total_spent <= threshold:
        cushion = round(spending_ceiling - total_spent, 2)
        return {
            "id": "R7",
            "severity": "POSITIVE",
            "category": "Savings Goal",
            "message": (
                f"Great financial discipline! Total spend ({currency}{total_spent:,.2f}) "
                f"is well within 70% of allowable budget. You have {currency}{cushion:,.2f} "
                f"headroom while fully protecting your savings goal."
            ),
        }
    return None


def rule_r8(
    category_name: str,
    known_categories: List[str]
) -> Dict[str, str]:
    """
    R8: categories not in the budget list are treated as Miscellaneous
    Returns normalized category name and rule details.
    """
    is_known = category_name in known_categories
    final_cat = category_name if is_known else "Miscellaneous"
    return {
        "id": "R8",
        "severity": "INFO",
        "category": final_cat,
        "is_custom": not is_known,
        "message": (
            f"Category '{category_name}' is not in configured budget categories; "
            f"classified under Miscellaneous."
        ) if not is_known else f"Category '{category_name}' recognized.",
    }


# ============================================================================
# SALARY TREND RULES (S1 - S8)
# ============================================================================

def rule_s1(
    current_salary: float,
    previous_salary: float
) -> float:
    """
    S1: salary change % = (current - previous) / previous x 100
    """
    if previous_salary <= 0:
        return 0.0
    return round(((current_salary - previous_salary) / previous_salary) * 100.0, 2)


def rule_s2(
    current_salary: float,
    previous_salary: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    S2: salary increased -> POSITIVE; suggest saving at least 50% of the
        increment and recalculating budgets with the new salary
    """
    if previous_salary <= 0:
        return None
    change_pct = rule_s1(current_salary, previous_salary)
    if change_pct > 0:
        increment = round(current_salary - previous_salary, 2)
        save_amount = round(increment * 0.50, 2)
        return {
            "id": "S2",
            "severity": "POSITIVE",
            "category": "Salary Trend",
            "message": (
                f"Salary increased by {change_pct:.1f}% (+{currency}{increment:,.2f}). "
                f"Suggested action: Allocate at least 50% of this increment "
                f"({currency}{save_amount:,.2f}) directly into savings, and recalculate "
                f"category budgets using the new salary."
            ),
        }
    return None


def rule_s3(
    current_salary: float,
    previous_salary: float,
    categories_over_budget: List[str],
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    S3: salary decreased 1-10% -> WARNING; list the categories that now exceed
        their new, lower budget limits
    Condition: -10.0 <= change_pct <= -1.0
    """
    if previous_salary <= 0:
        return None
    change_pct = rule_s1(current_salary, previous_salary)
    # Salary decreased 1-10% (inclusive of -10.0%, e.g., 50000 -> 45000 is -10.0%)
    if -10.001 <= change_pct <= -0.999:
        drop_inr = round(previous_salary - current_salary, 2)
        if categories_over_budget:
            cat_list = ", ".join(categories_over_budget)
            cat_msg = f" The following categories now exceed their recalculated limits: {cat_list}."
        else:
            cat_msg = " Monitor upcoming expenses closely to stay within the revised category caps."

        return {
            "id": "S3",
            "severity": "WARNING",
            "category": "Salary Trend",
            "message": (
                f"Salary decreased by {abs(change_pct):.1f}% (-{currency}{drop_inr:,.2f}).{cat_msg}"
            ),
        }
    return None


def rule_s4(
    current_salary: float,
    previous_salary: float,
    currency: str = "₹"
) -> Optional[Dict[str, str]]:
    """
    S4: salary decreased more than 10% -> CRITICAL; recommend a lean budget,
        cutting Entertainment, Shopping, and Miscellaneous before essentials
    Condition: change_pct < -10.0
    """
    if previous_salary <= 0:
        return None
    change_pct = rule_s1(current_salary, previous_salary)
    if change_pct < -10.001:
        drop_inr = round(previous_salary - current_salary, 2)
        return {
            "id": "S4",
            "severity": "CRITICAL",
            "category": "Salary Trend",
            "message": (
                f"Significant salary reduction of {abs(change_pct):.1f}% (-{currency}{drop_inr:,.2f}). "
                f"Recommend immediate lean budget: cut discretionary spending in Entertainment, "
                f"Shopping, and Miscellaneous first to safeguard essential commitments (Rent, Food, Utilities)."
            ),
        }
    return None


def rule_s5(
    salaries: List[float],
    expenses: List[float]
) -> Optional[Dict[str, str]]:
    """
    S5: expenses grew faster than salary over the last 3 months -> WARNING
        (lifestyle inflation)
    Requires at least 3 months of history.
    """
    if len(salaries) < 3 or len(expenses) < 3:
        return None

    # Consider the 3 months: [m-2, m-1, m]
    s_start, s_end = salaries[-3], salaries[-1]
    e_start, e_end = expenses[-3], expenses[-1]

    if s_start <= 0 or e_start <= 0:
        return None

    s_growth_pct = ((s_end - s_start) / s_start) * 100.0
    e_growth_pct = ((e_end - e_start) / e_start) * 100.0

    if e_growth_pct > s_growth_pct and e_growth_pct > 0:
        return {
            "id": "S5",
            "severity": "WARNING",
            "category": "Salary Trend",
            "message": (
                f"Potential lifestyle inflation detected! Over the last 3 months, "
                f"your expenses grew by {e_growth_pct:.1f}% while salary changed by "
                f"{s_growth_pct:.1f}%. Growth in spending is outpacing income growth."
            ),
        }
    return None


def rule_s6(
    savings_rates: List[float]
) -> Optional[Dict[str, str]]:
    """
    S6: savings rate = (salary - spent) / salary; fell 2 consecutive months
        -> WARNING; rose -> POSITIVE
    """
    if len(savings_rates) < 2:
        return None

    # Check 2 consecutive drops: [sr_2, sr_1, sr_0]
    if len(savings_rates) >= 3:
        sr0, sr1, sr2 = savings_rates[-3], savings_rates[-2], savings_rates[-1]
        if sr2 < sr1 and sr1 < sr0:
            return {
                "id": "S6",
                "severity": "WARNING",
                "category": "Savings Rate Trend",
                "message": (
                    f"Savings rate has declined for two consecutive months "
                    f"({sr0:.1f}% → {sr1:.1f}% → {sr2:.1f}%). "
                    f"Review discretionary expenses to stop further savings erosion."
                ),
            }

    # Check rise from previous month
    if savings_rates[-1] > savings_rates[-2]:
        diff = round(savings_rates[-1] - savings_rates[-2], 1)
        return {
            "id": "S6",
            "severity": "POSITIVE",
            "category": "Savings Rate Trend",
            "message": (
                f"Savings rate improved by {diff:+.1f}% this month "
                f"({savings_rates[-2]:.1f}% → {savings_rates[-1]:.1f}%)."
            ),
        }

    return None


def rule_s7(
    salaries: List[float]
) -> Optional[Dict[str, str]]:
    """
    S7: salary decreased 2 or more consecutive months -> CRITICAL; recommend an
        urgent review of fixed costs (rent, EMIs, utilities)
    """
    if len(salaries) < 3:
        return None

    s0, s1, s2 = salaries[-3], salaries[-2], salaries[-1]
    if s2 < s1 and s1 < s0:
        return {
            "id": "S7",
            "severity": "CRITICAL",
            "category": "Salary Trend",
            "message": (
                f"Salary has dropped for 2 consecutive months. "
                f"Recommend an urgent review of fixed costs (rent, EMIs, utilities) "
                f"and renegotiating contracts or subscriptions."
            ),
        }
    return None


def rule_s8() -> Dict[str, str]:
    """
    S8: first month with no history -> show "No previous data for salary comparison" and skip S1-S7
    """
    return {
        "id": "S8",
        "severity": "INFO",
        "category": "Salary Trend",
        "message": "No previous data for salary comparison.",
    }


def rule_large_salary_change_prompt(
    current_salary: float,
    previous_salary: float,
    change_type: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """
    Special Case Rule:
    If salary changes by more than 25% versus previous month,
    show a confirmation prompt asking whether it is a hike, bonus, or deduction.
    """
    if previous_salary <= 0:
        return None
    change_pct = rule_s1(current_salary, previous_salary)
    if abs(change_pct) > 25.0 and (not change_type or not change_type.strip()):
        return {
            "id": "SPECIAL_CONFIRMATION",
            "severity": "WARNING",
            "category": "Salary Verification",
            "message": (
                f"Salary changed by {change_pct:+.1f}% versus last month. "
                f"Please confirm whether this was a hike, bonus, or deduction to calibrate advice."
            ),
        }
    return None
