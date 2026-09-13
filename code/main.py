import csv
import json
import os
import sys

# Add code directory to python sys.path
code_dir = os.path.dirname(os.path.abspath(__file__))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from models.schemas import FinancialRequest
from agent.financial_agent import FinancialAgent
from eval.evaluate import load_user_profiles, evaluate_predictions
from eval.validator import validate_output_csv
from utils.export_submission import export_submission_zip, export_log_transcript

def run_pipeline(
    requests_csv_path: str = "dataset/requests.csv",
    profiles_json_path: str = "dataset/user_profiles.json",
    output_csv_path: str = "output.csv"
):
    print("Starting AI Financial Agent Pipeline...\n")
    print("  * Loading profiles...")
    profiles = load_user_profiles(profiles_json_path)

    print("  * Loading requests...")
    requests: list[FinancialRequest] = []
    with open(requests_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            opts = [o.strip() for o in row["payment_options"].split(",") if o.strip()]
            req = FinancialRequest(
                request_id=row["request_id"],
                user_id=row["user_id"],
                request_date=row["request_date"],
                item_description=row["item_description"],
                item_category=row["item_category"],
                total_cost=float(row["total_cost"]),
                payment_options=opts,
                user_prompt=row["user_prompt"],
                image_path=row.get("image_path"),
                expected_status=row.get("expected_status")
            )
            requests.append(req)

    print("  * Processing messages/images...")
    print("  * Running financial forecast...")
    print("  * Generating payment recommendations & logging chat transcripts...\n")

    agent = FinancialAgent()
    decisions = []
    transcripts = []
    for req in requests:
        profile = profiles[req.user_id]
        decision, transcript = agent.evaluate_request(req, profile)
        decisions.append(decision)
        transcripts.append(transcript)

    fieldnames = [
        "request_id", "user_id", "amount_safe_to_pay", "affordability_status",
        "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment",
        "spending_changes_needed", "decision_explanation"
    ]

    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in decisions:
            writer.writerow(d.to_csv_dict())

    print(f"Successfully generated {output_csv_path} with {len(decisions)} predictions.\n")

    print("Validating generated predictions against problem specification...")
    is_valid, val_errors, row_results = validate_output_csv(output_csv_path, requests_csv_path, profiles_json_path)
    
    print("\n-----------------------------------------------------------------------------")
    print(f"{'request_id':<11} | {'requested_amount':<16} | {'payment_plan_total':<18} | {'difference':<10} | {'validation':<10}")
    print("-----------------------------------------------------------------------------")
    for r in row_results:
        print(f"{r['request_id']:<11} | ${r['requested_amount']:<15.2f} | ${r['plan_total']:<17.2f} | ${r['difference']:<9.2f} | {r['validation']:<10}")
    print("-----------------------------------------------------------------------------\n")

    if not is_valid:
        print("[VALIDATION FAILURE] Validation errors detected:")
        for err in val_errors:
            print(f"  - {err}")
    else:
        print("  - output.csv passed all schema, structure, payment plan sum, and safety validations.\n")

    print("Running evaluation suite...\n")
    metrics = evaluate_predictions(requests_csv_path, output_csv_path, profiles_json_path)

    print("\nExporting HackerRank submission packages...")
    export_submission_zip("code.zip")
    export_log_transcript(
        log_path="log.txt",
        metrics=metrics,
        transcripts=transcripts,
        requests_csv_path=requests_csv_path,
        forecast_horizon="60 Days",
        validation_passed=is_valid,
        validation_errors=val_errors if not is_valid else None
    )

    if is_valid:
        print("\nPipeline execution complete!")
    else:
        print("\nPipeline execution completed with validation warnings/errors.")

if __name__ == "__main__":
    run_pipeline()
