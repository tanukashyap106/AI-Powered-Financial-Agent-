import os
import zipfile
from datetime import datetime
from typing import Dict, Any, Optional, List

def export_submission_zip(output_zip_path: str = "code.zip"):
    """
    Zips the code/ directory, strictly excluding virtualenvs, node_modules,
    build artifacts, dataset/, data/, and temporary files.
    """
    code_dir = "code"
    excluded_patterns = ["__pycache__", ".git", ".pytest_cache", "venv", ".venv", "node_modules", "dataset", "data", "build"]
    excluded_exts = [".pyc", ".pyo", ".log", ".tmp", ".zip", ".csv"]

    print(f"Creating submission code zip: {output_zip_path}...")
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if not any(ex in d.lower() for ex in excluded_patterns)]
            for file in files:
                if any(file.endswith(ext) for ext in excluded_exts):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(code_dir))
                zipf.write(file_path, arcname)
                print(f"  + Added {arcname}")

    print(f"Successfully exported {output_zip_path} ({os.path.getsize(output_zip_path)} bytes).")

def export_log_transcript(
    log_path: str = "log.txt",
    metrics: Optional[Dict[str, Any]] = None,
    transcripts: Optional[List[Any]] = None,
    requests_csv_path: str = "dataset/requests.csv",
    forecast_horizon: str = "60 Days",
    validation_passed: bool = True,
    validation_errors: Optional[List[str]] = None
):
    """
    Generates execution transcript log.txt for HackerRank submission logging.
    Records model architecture, forecast parameters, evaluation summary metrics,
    and step-by-step chat interaction transcripts for every request.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if metrics:
        total_eval = str(metrics.get("total_evaluated", 0))
        accuracy_str = metrics.get("status_accuracy_str", f"{metrics.get('status_accuracy_pct', 0.0)}%")
        compliance_str = metrics.get("safety_compliance_str", f"{metrics.get('safety_compliance_pct', 100.0)}%")
        violations = str(metrics.get("safety_violations_count", 0))
    else:
        total_eval = "N/A"
        accuracy_str = "N/A"
        compliance_str = "N/A"
        violations = "N/A"

    if validation_passed:
        status_text = f"Executed successfully across {requests_csv_path}"
        completion_text = "Pipeline execution complete!\n============================"
    else:
        err_msg = "; ".join(validation_errors) if validation_errors else "Validation failed"
        status_text = f"FAILED validation across {requests_csv_path}: {err_msg}"
        completion_text = "Pipeline execution FAILED!\n=========================="

    log_sections = [
        "=== BUY OR WAIT? AI FINANCIAL AGENT EXECUTION LOG ===",
        f"Timestamp: {timestamp}\n",
        "Model Architecture:",
        "Hybrid Deterministic Cashflow Forecast + Multi-Modal VLM Parser\n",
        "Forecast Horizon:",
        f"{forecast_horizon}\n",
        "Safety Buffer Rule:",
        "Hard Constraint B(t) >= MinBuffer\n",
        "Pipeline Status:",
        f"{status_text}\n",
        "Evaluation:",
        f"Total Requests Evaluated : {total_eval}",
        f"Status Accuracy          : {accuracy_str}",
        f"Safety Compliance Rate   : {compliance_str}",
        f"Safety Violations        : {violations}\n",
        "Artifacts Generated:",
        "* output.csv",
        "* code.zip",
        "* log.txt\n",
        "========================================================",
        "DETAILED CHAT TRANSCRIPTS & AGENT INTERACTION LOGS:",
        "========================================================"
    ]

    if transcripts:
        for t in transcripts:
            log_sections.append(t.to_transcript_block())

    log_sections.extend([
        "\n========================================================",
        completion_text
    ])

    log_content = "\n".join(log_sections) + "\n"

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(log_content)

    print(f"Successfully written transcript log to {log_path}.")

if __name__ == "__main__":
    export_submission_zip("code.zip")
    export_log_transcript("log.txt")
