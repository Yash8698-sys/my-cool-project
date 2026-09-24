"""
app.py
Flask web routes for the Knowledge-Based Personal Expense Monitoring Agent.
Coordinates PEAS components: Sensors -> Salary Analysis -> Expense Calculation -> Rules -> Decision Agent -> Actuators.
"""

import io
import csv
from datetime import datetime
from typing import Dict, Any, List

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    Response,
    jsonify,
)

from database import (
    get_engine,
    get_session_factory,
    init_db,
    get_settings,
    Settings,
    MonthlySalary,
    Expense,
    DEFAULT_CATEGORIES,
    DEFAULT_SAVINGS_GOAL,
    DEFAULT_CURRENCY,
)
from agent import (
    sensors,
    salary_analysis,
    expense_calculation,
    decision_agent,
    actuators,
)

app = Flask(__name__)
app.secret_key = "knowledge-based-expense-agent-secret-key-2026"

engine = get_engine()
init_db(engine)
SessionFactory = get_session_factory(engine)


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Closes the scoped database session on request teardown."""
    SessionFactory.remove()


def current_ym() -> str:
    """Returns the current year-month as YYYY-MM."""
    now = datetime.now()
    return f"{now.year:04d}-{now.month:02d}"


def get_all_recorded_months(session) -> List[Dict[str, Any]]:
    """Retrieves all months with salary records or expenses, sorted chronologically."""
    salaries = session.query(MonthlySalary).order_by(MonthlySalary.month.asc()).all()
    all_expenses = session.query(Expense).all()

    # Group expenses by month
    expense_map: Dict[str, float] = {}
    for exp in all_expenses:
        expense_map[exp.month] = expense_map.get(exp.month, 0.0) + exp.amount

    month_set = set(s.month for s in salaries).union(expense_map.keys())
    if not month_set:
        return []

    sorted_months = sorted(list(month_set))
    history: List[Dict[str, Any]] = []

    salary_dict = {s.month: s for s in salaries}
    for m in sorted_months:
        sal_rec = salary_dict.get(m)
        sal = sal_rec.salary if sal_rec else 0.0
        other = sal_rec.other_income if sal_rec else 0.0
        spent = round(expense_map.get(m, 0.0), 2)
        sr = round(((sal - spent) / sal) * 100.0, 1) if sal > 0 else 0.0
        history.append({
            "month": m,
            "salary": sal,
            "other_income": other,
            "total_income": sal + other,
            "total_spent": spent,
            "savings": round(sal + other - spent, 2),
            "savings_rate": sr,
            "change_type": sal_rec.change_type if sal_rec else None,
        })
    return history


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    """Home redirect to the current month's dashboard or entry."""
    session = SessionFactory()
    latest_salary = session.query(MonthlySalary).order_by(MonthlySalary.month.desc()).first()
    target_month = latest_salary.month if latest_salary else current_ym()
    return redirect(url_for("dashboard", month=target_month))


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """
    GET/POST /settings
    Currency, savings goal (% of salary), budget limit per category as % of salary.
    """
    session = SessionFactory()
    app_settings = get_settings(session)

    if request.method == "POST":
        currency = request.form.get("currency", DEFAULT_CURRENCY).strip() or DEFAULT_CURRENCY
        savings_goal_raw = request.form.get("savings_goal", str(DEFAULT_SAVINGS_GOAL))

        try:
            savings_goal = float(savings_goal_raw)
            if savings_goal < 0 or savings_goal > 100:
                raise ValueError()
        except ValueError:
            flash("Savings goal must be a percentage between 0 and 100.", "danger")
            return redirect(url_for("settings_page"))

        # Category budgets
        new_budgets: Dict[str, float] = {}
        for cat in DEFAULT_CATEGORIES.keys():
            raw_val = request.form.get(f"budget_{cat}", "0")
            try:
                cat_val = float(raw_val)
                if cat_val < 0:
                    raise ValueError()
                new_budgets[cat] = cat_val
            except ValueError:
                flash(f"Budget percentage for {cat} must be a non-negative number.", "danger")
                return redirect(url_for("settings_page"))

        app_settings.currency = currency
        app_settings.savings_goal_percent = savings_goal
        app_settings.category_budgets = new_budgets
        session.commit()

        flash("Settings successfully updated.", "success")
        return redirect(url_for("settings_page"))

    return render_template(
        "settings.html",
        settings=app_settings,
        default_categories=DEFAULT_CATEGORIES,
    )


@app.route("/entry", methods=["GET", "POST"])
def entry_page():
    """
    GET/POST /entry
    Select month (YYYY-MM), enter salary and optional other income,
    and manage expenses.
    """
    session = SessionFactory()
    selected_month = request.args.get("month", current_ym())

    ok_month, err_m = sensors.validate_month(selected_month)
    if not ok_month:
        flash(err_m, "warning")
        selected_month = current_ym()

    # Handle salary update POST
    if request.method == "POST" and "update_salary" in request.form:
        raw_month = request.form.get("month", selected_month)
        ok_m, err_m = sensors.validate_month(raw_month)
        if not ok_m:
            flash(err_m, "danger")
            return redirect(url_for("entry_page", month=selected_month))

        selected_month = raw_month
        ok_sal, sal_val, err_sal = sensors.validate_salary(request.form.get("salary"))
        if not ok_sal:
            flash(err_sal, "danger")
            return redirect(url_for("entry_page", month=selected_month))

        ok_oth, oth_val, err_oth = sensors.validate_other_income(request.form.get("other_income", 0))
        if not ok_oth:
            flash(err_oth, "danger")
            return redirect(url_for("entry_page", month=selected_month))

        change_type = request.form.get("change_type", "").strip() or None

        rec = session.query(MonthlySalary).filter_by(month=selected_month).first()
        if rec:
            rec.salary = sal_val
            rec.other_income = oth_val
            if change_type:
                rec.change_type = change_type
        else:
            rec = MonthlySalary(
                month=selected_month,
                salary=sal_val,
                other_income=oth_val,
                change_type=change_type,
            )
            session.add(rec)
        session.commit()
        flash(f"Income record saved for {selected_month}.", "success")
        return redirect(url_for("entry_page", month=selected_month))

    salary_rec = session.query(MonthlySalary).filter_by(month=selected_month).first()
    expenses = session.query(Expense).filter_by(month=selected_month).order_by(Expense.date.desc()).all()
    app_settings = get_settings(session)

    # Check for large salary change requiring confirmation (>25%)
    all_months = get_all_recorded_months(session)
    salary_analysis_res = None
    if salary_rec:
        salary_analysis_res = salary_analysis.perform_salary_analysis(
            current_month=selected_month,
            current_salary=salary_rec.salary,
            past_salaries=all_months,
            category_percentages=app_settings.category_budgets,
            change_type=salary_rec.change_type,
        )

    # All distinct months for selector
    month_options = sorted(list(set([m["month"] for m in all_months] + [selected_month, current_ym()])))

    return render_template(
        "entry.html",
        selected_month=selected_month,
        salary_rec=salary_rec,
        expenses=expenses,
        settings=app_settings,
        salary_analysis=salary_analysis_res,
        month_options=month_options,
    )


@app.route("/expense/add", methods=["POST"])
def add_expense():
    """Adds a single expense item via form submission."""
    session = SessionFactory()
    selected_month = request.form.get("month", current_ym())
    date_str = request.form.get("date", "")
    category = request.form.get("category", "")
    description = request.form.get("description", "")
    amount_str = request.form.get("amount", "")

    ok, exp_data, err = sensors.validate_expense(date_str, category, description, amount_str, selected_month)
    if not ok:
        flash(err, "danger")
        return redirect(url_for("entry_page", month=selected_month))

    new_exp = Expense(
        month=exp_data["month"],
        date=exp_data["date"],
        category=exp_data["category"],
        description=exp_data["description"],
        amount=exp_data["amount"],
    )
    session.add(new_exp)
    session.commit()
    flash(f"Expense of {exp_data['amount']} added to {exp_data['category']}.", "success")
    return redirect(url_for("entry_page", month=selected_month))


@app.route("/expense/edit/<int:expense_id>", methods=["POST"])
def edit_expense(expense_id: int):
    """Updates an existing expense."""
    session = SessionFactory()
    exp = session.query(Expense).get(expense_id)
    if not exp:
        flash("Expense item not found.", "warning")
        return redirect(url_for("entry_page"))

    selected_month = exp.month
    date_str = request.form.get("date", exp.date)
    category = request.form.get("category", exp.category)
    description = request.form.get("description", exp.description)
    amount_str = request.form.get("amount", str(exp.amount))

    ok, exp_data, err = sensors.validate_expense(date_str, category, description, amount_str, selected_month)
    if not ok:
        flash(err, "danger")
        return redirect(url_for("entry_page", month=selected_month))

    exp.date = exp_data["date"]
    exp.category = exp_data["category"]
    exp.description = exp_data["description"]
    exp.amount = exp_data["amount"]
    session.commit()
    flash("Expense updated successfully.", "success")
    return redirect(url_for("entry_page", month=selected_month))


@app.route("/expense/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id: int):
    """Deletes an expense item."""
    session = SessionFactory()
    exp = session.query(Expense).get(expense_id)
    if exp:
        month = exp.month
        session.delete(exp)
        session.commit()
        flash("Expense deleted.", "info")
        return redirect(url_for("entry_page", month=month))
    flash("Expense not found.", "warning")
    return redirect(url_for("entry_page"))


@app.route("/dashboard/<month>")
def dashboard(month: str):
    """
    GET /dashboard/<month>
    Full analysis for the selected month:
    1. Salary trend card
    2. Summary metrics
    3. Category table (color-coded)
    4. Alerts list sorted by severity
    5. Up to 3 recommendations
    6. Chart.js charts (bar, line, doughnut)
    7. 'Show calculations' collapsible section
    """
    session = SessionFactory()
    ok_m, err_m = sensors.validate_month(month)
    if not ok_m:
        flash(err_m, "warning")
        return redirect(url_for("dashboard", month=current_ym()))

    app_settings = get_settings(session)
    salary_rec = session.query(MonthlySalary).filter_by(month=month).first()
    expenses = session.query(Expense).filter_by(month=month).order_by(Expense.date.desc()).all()
    all_history = get_all_recorded_months(session)

    current_salary = salary_rec.salary if salary_rec else 0.0
    other_income = salary_rec.other_income if salary_rec else 0.0
    change_type = salary_rec.change_type if salary_rec else None

    # 1. PEAS: Sensors / Input validation
    expenses_raw = [
        {"id": e.id, "date": e.date, "category": e.category, "description": e.description, "amount": e.amount}
        for e in expenses
    ]

    # 2. PEAS: Salary Analysis
    sal_analysis = salary_analysis.perform_salary_analysis(
        current_month=month,
        current_salary=current_salary,
        past_salaries=all_history,
        category_percentages=app_settings.category_budgets,
        change_type=change_type,
    )

    # 3. PEAS: Expense Calculation
    days_in_month, days_elapsed, is_complete = expense_calculation.get_month_day_metrics(month)
    categories = expense_calculation.calculate_category_metrics(
        expenses=expenses_raw,
        budgets_inr=sal_analysis["budgets_inr"],
        days_in_month=days_in_month,
        days_elapsed=days_elapsed,
        is_month_complete=is_complete,
    )

    summary = expense_calculation.calculate_summary_metrics(
        salary=current_salary,
        other_income=other_income,
        expenses=expenses_raw,
        savings_goal_percent=app_settings.savings_goal_percent,
        currency=app_settings.currency,
    )

    # 4. PEAS: Decision-Making Agent & Rules Engine
    raw_alerts = decision_agent.evaluate_all_rules(
        current_month=month,
        current_salary=current_salary,
        other_income=other_income,
        change_type=change_type,
        expenses=expenses_raw,
        category_metrics=categories,
        summary_metrics=summary,
        historical_months=all_history,
        days_in_month=days_in_month,
        days_elapsed=days_elapsed,
        is_month_complete=is_complete,
        currency=app_settings.currency,
    )

    # 5. PEAS: Actuators (Alerts, Recommendations, Charts, Explanations)
    alerts = actuators.build_alerts_view(raw_alerts)

    recommendations = actuators.build_recommendations(
        salary=current_salary,
        salary_change_inr=sal_analysis["change_inr"],
        salary_change_pct=sal_analysis["change_percent"],
        category_metrics=categories,
        summary_metrics=summary,
        alerts=raw_alerts,
        currency=app_settings.currency,
    )

    chart_payloads = actuators.build_chart_payloads(
        category_metrics=categories,
        historical_months=all_history,
    )

    calculations = expense_calculation.generate_calculation_explanations(
        month=month,
        salary=current_salary,
        other_income=other_income,
        summary=summary,
        categories=categories,
        days_in_month=days_in_month,
        days_elapsed=days_elapsed,
        is_complete=is_complete,
        salary_change_inr=sal_analysis["change_inr"],
        salary_change_pct=sal_analysis["change_percent"],
        has_previous=sal_analysis["has_previous"],
        currency=app_settings.currency,
    )

    # Month navigation
    available_months = sorted(list(set([m["month"] for m in all_history] + [month, current_ym()])))

    return render_template(
        "dashboard.html",
        month=month,
        settings=app_settings,
        salary_rec=salary_rec,
        salary_analysis=sal_analysis,
        summary=summary,
        categories=categories,
        alerts=alerts,
        recommendations=recommendations,
        charts=chart_payloads,
        calculations=calculations,
        available_months=available_months,
        expenses=expenses_raw,
    )


@app.route("/history")
def history_page():
    """
    GET /history
    Salary, spending, and savings across all recorded months.
    """
    session = SessionFactory()
    all_months = get_all_recorded_months(session)
    app_settings = get_settings(session)

    # Calculate totals
    total_income = sum(m["total_income"] for m in all_months)
    total_spent = sum(m["total_spent"] for m in all_months)
    total_savings = total_income - total_spent
    avg_savings_rate = (
        round(sum(m["savings_rate"] for m in all_months) / len(all_months), 1)
        if all_months else 0.0
    )

    # Line chart payload for history page
    line_labels = [m["month"] for m in all_months]
    line_salaries = [m["salary"] for m in all_months]
    line_spending = [m["total_spent"] for m in all_months]
    line_savings = [m["savings"] for m in all_months]

    history_chart = {
        "labels": line_labels,
        "datasets": [
            {
                "label": "Salary",
                "data": line_salaries,
                "borderColor": "#3b82f6",
                "backgroundColor": "rgba(59, 130, 246, 0.15)",
                "tension": 0.3,
                "borderWidth": 2.5,
            },
            {
                "label": "Spending",
                "data": line_spending,
                "borderColor": "#ef4444",
                "backgroundColor": "rgba(239, 68, 68, 0.15)",
                "tension": 0.3,
                "borderWidth": 2.5,
            },
            {
                "label": "Net Savings",
                "data": line_savings,
                "borderColor": "#10b981",
                "backgroundColor": "rgba(16, 185, 129, 0.15)",
                "tension": 0.3,
                "borderWidth": 2.5,
            },
        ],
    }

    return render_template(
        "history.html",
        all_months=all_months,
        settings=app_settings,
        total_income=total_income,
        total_spent=total_spent,
        total_savings=total_savings,
        avg_savings_rate=avg_savings_rate,
        history_chart=history_chart,
    )


@app.route("/export/<month>")
def export_month_csv(month: str):
    """
    GET /export/<month>
    Download the monthly report as CSV.
    """
    session = SessionFactory()
    salary_rec = session.query(MonthlySalary).filter_by(month=month).first()
    expenses = session.query(Expense).filter_by(month=month).order_by(Expense.date.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Summary section
    sal = salary_rec.salary if salary_rec else 0.0
    oth = salary_rec.other_income if salary_rec else 0.0
    tot_spent = sum(e.amount for e in expenses)
    remaining = (sal + oth) - tot_spent

    writer.writerow(["=== MONTHLY REPORT ==="])
    writer.writerow(["Month", month])
    writer.writerow(["Base Salary", sal])
    writer.writerow(["Other Income", oth])
    writer.writerow(["Total Expenses", round(tot_spent, 2)])
    writer.writerow(["Net Remaining", round(remaining, 2)])
    writer.writerow([])

    # Expenses line items
    writer.writerow(["Date", "Category", "Description", "Amount"])
    for e in expenses:
        writer.writerow([e.date, e.category, e.description, f"{e.amount:.2f}"])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Expense_Report_{month}.csv"},
    )


@app.route("/import", methods=["POST"])
def import_csv():
    """
    POST /import
    Upload a CSV of expenses.
    """
    session = SessionFactory()
    target_month = request.form.get("target_month", current_ym())

    if "file" not in request.files:
        flash("No file part selected.", "danger")
        return redirect(url_for("entry_page", month=target_month))

    file = request.files["file"]
    if file.filename == "":
        flash("No file chosen for upload.", "warning")
        return redirect(url_for("entry_page", month=target_month))

    try:
        content = file.stream.read().decode("utf-8")
        valid_expenses, errors = sensors.parse_and_validate_csv(content, default_month=target_month)

        if not valid_expenses and errors:
            flash(f"CSV Import Failed: {'; '.join(errors[:3])}", "danger")
            return redirect(url_for("entry_page", month=target_month))

        for exp in valid_expenses:
            new_item = Expense(
                month=exp["month"],
                date=exp["date"],
                category=exp["category"],
                description=exp["description"],
                amount=exp["amount"],
            )
            session.add(new_item)
        session.commit()

        success_msg = f"Successfully imported {len(valid_expenses)} expense item(s)."
        if errors:
            success_msg += f" Note: {len(errors)} row(s) had errors and were skipped."
        flash(success_msg, "success")
    except Exception as e:
        flash(f"Error parsing CSV file: {str(e)}", "danger")

    return redirect(url_for("entry_page", month=target_month))


@app.route("/sample-data", methods=["POST"])
def insert_sample_data():
    """
    POST /sample-data
    Inserts 3 months of demo data (salaries 48000, 50000, 45000)
    demonstrating salary increase (S2) and salary decrease (S3).
    """
    session = SessionFactory()

    # Clear existing demo months to keep clean state
    demo_months = ["2026-01", "2026-02", "2026-03"]
    session.query(Expense).filter(Expense.month.isin(demo_months)).delete(synchronize_session=False)
    session.query(MonthlySalary).filter(MonthlySalary.month.isin(demo_months)).delete(synchronize_session=False)

    # 1. Month 1: 2026-01 -> Salary: 48,000 (Base baseline)
    m1_sal = MonthlySalary(month="2026-01", salary=48000.0, other_income=2000.0, change_type=None)
    session.add(m1_sal)
    m1_expenses = [
        Expense(month="2026-01", date="2026-01-02", category="Rent", description="Apartment rent", amount=14400.0),
        Expense(month="2026-01", date="2026-01-05", category="Food", description="Grocery shopping", amount=4500.0),
        Expense(month="2026-01", date="2026-01-12", category="Transport", description="Metro rail card recharge", amount=1800.0),
        Expense(month="2026-01", date="2026-01-15", category="Utilities", description="Electricity and water bill", amount=2400.0),
        Expense(month="2026-01", date="2026-01-20", category="Shopping", description="Winter jacket", amount=3200.0),
        Expense(month="2026-01", date="2026-01-25", category="Entertainment", description="Movie and dinner", amount=1500.0),
        Expense(month="2026-01", date="2026-01-28", category="Miscellaneous", description="Home repairs", amount=1200.0),
    ]
    for e in m1_expenses:
        session.add(e)

    # 2. Month 2: 2026-02 -> Salary: 50,000 (+4.17% hike -> fires S2!)
    m2_sal = MonthlySalary(month="2026-02", salary=50000.0, other_income=0.0, change_type="hike")
    session.add(m2_sal)
    m2_expenses = [
        Expense(month="2026-02", date="2026-02-02", category="Rent", description="Apartment rent", amount=14400.0),
        Expense(month="2026-02", date="2026-02-06", category="Food", description="Groceries and weekly organics", amount=5200.0),
        Expense(month="2026-02", date="2026-02-10", category="Transport", description="Fuel and cab rides", amount=2200.0),
        Expense(month="2026-02", date="2026-02-14", category="Shopping", description="Shoes and clothing", amount=3800.0),
        Expense(month="2026-02", date="2026-02-18", category="Utilities", description="Internet and phone plan", amount=1900.0),
        Expense(month="2026-02", date="2026-02-22", category="Entertainment", description="Concert tickets", amount=1800.0),
        Expense(month="2026-02", date="2026-02-26", category="Health", description="Annual health checkup", amount=1500.0),
    ]
    for e in m2_expenses:
        session.add(e)

    # 3. Month 3: 2026-03 -> Salary: 45,000 (-10.0% drop -> fires S3!)
    m3_sal = MonthlySalary(month="2026-03", salary=45000.0, other_income=0.0, change_type="deduction")
    session.add(m3_sal)
    m3_expenses = [
        Expense(month="2026-03", date="2026-03-02", category="Rent", description="Apartment rent", amount=14000.0),
        Expense(month="2026-03", date="2026-03-05", category="Food", description="Bulk monthly groceries", amount=6200.0),
        Expense(month="2026-03", date="2026-03-10", category="Shopping", description="Electronic gadget sale", amount=5200.0),
        Expense(month="2026-03", date="2026-03-15", category="Transport", description="Cab commutes and fuel", amount=2500.0),
        Expense(month="2026-03", date="2026-03-18", category="Utilities", description="Electricity bill", amount=2100.0),
        Expense(month="2026-03", date="2026-03-21", category="Entertainment", description="Weekend outing", amount=1900.0),
        Expense(month="2026-03", date="2026-03-24", category="Miscellaneous", description="Unplanned vehicle servicing", amount=2300.0),
    ]
    for e in m3_expenses:
        session.add(e)

    session.commit()
    flash(
        "Successfully inserted 3 months of sample data (48,000 → 50,000 → 45,000). "
        "Showing March 2026 analysis demonstrating Rule S3!",
        "success"
    )
    return redirect(url_for("dashboard", month="2026-03"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
