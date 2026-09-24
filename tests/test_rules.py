"""
tests/test_rules.py
Unit tests for all Knowledge Base rules (R1-R8 and S1-S8),
including the required salary drop from 50,000 to 45,000 triggering Rule S3.
"""

import pytest
from agent import rules


# ============================================================================
# BUDGET RULES TESTS (R1 - R8)
# ============================================================================

def test_rule_r1_warning():
    """R1 fires WARNING when category spend is >= 80% and < 100%."""
    # 85% spent
    alert = rules.rule_r1("Food", spent=850.0, budget=1000.0, currency="₹")
    assert alert is not None
    assert alert["id"] == "R1"
    assert alert["severity"] == "WARNING"
    assert "Food" in alert["category"]
    assert "85.0%" in alert["message"]

    # Exactly 80%
    alert_80 = rules.rule_r1("Rent", spent=800.0, budget=1000.0)
    assert alert_80 is not None
    assert alert_80["id"] == "R1"

    # Below 80% should not fire
    assert rules.rule_r1("Food", spent=799.0, budget=1000.0) is None
    # 100% or above should not fire R1 (handled by R2)
    assert rules.rule_r1("Food", spent=1000.0, budget=1000.0) is None


def test_rule_r2_critical():
    """R2 fires CRITICAL when category spend is >= 100% of budget."""
    # Exactly 100%
    alert = rules.rule_r2("Shopping", spent=1000.0, budget=1000.0, currency="₹")
    assert alert is not None
    assert alert["id"] == "R2"
    assert alert["severity"] == "CRITICAL"
    assert "100.0%" in alert["message"]

    # Over 100% (e.g. 150%)
    alert_over = rules.rule_r2("Entertainment", spent=1500.0, budget=1000.0)
    assert alert_over is not None
    assert alert_over["id"] == "R2"
    assert alert_over["severity"] == "CRITICAL"
    assert "Over by" in alert_over["message"]

    # Below 100% should not fire
    assert rules.rule_r2("Shopping", spent=999.0, budget=1000.0) is None


def test_rule_r3_savings_goal_at_risk():
    """R3 fires CRITICAL when total spend > (salary - savings goal)."""
    salary = 50000.0
    savings_goal_inr = 10000.0  # 20%
    # Allowable ceiling = 40000. Spend = 42000 -> exceeds ceiling
    alert = rules.rule_r3(total_spent=42000.0, salary=salary, savings_goal_inr=savings_goal_inr)
    assert alert is not None
    assert alert["id"] == "R3"
    assert alert["severity"] == "CRITICAL"
    assert "Savings goal is at risk" in alert["message"]

    # Spend <= allowable ceiling should not fire
    assert rules.rule_r3(total_spent=40000.0, salary=salary, savings_goal_inr=savings_goal_inr) is None
    assert rules.rule_r3(total_spent=35000.0, salary=salary, savings_goal_inr=savings_goal_inr) is None


def test_rule_r4_large_single_expense():
    """R4 fires INFO when a single expense is > 30% of category budget."""
    category_budget = 10000.0
    # 3500 is 35% of budget (> 30%)
    alert = rules.rule_r4(
        expense_desc="Flight ticket",
        expense_amount=3500.0,
        category_name="Transport",
        category_budget=category_budget
    )
    assert alert is not None
    assert alert["id"] == "R4"
    assert alert["severity"] == "INFO"
    assert "35.0%" in alert["message"]
    assert "Flight ticket" in alert["message"]

    # Exactly 30% or below should not fire
    assert rules.rule_r4("Bus pass", 3000.0, "Transport", category_budget) is None
    assert rules.rule_r4("Metro", 2500.0, "Transport", category_budget) is None


def test_rule_r5_pacing_warning():
    """R5 fires WARNING when category is on pace to exceed budget, skipped if month complete."""
    budget = 10000.0
    # Day 10 of 30, spent 4000. Pace = (4000/10)*30 = 12000 (> 10000)
    alert = rules.rule_r5(
        category_name="Food",
        spent=4000.0,
        budget=budget,
        days_elapsed=10,
        days_in_month=30,
        is_month_complete=False
    )
    assert alert is not None
    assert alert["id"] == "R5"
    assert alert["severity"] == "WARNING"
    assert "on pace to exceed" in alert["message"]

    # If month is complete, R5 must be skipped
    alert_complete = rules.rule_r5(
        category_name="Food",
        spent=4000.0,
        budget=budget,
        days_elapsed=30,
        days_in_month=30,
        is_month_complete=True
    )
    assert alert_complete is None

    # If pacing within budget (e.g. spent 2000 in 10 days -> pace 6000 <= 10000)
    assert rules.rule_r5("Food", 2000.0, budget, 10, 30, False) is None


def test_rule_r6_discretionary_warning():
    """R6 fires WARNING when Entertainment + Shopping > 25% of salary."""
    salary = 50000.0
    # 25% of 50000 is 12500. Total = 7000 + 6000 = 13000 (26%)
    alert = rules.rule_r6(entertainment_spent=7000.0, shopping_spent=6000.0, salary=salary)
    assert alert is not None
    assert alert["id"] == "R6"
    assert alert["severity"] == "WARNING"
    assert "26.0%" in alert["message"]

    # Total <= 25% (e.g. 12000) should not fire
    assert rules.rule_r6(entertainment_spent=6000.0, shopping_spent=6000.0, salary=salary) is None


def test_rule_r7_positive_savings_on_track():
    """R7 fires POSITIVE when total spend <= 70% of (salary - savings goal)."""
    salary = 50000.0
    savings_goal = 10000.0  # Allowable ceiling = 40000. 70% threshold = 28000
    # Spend = 25000 <= 28000
    alert = rules.rule_r7(total_spent=25000.0, salary=salary, savings_goal_inr=savings_goal)
    assert alert is not None
    assert alert["id"] == "R7"
    assert alert["severity"] == "POSITIVE"
    assert "discipline" in alert["message"].lower()

    # Spend > 70% ceiling (e.g. 30000 > 28000) should not fire R7
    assert rules.rule_r7(total_spent=30000.0, salary=salary, savings_goal_inr=savings_goal) is None


def test_rule_r8_category_normalization():
    """R8 maps categories not in budget list to Miscellaneous."""
    known = ["Food", "Rent", "Transport", "Miscellaneous"]
    res_known = rules.rule_r8("Food", known)
    assert res_known["category"] == "Food"
    assert not res_known["is_custom"]

    res_unknown = rules.rule_r8("Electronics", known)
    assert res_unknown["category"] == "Miscellaneous"
    assert res_unknown["is_custom"]


# ============================================================================
# SALARY TREND RULES TESTS (S1 - S8)
# ============================================================================

def test_rule_s1_salary_percentage_calculation():
    """S1 accurately computes percentage change."""
    # Increase from 48000 to 50000 = +4.17%
    pct_up = rules.rule_s1(50000.0, 48000.0)
    assert pct_up == pytest.approx(4.17, rel=1e-2)

    # Decrease from 50000 to 45000 = -10.0%
    pct_down = rules.rule_s1(45000.0, 50000.0)
    assert pct_down == -10.0


def test_rule_s2_salary_increase():
    """S2 fires POSITIVE when salary increases, suggesting 50% savings of increment."""
    alert = rules.rule_s2(current_salary=50000.0, previous_salary=48000.0)
    assert alert is not None
    assert alert["id"] == "S2"
    assert alert["severity"] == "POSITIVE"
    # Increment is 2000, 50% is 1000
    assert "1,000.00" in alert["message"]
    assert "50%" in alert["message"]


def test_rule_s3_salary_drop_50000_to_45000():
    """
    CRITICAL TEST REQUIREMENT:
    Salary drop from 50000 to 45000 MUST fire S3 (1-10% decrease).
    """
    prev_salary = 50000.0
    curr_salary = 45000.0
    # Drop is exactly -10.0%
    alert = rules.rule_s3(
        current_salary=curr_salary,
        previous_salary=prev_salary,
        categories_over_budget=["Food", "Shopping"]
    )
    assert alert is not None, "Rule S3 MUST fire for drop from 50,000 to 45,000!"
    assert alert["id"] == "S3"
    assert alert["severity"] == "WARNING"
    assert "10.0%" in alert["message"]
    assert "Food, Shopping" in alert["message"]


def test_rule_s3_moderate_drop():
    """S3 fires for any drop between 1% and 10%."""
    # 5% drop (50000 -> 47500)
    alert = rules.rule_s3(47500.0, 50000.0, categories_over_budget=[])
    assert alert is not None
    assert alert["id"] == "S3"
    assert alert["severity"] == "WARNING"
    assert "5.0%" in alert["message"]


def test_rule_s4_salary_drop_more_than_10_percent():
    """S4 fires CRITICAL when salary drops more than 10%."""
    # 20% drop (50000 -> 40000)
    alert = rules.rule_s4(current_salary=40000.0, previous_salary=50000.0)
    assert alert is not None
    assert alert["id"] == "S4"
    assert alert["severity"] == "CRITICAL"
    assert "lean budget" in alert["message"].lower()
    assert "20.0%" in alert["message"]

    # 10% drop does NOT fire S4 (it fires S3)
    assert rules.rule_s4(current_salary=45000.0, previous_salary=50000.0) is None


def test_rule_s5_lifestyle_inflation():
    """S5 fires WARNING when expense growth exceeds salary growth over 3 months."""
    salaries = [40000.0, 42000.0, 44000.0]  # +10% growth
    expenses = [30000.0, 35000.0, 42000.0]  # +40% growth
    alert = rules.rule_s5(salaries, expenses)
    assert alert is not None
    assert alert["id"] == "S5"
    assert alert["severity"] == "WARNING"
    assert "lifestyle inflation" in alert["message"].lower()

    # Expenses grew slower than salary: should not fire
    expenses_slow = [30000.0, 31000.0, 31500.0]  # +5% growth
    assert rules.rule_s5(salaries, expenses_slow) is None


def test_rule_s6_savings_rate_trend():
    """S6 fires WARNING if savings rate fell 2 consecutive months, POSITIVE if it rose."""
    # 2 consecutive drops: 30% -> 25% -> 18%
    alert_fall = rules.rule_s6([30.0, 25.0, 18.0])
    assert alert_fall is not None
    assert alert_fall["id"] == "S6"
    assert alert_fall["severity"] == "WARNING"
    assert "two consecutive months" in alert_fall["message"]

    # Rise: 18% -> 24%
    alert_rise = rules.rule_s6([18.0, 24.0])
    assert alert_rise is not None
    assert alert_rise["id"] == "S6"
    assert alert_rise["severity"] == "POSITIVE"
    assert "improved" in alert_rise["message"].lower()


def test_rule_s7_salary_decreased_consecutive_months():
    """S7 fires CRITICAL when salary decreases 2 or more consecutive months."""
    salaries = [55000.0, 50000.0, 45000.0]
    alert = rules.rule_s7(salaries)
    assert alert is not None
    assert alert["id"] == "S7"
    assert alert["severity"] == "CRITICAL"
    assert "2 consecutive months" in alert["message"]
    assert "fixed costs" in alert["message"].lower()

    # Not 2 consecutive drops
    assert rules.rule_s7([45000.0, 50000.0, 48000.0]) is None


def test_rule_s8_first_month():
    """S8 fires INFO for first recorded month with no history."""
    alert = rules.rule_s8()
    assert alert["id"] == "S8"
    assert alert["severity"] == "INFO"
    assert "No previous data for salary comparison" in alert["message"]


def test_special_large_salary_change_prompt():
    """Special case: salary change > 25% prompts for confirmation."""
    # From 40000 to 55000 (+37.5%) with no change_type confirmed
    alert = rules.rule_large_salary_change_prompt(55000.0, 40000.0, change_type=None)
    assert alert is not None
    assert alert["id"] == "SPECIAL_CONFIRMATION"
    assert "hike, bonus, or deduction" in alert["message"]

    # When user has confirmed change_type, prompt does not trigger
    alert_confirmed = rules.rule_large_salary_change_prompt(55000.0, 40000.0, change_type="hike")
    assert alert_confirmed is None
