import csv
import json
from typing import Dict, Any, List
from models.schemas import UserProfile, ExpenseItem, PendingCommitment
from engine.cashflow_simulator import CashflowSimulator

def load_user_profiles(json_path: str) -> Dict[str, UserProfile]:
    with open(json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    profiles = {}
    for u_id, u_data in raw_data.items():
        essentials = [ExpenseItem(**item) for item in u_data.get("essential_expenses", [])]
        subs = [ExpenseItem(**item) for item in u_data.get("recurring_subscriptions", [])]
        pends = [PendingCommitment(**item) for item in u_data.get("pending_commitments", [])]

        profiles[u_id] = UserProfile(
            user_id=u_id,
            name=u_data["name"],
            current_balance=u_data["current_balance"],
            min_buffer_balance=u_data["min_buffer_balance"],
            paycheck_amount=u_data["paycheck_amount"],
            pay_day_1=u_data["pay_day_1"],
            pay_day_2=u_data.get("pay_day_2"),
            essential_expenses=essentials,
            recurring_subscriptions=subs,
            pending_commitments=pends,
            flexible_monthly_spending=u_data.get("flexible_monthly_spending", 0.0)
        )
    return profiles

def evaluate_predictions(requests_csv: str, output_csv: str, profiles_json: str) -> Dict[str, Any]:
    profiles = load_user_profiles(profiles_json)
    simulator = CashflowSimulator(forecast_days=60)

    requests_dict = {}
    with open(requests_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            requests_dict[row["request_id"]] = row

    preds_dict = {}
    with open(output_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            preds_dict[row["request_id"]] = row

    total_count = 0
    correct_status_count = 0
    safety_violations = 0

    print("==================================================")
    print("      BUY OR WAIT? AGENT EVALUATION REPORT        ")
    print("==================================================")

    for req_id, req in requests_dict.items():
        if req_id not in preds_dict:
            continue

        total_count += 1
        pred = preds_dict[req_id]
        expected_status = req.get("expected_status")
        u_id = req["user_id"]
        profile = profiles[u_id]

        status_match = False
        if expected_status:
            if pred["affordability_status"] == expected_status:
                correct_status_count += 1
                status_match = True

        try:
            raw_plan = json.loads(pred["payment_plan"])
            from models.schemas import PaymentPlanItem
            plan_items = [PaymentPlanItem(**item) for item in raw_plan]
            is_safe, lowest_bal, min_headroom = simulator.evaluate_payment_plan_safety(
                profile, req["request_date"], plan_items
            )
            if not is_safe:
                safety_violations += 1
                print(f"[SAFETY VIOLATION] Request {req_id}: Min headroom reached = ${min_headroom:.2f}")
        except Exception as e:
            print(f"[ERROR] Failed safety simulation for {req_id}: {e}")

        print(f"Request: {req_id} | User: {u_id} | Item: {req['item_description']} (${req['total_cost']})")
        print(f"  - Status: {pred['affordability_status']} (Expected: {expected_status}) [{'MATCH' if status_match else 'DIFF'}]")
        print(f"  - Recommended Method: {pred['recommended_payment_method']}")
        print(f"  - Amount Safe Today: ${pred['amount_safe_to_pay']}")
        print(f"  - Earliest Full Payment Date: {pred['earliest_date_for_full_payment']}")
        print(f"  - Explanation: {pred['decision_explanation'][:90]}...")
        print("-" * 50)

    accuracy = (correct_status_count / total_count * 100.0) if total_count > 0 else 0.0
    violation_rate = (safety_violations / total_count * 100.0) if total_count > 0 else 0.0

    metrics = {
        "total_evaluated": total_count,
        "correct_status_count": correct_status_count,
        "status_accuracy_pct": round(accuracy, 2),
        "safety_violations_count": safety_violations,
        "safety_violation_rate_pct": round(violation_rate, 2),
        "safety_compliance_pct": round(100.0 - violation_rate, 2)
    }

    print("\nEVALUATION SUMMARY METRICS:")
    print(f"  - Total Requests Evaluated : {metrics['total_evaluated']}")
    print(f"  - Status Accuracy          : {metrics['status_accuracy_pct']}%")
    print(f"  - Safety Compliance Rate   : {metrics['safety_compliance_pct']}%")
    print(f"  - Safety Violations        : {metrics['safety_violations_count']}")
    print("==================================================")

    return metrics

if __name__ == "__main__":
    evaluate_predictions("dataset/requests.csv", "output.csv", "dataset/user_profiles.json")
