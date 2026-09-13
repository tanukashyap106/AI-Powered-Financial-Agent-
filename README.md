# "Buy or Wait?" AI-Powered Financial Agent

An intelligent, multi-modal financial decision agent built to evaluate individual purchase requests against personal cashflow forecasts, recurring obligations, and minimum safety reserves. The agent determines whether a user can safely afford a requested expense today, via a payment plan, at a future date after incoming salary, or not at all.

---

## 🌟 Key Features

* **Hybrid Architecture**: Combines a deterministic time-series cashflow engine with multi-modal context parsing (bills, invoices, doctor estimates, user prompts).
* **Hard Safety Buffer Constraint**: Enforces $B(t) \ge \text{MinBuffer}$ at every day $t$ throughout the **60-day forecast horizon**. Minimum reserves are strictly protected by the deterministic validator.
* **Penny-Exact Installment Plan Generation**: Generates 3-month (`INSTALLMENTS_3M`) and 6-month (`INSTALLMENTS_6M`) payment plans with exact cent balancing (`sum(payment_plan) == requested_cost`).
* **Liquidity Protection**: Automatically recommends installment plans over large lump-sum payments when a purchase exceeds 50% of liquid reserves.
* **Automated Validation & Evaluation Suite**: Performs independent schema verification, numeric range checks, cashflow safety simulations, and dynamic metric calculations.
* **Transcript Logging**: Generates execution transcript logs (`log.txt`) recording every user prompt, parsed attachment, cashflow simulation step, and decision output.

---

## 📁 Repository Structure

```text
.
├── code/
│   ├── agent/
│   │   └── financial_agent.py      # Core agent orchestrator & decision logic
│   ├── engine/
│   │   └── cashflow_simulator.py   # Deterministic 60-day time-series cashflow simulator
│   ├── eval/
│   │   ├── evaluate.py             # Accuracy, safety compliance, & violation metrics evaluator
│   │   └── validator.py            # Independent schema, numeric, & cashflow safety validator
│   ├── models/
│   │   └── schemas.py              # Data models (UserProfile, FinancialRequest, AgentDecision, Enums)
│   ├── parsers/
│   │   └── multimodal_parser.py    # Multi-modal media & user prompt context parser
│   ├── utils/
│   │   └── export_submission.py    # Submission artifact exporter (code.zip & transcript log.txt)
│   └── main.py                     # Entrypoint module inside code/
├── dataset/
│   ├── requests.csv                # Financial evaluation requests input
│   ├── user_profiles.json          # Financial user profile data (balances, paychecks, expenses)
│   └── media/                      # OCR, document notes, and image attachments
├── main.py                         # Root pipeline launcher script
├── problem_statement.md            # HackerRank problem specification
├── output.csv                      # Required pipeline output CSV predictions
├── log.txt                         # Execution transcript log
└── code.zip                        # HackerRank code submission archive
```

---

## 📊 Required Output Schema (`output.csv`)

| Column Name | Type | Description |
|---|---|---|
| `request_id` | string | Unique identifier for the financial request |
| `user_id` | string | Unique identifier for the user |
| `amount_safe_to_pay` | float | Maximum safe out-of-pocket amount user can pay today |
| `affordability_status` | enum | `AFFORDABLE_NOW`, `AFFORDABLE_WITH_PLAN`, `AFFORDABLE_LATER`, `NOT_AFFORDABLE` |
| `recommended_payment_method` | enum | `PAY_IN_FULL`, `INSTALLMENTS_3M`, `INSTALLMENTS_6M`, `PARTIAL_PAYMENT`, `WAIT_FOR_INCOME`, `DO_NOT_PROCEED` |
| `payment_plan` | JSON string | List of payments `[{"date": "YYYY-MM-DD", "amount": 150.0}]` |
| `earliest_date_for_full_payment` | string | ISO date `YYYY-MM-DD` when full lump-sum payment is safe (`N/A` if unavailable) |
| `spending_changes_needed` | JSON string | List of budget reductions `[{"category": "Dining Out", "reduction_amount": 75.0}]` |
| `decision_explanation` | string | Short narrative explaining recommendation, cashflow metrics, & risk analysis |

---

## 💡 Status Definitions

- **`AFFORDABLE_NOW`**: Can safely pay the full lump-sum cost today while maintaining the minimum buffer reserve throughout the forecast horizon.
- **`AFFORDABLE_WITH_PLAN`**: Cannot safely pay in full today, but can afford via an available 3-month or 6-month installment plan starting today.
- **`AFFORDABLE_LATER`**: Cannot afford today even with installments, but can afford full payment on `earliest_date_for_full_payment` after an incoming paycheck without budget cuts.
- **`NOT_AFFORDABLE`**: Exceeds financial capacity across the forecast period even after reasonable flexible spending adjustments.

---

## 🚀 How to Run the Complete Pipeline

Run the complete pipeline, perform output validation, run the evaluation suite, and export submission packages using:

```bash
python main.py
```

### Pipeline Workflow:
1. **Loads Profile & Request Data**: Parses `dataset/user_profiles.json` and `dataset/requests.csv`.
2. **Runs Multi-Modal Parsing & Cashflow Forecast**: Simulates daily cash balance $B(t)$ over 60 days.
3. **Generates Predictions**: Outputs predictions to `output.csv`.
4. **Executes Schema & Safety Validator**: Verifies header order, numeric types, JSON structures, plan sums, and $B(t) \ge \text{MinBuffer}$ constraints.
5. **Runs Evaluation Suite**: Calculates status accuracy, safety compliance rate, and safety violation counts dynamically.
6. **Exports Deliverables**: Creates `code.zip` (packaged source codebase) and `log.txt` (execution summary & detailed chat transcripts).

---

## 📦 Submission Deliverables

- **`code.zip`**: Packaged `code/` directory containing source files (`main.py`, `agent/`, `engine/`, `eval/`, `models/`, `parsers/`, `utils/`). Excludes `dataset/`, `venv`, node modules, and build artifacts.
- **`output.csv`**: Predictions output matching the required schema.
- **`log.txt`**: Execution transcript log containing model metadata, forecast settings, evaluation summary metrics, and per-request agent interaction logs.