"""
agent/sensors.py
Collects, validates, and normalizes user input for the Knowledge-Based Personal Expense Monitoring Agent.
Part of the PEAS Sensor stage.
"""

import csv
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def validate_month(month_str: str) -> Tuple[bool, str]:
    """
    Validates that a month string is in valid YYYY-MM format.
    Returns (is_valid, error_message).
    """
    if not month_str or not isinstance(month_str, str):
        return False, "Month must be provided in YYYY-MM format."
    pattern = r"^\d{4}-(0[1-9]|1[0-2])$"
    if not re.match(pattern, month_str.strip()):
        return False, f"Invalid month format '{month_str}'. Expected YYYY-MM."
    return True, ""


def validate_salary(salary_val: Any) -> Tuple[bool, float, str]:
    """
    Validates numeric salary input. Salary cannot be negative.
    Returns (is_valid, parsed_salary, error_message).
    """
    if salary_val is None or str(salary_val).strip() == "":
        return False, 0.0, "Salary cannot be empty."
    try:
        val = float(salary_val)
        if val < 0:
            return False, 0.0, "Salary cannot be negative."
        return True, round(val, 2), ""
    except (ValueError, TypeError):
        return False, 0.0, f"Invalid salary '{salary_val}'. Must be a numeric amount."


def validate_other_income(other_income_val: Any) -> Tuple[bool, float, str]:
    """
    Validates numeric other income input. Cannot be negative.
    Returns (is_valid, parsed_amount, error_message).
    """
    if other_income_val is None or str(other_income_val).strip() == "":
        return True, 0.0, ""
    try:
        val = float(other_income_val)
        if val < 0:
            return False, 0.0, "Other income cannot be negative."
        return True, round(val, 2), ""
    except (ValueError, TypeError):
        return False, 0.0, f"Invalid other income '{other_income_val}'. Must be a numeric amount."


def validate_expense(
    date_str: str,
    category: str,
    description: str,
    amount_val: Any,
    selected_month: str
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validates a single expense entry:
    - Numeric amount > 0
    - Non-empty category
    - Valid date in YYYY-MM-DD format
    - Date falls strictly inside the selected month (YYYY-MM)
    """
    if not category or not category.strip():
        return False, None, "Category cannot be empty."

    # Validate amount
    try:
        amt = float(amount_val)
        if amt <= 0:
            return False, None, "Expense amount must be greater than zero."
    except (ValueError, TypeError):
        return False, None, f"Invalid expense amount '{amount_val}'. Must be a numeric amount."

    # Validate date
    if not date_str or not date_str.strip():
        return False, None, "Expense date cannot be empty."
    date_clean = date_str.strip()
    try:
        parsed_date = datetime.strptime(date_clean, "%Y-%m-%d")
    except ValueError:
        return False, None, f"Invalid date '{date_clean}'. Expected YYYY-MM-DD format."

    # Check date falls inside selected_month
    month_prefix = f"{parsed_date.year:04d}-{parsed_date.month:02d}"
    if month_prefix != selected_month:
        return False, None, (
            f"Expense date '{date_clean}' does not belong to the selected month '{selected_month}'."
        )

    clean_expense = {
        "date": date_clean,
        "category": category.strip(),
        "description": description.strip() if description else "",
        "amount": round(amt, 2),
        "month": selected_month,
    }
    return True, clean_expense, ""


def parse_and_validate_csv(
    file_content: str,
    default_month: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses a CSV string and validates expense rows.
    Expected CSV headers (case-insensitive):
    date, category, description (optional), amount, month (optional)
    Returns (valid_expenses, error_messages).
    """
    valid_expenses: List[Dict[str, Any]] = []
    errors: List[str] = []

    f = io.StringIO(file_content.strip())
    reader = csv.DictReader(f)

    if not reader.fieldnames:
        return [], ["Uploaded CSV is empty or has invalid headers."]

    # Normalize header names to lowercase
    normalized_headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    if "date" not in normalized_headers or "amount" not in normalized_headers:
        return [], ["CSV must contain at least 'date' and 'amount' columns."]

    row_num = 1
    for row in reader:
        row_num += 1
        date_val = row.get(normalized_headers.get("date", ""), "").strip()
        amount_val = row.get(normalized_headers.get("amount", ""), "").strip()
        category_val = row.get(normalized_headers.get("category", ""), "Miscellaneous").strip() or "Miscellaneous"
        desc_col = normalized_headers.get("description", "")
        desc_val = row.get(desc_col, "").strip() if desc_col else ""
        month_col = normalized_headers.get("month", "")
        row_month = row.get(month_col, "").strip() if month_col else (default_month or "")

        if not date_val:
            errors.append(f"Row {row_num}: Date is missing.")
            continue

        # Extract month from date if row_month not specified
        try:
            parsed_dt = datetime.strptime(date_val, "%Y-%m-%d")
            extracted_month = f"{parsed_dt.year:04d}-{parsed_dt.month:02d}"
        except ValueError:
            errors.append(f"Row {row_num}: Invalid date '{date_val}', expected YYYY-MM-DD.")
            continue

        target_month = row_month if row_month else extracted_month
        ok, exp_data, err = validate_expense(date_val, category_val, desc_val, amount_val, target_month)
        if not ok:
            errors.append(f"Row {row_num}: {err}")
        else:
            valid_expenses.append(exp_data)

    return valid_expenses, errors
