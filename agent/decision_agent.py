"""
agent/decision_agent.py
Runs all Knowledge Base rules, sorts and ranks alerts by severity (CRITICAL > WARNING > INFO > POSITIVE),
and adjusts advice strictness based on salary trends.
Part of the PEAS Reasoning stage.
"""

from typing import Any, Dict, List, Optional
from agent import rules

SEVERITY_WEIGHT = {
    "CRITICAL": 4,
    "WARNING": 3,
    "INFO": 2,
    "POSITIVE": 1,
}


def evaluate_all_rules(
    current_month: str,
    current_salary: float,
    other_income: float,
    change_type: Optional[str],
    expenses: List[Dict[str, Any]],
    category_metrics: List[Dict[str, Any]],
    summary_metrics: Dict[str, Any],
    historical_months: List[Dict[str, Any]],  # chronological list of prior months
    days_in_month: int,
    days_elapsed: int,
    is_month_complete: bool,
    currency: str = "₹"
) -> List[Dict[str, str]]:
    """
    Executes the entire rule engine against current month data and historical context.
    Returns prioritized list of alert objects.
    """
    alerts: List[Dict[str, str]] = []

    # 1. Budget rules for categories (R1, R2, R5)
    for cat in category_metrics:
        cat_name = cat["category"]
        spent = cat["spent"]
        budget = cat["budget"]

        # R2: Category >= 100%
        r2_alert = rules.rule_r2(cat_name, spent, budget, currency)
        if r2_alert:
            alerts.append(r2_alert)
        else:
            # R1: Category 80% <= spend < 100%
            r1_alert = rules.rule_r1(cat_name, spent, budget, currency)
            if r1_alert:
                alerts.append(r1_alert)

        # R5: Pacing (skip if month complete or already exceeded)
        r5_alert = rules.rule_r5(
            cat_name, spent, budget, days_elapsed, days_in_month, is_month_complete, currency
        )
        if r5_alert:
            alerts.append(r5_alert)

    # 2. Overall budget rules (R3, R7)
    total_spent = summary_metrics["total_spent"]
    savings_goal_inr = summary_metrics["savings_goal_inr"]

    r3_alert = rules.rule_r3(total_spent, current_salary, savings_goal_inr, currency)
    if r3_alert:
        alerts.append(r3_alert)
    else:
        # R7: Total spend <= 70% of allowable ceiling
        r7_alert = rules.rule_r7(total_spent, current_salary, savings_goal_inr, currency)
        if r7_alert:
            alerts.append(r7_alert)

    # 3. Discretionary spending rule (R6)
    ent_spent = next((c["spent"] for c in category_metrics if c["category"] == "Entertainment"), 0.0)
    shop_spent = next((c["spent"] for c in category_metrics if c["category"] == "Shopping"), 0.0)
    r6_alert = rules.rule_r6(ent_spent, shop_spent, current_salary, currency)
    if r6_alert:
        alerts.append(r6_alert)

    # 4. Large single expense rule (R4)
    budgets_map = {c["category"]: c["budget"] for c in category_metrics}
    for exp in expenses:
        cat_name = exp.get("category", "Miscellaneous")
        cat_budget = budgets_map.get(cat_name, budgets_map.get("Miscellaneous", 0.0))
        r4_alert = rules.rule_r4(
            exp.get("description", ""),
            float(exp.get("amount", 0.0)),
            cat_name,
            cat_budget,
            currency
        )
        if r4_alert:
            # Avoid flooding duplicate alerts for same category & amount
            if not any(a["id"] == "R4" and a["message"] == r4_alert["message"] for a in alerts):
                alerts.append(r4_alert)

    # 5. Salary trend rules (S1 - S8)
    prior_records = [m for m in historical_months if m["month"] < current_month]
    prior_records.sort(key=lambda m: m["month"])

    if not prior_records:
        # S8: First month with no history
        alerts.append(rules.rule_s8())
    else:
        prev_month = prior_records[-1]
        prev_salary = float(prev_month.get("salary", 0.0))

        # Special Case: >25% change confirmation
        special_alert = rules.rule_large_salary_change_prompt(current_salary, prev_salary, change_type)
        if special_alert:
            alerts.append(special_alert)

        # S2: Salary increased
        s2_alert = rules.rule_s2(current_salary, prev_salary, currency)
        if s2_alert:
            alerts.append(s2_alert)

        # Over budget categories for S3
        over_budget_cats = [c["category"] for c in category_metrics if c["used_pct"] >= 100.0]

        # S3: Salary decreased 1-10%
        s3_alert = rules.rule_s3(current_salary, prev_salary, over_budget_cats, currency)
        if s3_alert:
            alerts.append(s3_alert)

        # S4: Salary decreased >10%
        s4_alert = rules.rule_s4(current_salary, prev_salary, currency)
        if s4_alert:
            alerts.append(s4_alert)

        # Build 3-month sequence including current
        recent_salaries = [float(m["salary"]) for m in prior_records] + [current_salary]
        recent_expenses = [float(m.get("total_spent", 0.0)) for m in prior_records] + [total_spent]
        recent_savings_rates = [float(m.get("savings_rate", 0.0)) for m in prior_records] + [summary_metrics["savings_rate"]]

        # S5: Lifestyle inflation over 3 months
        s5_alert = rules.rule_s5(recent_salaries, recent_expenses)
        if s5_alert:
            alerts.append(s5_alert)

        # S6: Savings rate trend (fell 2 consecutive months or rose)
        s6_alert = rules.rule_s6(recent_savings_rates)
        if s6_alert:
            alerts.append(s6_alert)

        # S7: Salary decreased 2+ consecutive months
        s7_alert = rules.rule_s7(recent_salaries)
        if s7_alert:
            alerts.append(s7_alert)

    # Sort alerts by severity: CRITICAL (4) > WARNING (3) > INFO (2) > POSITIVE (1)
    # Secondary sort keeps deterministic order
    sorted_alerts = sorted(
        alerts,
        key=lambda a: (-SEVERITY_WEIGHT.get(a["severity"], 0), a["id"])
    )

    return sorted_alerts


def calculate_strictness_factor(
    alerts: List[Dict[str, str]],
    salary_change_pct: float
) -> float:
    """
    Adjusts advice strictness based on salary changes and risk severity.
    Returns a strictness multiplier (1.0 = normal, >1.0 = strict).
    """
    strictness = 1.0
    if salary_change_pct < -10.0:
        strictness = 1.5  # Lean budget needed
    elif salary_change_pct < -1.0:
        strictness = 1.25

    if any(a["id"] == "R3" for a in alerts):
        strictness += 0.25
    if any(a["id"] == "S7" for a in alerts):
        strictness += 0.25

    return strictness
