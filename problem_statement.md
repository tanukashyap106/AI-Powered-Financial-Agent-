# Problem Statement: "Buy or Wait?" AI Financial Agent

## Objective
Build an AI-powered financial agent that evaluates financial requests from users and decides whether a user can safely afford a requested expense ("Buy or Wait?").

The agent must consider:
- Current account balance
- Confirmed income and pay dates
- Essential recurring expenses (rent, groceries, healthcare, utilities)
- Flexible spending (dining, subscription services, entertainment)
- Pending payments & financial commitments
- Payment options (Pay in full, Installments, BNPL, Partial payment)
- Preferred minimum buffer balance (safety cushion reserve)
- Multi-modal evidence from attached text notes, messages, or images (paystubs, bills, receipts)

## Safety Rule
A recommendation is **SAFE** if and only if:
1. The user can complete the full payment plan.
2. The user covers all essential and committed expenses.
3. The user's account balance never drops below their preferred minimum buffer balance ($B(t) \ge \text{MinBuffer}$) at any day $t$ throughout the 60-day forecast horizon.

## Required Output Schema (`output.csv`)
The evaluation output CSV must contain the following fields:

| Column Name | Type | Description |
|---|---|---|
| `request_id` | string | Unique identifier for the financial request |
| `user_id` | string | Unique identifier for the user |
| `amount_safe_to_pay` | float | Maximum safe out-of-pocket amount user can pay today |
| `affordability_status` | enum | `AFFORDABLE_NOW`, `AFFORDABLE_WITH_PLAN`, `AFFORDABLE_LATER`, `NOT_AFFORDABLE` |
| `recommended_payment_method` | enum | `PAY_IN_FULL`, `INSTALLMENTS_3M`, `INSTALLMENTS_6M`, `PARTIAL_PAYMENT`, `WAIT_FOR_INCOME`, `DO_NOT_PROCEED` |
| `payment_plan` | JSON string | List of payments `[{"date": "YYYY-MM-DD", "amount": 150.0}]` |
| `earliest_date_for_full_payment` | string | ISO date `YYYY-MM-DD` when full lump-sum payment is safe |
| `spending_changes_needed` | JSON string | List of budget reductions `[{"category": "Dining Out", "reduction_amount": 75.0}]` |
| `decision_explanation` | string | Short narrative explaining the recommendation, cashflow metrics, and risk analysis |

## Status Definitions
- `AFFORDABLE_NOW`: Can safely pay the full cost today while maintaining the minimum buffer reserve.
- `AFFORDABLE_WITH_PLAN`: Cannot safely pay in full today, but can afford via an available installment/BNPL plan starting today.
- `AFFORDABLE_LATER`: Cannot afford today even with installments, but can afford full payment on `earliest_date_for_full_payment` after incoming salary/reductions.
- `NOT_AFFORDABLE`: Exceeds financial capacity across the forecast period even after reasonable flexible spending adjustments.

## Submission Package Requirements
1. **`code.zip`**: Archive of the `code/` directory. Exclude virtual environments, `node_modules`, `dataset/`, `data/`, and build artifacts.
2. **`output.csv`**: Populated predictions for `dataset/requests.csv`.
3. **`log.txt`**: Execution transcript log.
