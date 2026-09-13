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
from utils.export_submission import export_submission_zip, export_log_transcript

def run_pipeline(
    requests_csv_path: str = "dataset/requests.csv",
    profiles_json_path: str = "dataset/user_profiles.json",
    output_csv_path: str = "output.csv"
):
    print("Starting AI Financial Agent Pipeline...")
    print(f"  - Loading profiles from: {profiles_json_path}")
    print(f"  - Loading requests from: {requests_csv_path}")

    profiles = load_user_profiles(profiles_json_path)
    agent = FinancialAgent()

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

    decisions = []
    for req in requests:
        profile = profiles[req.user_id]
        decision = agent.evaluate_request(req, profile)
        decisions.append(decision)

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

    print(f"Successfully generated populated '{output_csv_path}' with {len(decisions)} predictions.\n")

    print("Running evaluation suite...")
    metrics = evaluate_predictions(requests_csv_path, output_csv_path, profiles_json_path)

    print("\nExporting HackerRank submission packages...")
    export_submission_zip("code.zip")
    export_log_transcript("log.txt")

    print("\nPipeline execution complete! All deliverables ready for HackerRank upload.")

if __name__ == "__main__":
    run_pipeline()
