import csv
import json
import os
from typing import Dict, Any, List, Tuple
from models.schemas import UserProfile
from engine.cashflow_simulator import CashflowSimulator
from eval.evaluate import load_user_profiles

VALID_STATUSES = {"AFFORDABLE_NOW", "AFFORDABLE_WITH_PLAN", "AFFORDABLE_LATER", "NOT_AFFORDABLE"}
VALID_METHODS = {"PAY_IN_FULL", "INSTALLMENTS_3M", "INSTALLMENTS_6M", "PARTIAL_PAYMENT", "WAIT_FOR_INCOME", "DO_NOT_PROCEED"}
REQUIRED_FIELDS = [
    "request_id", "user_id", "amount_safe_to_pay", "affordability_status",
    "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment",
    "spending_changes_needed", "decision_explanation"
]

def validate_output_csv(
    output_csv_path: str,
    requests_csv_path: str,
    profiles_json_path: str
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    Validates output.csv against schema requirements, request coverage,
    valid data types, valid payment plans, and financial safety constraints.
    Returns (is_valid, list_of_errors, list_of_row_results).
    """
    errors = []
    row_results = []

    if not os.path.exists(output_csv_path):
        return False, [f"Output file '{output_csv_path}' does not exist."], []

    # Load profiles and requests
    profiles = load_user_profiles(profiles_json_path)
    requests_dict = {}
    with open(requests_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            requests_dict[row["request_id"]] = row

    # Load output.csv
    preds_dict = {}
    with open(output_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        if not header or header != REQUIRED_FIELDS:
            errors.append(f"Header schema mismatch. Required: {REQUIRED_FIELDS}, Found: {header}")
        
        for row_idx, row in enumerate(reader, start=1):
            req_id = row.get("request_id")
            if not req_id:
                errors.append(f"Row {row_idx}: Missing request_id.")
                continue
            preds_dict[req_id] = row

    # Check request coverage
    for req_id in requests_dict.keys():
        if req_id not in preds_dict:
            errors.append(f"Missing prediction for request_id: {req_id}")

    simulator = CashflowSimulator(forecast_days=60)

    # Validate each prediction row
    for req_id, pred in preds_dict.items():
        if req_id not in requests_dict:
            errors.append(f"Unknown request_id in output.csv: {req_id}")
            continue

        row_errors = []
        req = requests_dict[req_id]
        u_id = pred.get("user_id")
        req_cost = float(req["total_cost"])

        if u_id != req["user_id"]:
            row_errors.append(f"user_id mismatch ({u_id} vs {req['user_id']}).")

        # 1. Numeric validation: amount_safe_to_pay
        amt_safe = 0.0
        try:
            amt_safe = float(pred["amount_safe_to_pay"])
            if amt_safe < 0:
                row_errors.append(f"amount_safe_to_pay is negative ({amt_safe}).")
        except ValueError:
            row_errors.append(f"amount_safe_to_pay is not a valid float ({pred['amount_safe_to_pay']}).")

        # 2. Enum validations
        status = pred.get("affordability_status")
        if status not in VALID_STATUSES:
            row_errors.append(f"Invalid affordability_status '{status}'.")

        method = pred.get("recommended_payment_method")
        if method not in VALID_METHODS:
            row_errors.append(f"Invalid recommended_payment_method '{method}'.")

        # 3. Payment plan JSON validation & safety simulation
        plan_total = 0.0
        try:
            raw_plan = json.loads(pred.get("payment_plan", "[]"))
            if not isinstance(raw_plan, list):
                row_errors.append("payment_plan is not a JSON list.")
            else:
                from models.schemas import PaymentPlanItem
                plan_items = []
                for p_idx, item in enumerate(raw_plan):
                    if "date" not in item or "amount" not in item:
                        row_errors.append(f"payment_plan item {p_idx} missing date/amount.")
                    else:
                        plan_items.append(PaymentPlanItem(date=str(item["date"]), amount=float(item["amount"])))

                plan_total = round(sum(p.amount for p in plan_items), 2)

                # Payment plan sum assertions
                if status in {"AFFORDABLE_NOW", "AFFORDABLE_WITH_PLAN", "AFFORDABLE_LATER"}:
                    if abs(plan_total - req_cost) > 0.01:
                        row_errors.append(
                            f"Plan total (${plan_total:.2f}) does not match requested total cost (${req_cost:.2f})."
                        )
                elif status == "NOT_AFFORDABLE":
                    if len(plan_items) > 0:
                        row_errors.append("NOT_AFFORDABLE prediction must have an empty payment_plan.")

                # Perform deterministic cashflow safety check
                if u_id in profiles:
                    profile = profiles[u_id]
                    is_safe, lowest_bal, min_headroom = simulator.evaluate_payment_plan_safety(
                        profile, req["request_date"], plan_items
                    )
                    if not is_safe:
                        row_errors.append(
                            f"Safety constraint violation! Balance drops to ${lowest_bal:.2f} (Min headroom: ${min_headroom:.2f})."
                        )
        except Exception as e:
            row_errors.append(f"Failed to parse or evaluate payment_plan JSON: {e}")

        # 4. Spending changes JSON validation
        try:
            raw_spending = json.loads(pred.get("spending_changes_needed", "[]"))
            if not isinstance(raw_spending, list):
                row_errors.append("spending_changes_needed is not a JSON list.")
        except Exception as e:
            row_errors.append(f"Failed to parse spending_changes_needed JSON: {e}")

        # 5. Decision explanation validation
        explanation = pred.get("decision_explanation", "").strip()
        if not explanation:
            row_errors.append("Empty decision_explanation.")

        row_pass = len(row_errors) == 0
        if not row_pass:
            errors.extend([f"Request {req_id}: {err}" for err in row_errors])

        difference = round(abs(req_cost - plan_total), 2) if status != "NOT_AFFORDABLE" else 0.00

        row_results.append({
            "request_id": req_id,
            "requested_amount": req_cost,
            "safe_amount": amt_safe,
            "status": status,
            "payment_method": method,
            "plan_total": plan_total,
            "difference": difference,
            "validation": "PASS" if row_pass else "FAIL"
        })

    is_valid = len(errors) == 0
    return is_valid, errors, row_results
