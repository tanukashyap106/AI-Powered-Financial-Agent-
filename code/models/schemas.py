import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum

class AffordabilityStatus(str, Enum):
    AFFORDABLE_NOW = "AFFORDABLE_NOW"
    AFFORDABLE_WITH_PLAN = "AFFORDABLE_WITH_PLAN"
    AFFORDABLE_LATER = "AFFORDABLE_LATER"
    NOT_AFFORDABLE = "NOT_AFFORDABLE"

class RecommendedPaymentMethod(str, Enum):
    PAY_IN_FULL = "PAY_IN_FULL"
    INSTALLMENTS_3M = "INSTALLMENTS_3M"
    INSTALLMENTS_6M = "INSTALLMENTS_6M"
    PARTIAL_PAYMENT = "PARTIAL_PAYMENT"
    WAIT_FOR_INCOME = "WAIT_FOR_INCOME"
    DO_NOT_PROCEED = "DO_NOT_PROCEED"

@dataclass
class ExpenseItem:
    name: str
    amount: float
    due_day: int
    category: str = "General"
    flexible: bool = False

@dataclass
class PendingCommitment:
    name: str
    amount: float
    due_date: str
    category: str = "Pending"

@dataclass
class UserProfile:
    user_id: str
    name: str
    current_balance: float
    min_buffer_balance: float
    paycheck_amount: float
    pay_day_1: int
    pay_day_2: Optional[int] = None
    essential_expenses: List[ExpenseItem] = field(default_factory=list)
    recurring_subscriptions: List[ExpenseItem] = field(default_factory=list)
    pending_commitments: List[PendingCommitment] = field(default_factory=list)
    flexible_monthly_spending: float = 0.0

@dataclass
class FinancialRequest:
    request_id: str
    user_id: str
    request_date: str
    item_description: str
    item_category: str
    total_cost: float
    payment_options: List[str]
    user_prompt: str
    image_path: Optional[str] = None
    expected_status: Optional[str] = None

@dataclass
class PaymentPlanItem:
    date: str
    amount: float

@dataclass
class SpendingChange:
    category: str
    reduction_amount: float

@dataclass
class AgentDecision:
    request_id: str
    user_id: str
    amount_safe_to_pay: float
    affordability_status: AffordabilityStatus
    recommended_payment_method: RecommendedPaymentMethod
    payment_plan: List[PaymentPlanItem]
    earliest_date_for_full_payment: str
    spending_changes_needed: List[SpendingChange]
    decision_explanation: str

    def to_csv_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "amount_safe_to_pay": round(self.amount_safe_to_pay, 2),
            "affordability_status": self.affordability_status.value,
            "recommended_payment_method": self.recommended_payment_method.value,
            "payment_plan": json.dumps([asdict(p) for p in self.payment_plan]),
            "earliest_date_for_full_payment": self.earliest_date_for_full_payment,
            "spending_changes_needed": json.dumps([asdict(s) for s in self.spending_changes_needed]),
            "decision_explanation": self.decision_explanation
        }
