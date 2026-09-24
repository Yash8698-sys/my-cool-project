# Knowledge-Based Personal Expense Monitoring Agent

A rule-based, deterministic financial monitoring web application built with **Python Flask**, **SQLite (via SQLAlchemy)**, **Jinja2 templates**, **Bootstrap 5**, and **Chart.js**.

The agent monitors monthly income, analyzes expenditure against personalized category budgets, models multi-month trajectories, and triggers deterministic alerts and recommendations via an **IF-THEN Knowledge Base** without any external AI API dependencies.

---

## 1. PEAS Framework Specification

| PEAS Component | System Implementation | Code Mapping |
| :--- | :--- | :--- |
| **Performance Measure** | Accurate expense accounting, exact salary trend detection, timely budget deficit warnings, and actionable budget allocations. | [`agent/rules.py`](file:///c:/Users/Yash/Downloads/Knowledge-Expense-Ledger/agent/rules.py), [`agent/decision_agent.py`](file:///c:/Users/Yash/Downloads/Knowledge-Expense-Ledger/agent/decision_agent.py) |
| **Environment** | Monthly base salary, other income, categorized expense transactions, user-defined budget percentage caps, and historical monthly records. | SQLite Database ([`database.py`](file:///c:/Users/Yash/Downloads/Knowledge-Expense-Ledger/database.py)) |
| **Sensors (Input)** | Web forms and CSV file uploads capturing salary, transaction dates, descriptions, categories, and amounts. | [`agent/sensors.py`](file:///c:/Users/Yash/Downloads/Knowledge-Expense-Ledger/agent/sensors.py) |
| **Actuators (Output)** | Prioritized color-coded alert badges, specific INR recommendations, interactive Chart.js visualizations, calculation audits, and CSV reports. | [`agent/actuators.py`](file:///c:/Users/Yash/Downloads/Knowledge-Expense-Ledger/agent/actuators.py), HTML Templates |

---

## 2. Agent Architecture

The agent operates across a deterministic 6-stage pipeline:

```
[ User Input / CSV ]
        │
        ▼
1. Sensors (agent/sensors.py)
   - Validates non-negative amounts, date boundaries, and required fields
        │
        ▼
2. Salary Analysis (agent/salary_analysis.py)
   - Computes MoM change (INR & %), 3-month trend, and recalculated INR category budgets
        │
        ▼
3. Expense Calculation (agent/expense_calculation.py)
   - Aggregates category spending, pacing projections, and savings rates
        │
        ▼
4. Knowledge Base Rules (agent/rules.py)
   - Standalone functions evaluating budget constraints (R1-R8) & salary dynamics (S1-S8)
        │
        ▼
5. Decision Agent (agent/decision_agent.py)
   - Ranks alerts by severity (CRITICAL > WARNING > INFO > POSITIVE) & adapts strictness
        │
        ▼
6. Actuators (agent/actuators.py)
   - Generates UI alert badges, up to 3 INR recommendations, and Chart.js datasets
```

---

## 3. Knowledge Base Rules Reference

### Budget Rules
- **R1**: Category spend $\ge 80\%$ and $< 100\%$ of budget $\rightarrow$ `WARNING`.
- **R2**: Category spend $\ge 100\%$ of budget $\rightarrow$ `CRITICAL`.
- **R3**: Total spend $> (\text{Salary} - \text{Savings Goal})$ $\rightarrow$ `CRITICAL` (Savings goal compromised).
- **R4**: Single transaction $> 30\%$ of category budget $\rightarrow$ `INFO` (Large individual transaction).
- **R5**: Category on pace to exceed budget by month-end $\rightarrow$ `WARNING` (Skipped if month is complete).
- **R6**: Entertainment + Shopping $> 25\%$ of salary $\rightarrow$ `WARNING` (Discretionary spending warning).
- **R7**: Total spend $\le 70\%$ of $(\text{Salary} - \text{Savings Goal})$ $\rightarrow$ `POSITIVE` (Disciplined pacing).
- **R8**: Unrecognized categories default to **Miscellaneous**.

### Salary Trend Rules (Requires Prior History)
- **S1**: Salary Change $\% = \frac{\text{Current} - \text{Previous}}{\text{Previous}} \times 100$.
- **S2**: Salary increased $\rightarrow$ `POSITIVE` (Suggests saving $\ge 50\%$ of increment).
- **S3**: Salary decreased $1\text{–}10\%$ $\rightarrow$ `WARNING` (Highlights categories exceeding new lower limits; e.g. 50,000 to 45,000).
- **S4**: Salary decreased $> 10\%$ $\rightarrow$ `CRITICAL` (Recommends lean budget prioritizing essentials).
- **S5**: Expenses grew faster than salary over last 3 months $\rightarrow$ `WARNING` (Lifestyle inflation alert).
- **S6**: Savings rate fell 2 consecutive months $\rightarrow$ `WARNING`; rose $\rightarrow$ `POSITIVE`.
- **S7**: Salary decreased 2 or more consecutive months $\rightarrow$ `CRITICAL` (Urgent fixed-cost review).
- **S8**: First recorded month $\rightarrow$ `INFO` ("No previous data for salary comparison").
- **Special Case**: If salary changes by $> 25\%$, prompts confirmation for **hike**, **bonus**, or **deduction**.

---

## 4. Project Structure

```
├── app.py                      # Flask routes and PEAS coordinator
├── database.py                 # SQLAlchemy SQLite models (Settings, MonthlySalary, Expense)
├── requirements.txt            # Python dependencies (Flask, SQLAlchemy, pytest)
├── README.md                   # Complete architectural and operational documentation
├── agent/
│   ├── __init__.py
│   ├── sensors.py              # Sensor input collection and validation
│   ├── salary_analysis.py      # Salary metrics, trends, and INR budget calculation
│   ├── expense_calculation.py   # Spending totals, category metrics, and burn rate pacing
│   ├── rules.py                # Standalone IF-THEN knowledge base rules (R1-R8, S1-S8)
│   ├── decision_agent.py       # Severity prioritization and advice calibration
│   └── actuators.py            # Presentation formatting, INR recommendations, and Chart.js payloads
├── templates/
│   ├── base.html               # Responsive Bootstrap 5 shell, navigation, and flash alerts
│   ├── settings.html           # Currency, savings goal %, and category budget limits
│   ├── entry.html              # Salary entry, expense creation/editing, CSV upload
│   ├── dashboard.html          # Full monthly analytics, cards, table, alerts, recommendations, and charts
│   └── history.html            # Multi-month historical comparison and trajectory graphs
├── static/
│   ├── css/style.css           # Custom styling and color coding
│   └── js/main.js              # Client-side UI enhancements
└── tests/
    └── test_rules.py           # Pytest test suite covering every rule (including 50k -> 45k S3 test)
```

---

## 5. Setup & Running the Application

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Unit Test Suite
Verify that all 18 Knowledge Base rules pass:
```bash
pytest tests/test_rules.py
```

### 3. Start the Web Server
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 6. Pre-Loaded Demo Scenario

Click the **"Load Demo Data"** button in the top navigation bar to populate three months of realistic data:
1. **Month 1 (2026-01)**: Base salary ₹48,000 (Baseline established, Rule S8).
2. **Month 2 (2026-02)**: Base salary ₹50,000 (+4.17% hike $\rightarrow$ triggers **Rule S2** with 50% increment savings advice).
3. **Month 3 (2026-03)**: Base salary ₹45,000 (-10.0% reduction $\rightarrow$ triggers **Rule S3** listing over-budget categories).

---

## 7. Compliance & Disclaimer

> [!NOTE]
> This application provides automated budgeting guidance and rule-based spending heuristics only. It does not provide investment, tax, or legal advice. All financial messages are structured to be clear, supportive, and non-judgmental.
