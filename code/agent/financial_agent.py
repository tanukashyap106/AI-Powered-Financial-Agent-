from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from models.schemas import (
    FinancialRequest, UserProfile, AgentDecision,
    AffordabilityStatus, RecommendedPaymentMethod,
    PaymentPlanItem, SpendingChange
)
from engine.cashflow_simulator import CashflowSimulator
from parsers.multimodal_parser import MultimodalParser

@dataclass
class RequestTranscript:
    timestamp: str
    request_id: str
    user_id: str
    item_description: str
    total_cost: float
    user_prompt: str
    image_path: Optional[str]
    context: Dict[str, Any]
    steps: List[str]
    decision: AgentDecision

    def to_transcript_block(self) -> str:
        lines = [
            f"--- CHAT TRANSCRIPT: {self.request_id} (User: {self.user_id}) ---",
            f"Timestamp: {self.timestamp}",
            f"[USER PROMPT]: \"{self.user_prompt}\"",
            f"[ITEM OBLIGATION]: {self.item_description} (${self.total_cost:.2f})",
        ]
        if self.image_path:
            lines.append(f"[MULTIMODAL ATTACHMENT]: {self.image_path}")
            if self.context.get("media_text"):
                clean_txt = self.context['media_text'].replace('\n', ' ').strip()
                lines.append(f"[PARSED MEDIA CONTENT]: {clean_txt[:120]}...")
        lines.append("[ENGINE REASONING & CASHFLOW SIMULATION]:")
        for step in self.steps:
            lines.append(f"  - {step}")
        lines.extend([
            "[AGENT RESPONSE & RECOMMENDATION]:",
            f"  - Affordability Status          : {self.decision.affordability_status.value}",
            f"  - Recommended Payment Method    : {self.decision.recommended_payment_method.value}",
            f"  - Amount Safe to Pay Today      : ${self.decision.amount_safe_to_pay:.2f}",
            f"  - Earliest Full Payment Date    : {self.decision.earliest_date_for_full_payment}",
            f"  - Payment Plan                  : {self.decision.to_csv_dict()['payment_plan']}",
            f"  - Spending Changes Needed       : {self.decision.to_csv_dict()['spending_changes_needed']}",
            f"  - Decision Explanation          : {self.decision.decision_explanation}",
            "-" * 60
        ])
        return "\n".join(lines)

class FinancialAgent:
    """
    Personalized AI Financial Agent orchestrator.
    Determines maximum safe out-of-pocket payment, affordability status,
    safest payment method, installment plan, earliest full payment date,
    spending reduction recommendations, and human-readable explanation.
    """

    def __init__(self):
        self.simulator = CashflowSimulator(forecast_days=60)
        self.parser = MultimodalParser()

    def evaluate_request(self, request: FinancialRequest, profile: UserProfile) -> Tuple[AgentDecision, RequestTranscript]:
        eval_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context = self.parser.parse_request_context(request)
        req_dt = datetime.strptime(request.request_date, "%Y-%m-%d")
        steps = []

        max_safe_today = self.simulator.get_max_safe_pay_today(profile, request.request_date)
        steps.append(f"Max safe out-of-pocket payment today calculated: ${max_safe_today:.2f} (Current Balance: ${profile.current_balance:.2f}, Min Buffer: ${profile.min_buffer_balance:.2f})")

        # 1. Test Lump Sum Payment Today (PAY_IN_FULL)
        lump_plan = [PaymentPlanItem(date=request.request_date, amount=request.total_cost)]
        is_lump_safe, lump_min_bal, lump_min_headroom = self.simulator.evaluate_payment_plan_safety(
            profile, request.request_date, lump_plan
        )
        steps.append(f"Evaluated Lump Sum PAY_IN_FULL plan today (${request.total_cost:.2f}): is_safe={is_lump_safe}, min_balance=${lump_min_bal:.2f}, min_headroom=${lump_min_headroom:.2f}")

        available_opts = [opt.strip() for opt in request.payment_options]

        # Liquidity rule: If lump sum takes > 50% of available liquid balance and installment option exists,
        # prefer installment plan to protect liquidity reserve.
        prefer_installments = (
            request.total_cost > (profile.current_balance * 0.5) and
            any(opt in available_opts for opt in ["INSTALLMENTS_3M", "INSTALLMENTS_6M"])
        )
        if prefer_installments:
            steps.append("Item total cost > 50% of liquid balance and installment options exist -> liquidity rule activated: prefer installment plan.")

        if is_lump_safe and not prefer_installments:
            decision = AgentDecision(
                request_id=request.request_id,
                user_id=request.user_id,
                amount_safe_to_pay=min(request.total_cost, max_safe_today),
                affordability_status=AffordabilityStatus.AFFORDABLE_NOW,
                recommended_payment_method=RecommendedPaymentMethod.PAY_IN_FULL,
                payment_plan=lump_plan,
                earliest_date_for_full_payment=request.request_date,
                spending_changes_needed=[],
                decision_explanation=(
                    f"Affordable now! Paying ${request.total_cost:.2f} in full today leaves a healthy "
                    f"minimum balance cushion of at least ${lump_min_headroom + profile.min_buffer_balance:.2f} "
                    f"(above your ${profile.min_buffer_balance:.2f} required reserve) throughout the 60-day forecast."
                )
            )
            transcript = RequestTranscript(
                timestamp=eval_timestamp, request_id=request.request_id, user_id=request.user_id,
                item_description=request.item_description, total_cost=request.total_cost,
                user_prompt=request.user_prompt, image_path=request.image_path, context=context,
                steps=steps, decision=decision
            )
            return decision, transcript

        # 2. Test Installment Payment Plans if available (with penny-exact sum matching total_cost)
        if "INSTALLMENTS_3M" in available_opts:
            base_m_amt = round(request.total_cost / 3.0, 2)
            plan_3m = []
            running_sum = 0.0
            for i in range(3):
                p_date = (req_dt + timedelta(days=i*30)).strftime("%Y-%m-%d")
                if i < 2:
                    amt = base_m_amt
                    running_sum += amt
                else:
                    amt = round(request.total_cost - running_sum, 2)
                plan_3m.append(PaymentPlanItem(date=p_date, amount=amt))

            is_3m_safe, min_bal_3m, headroom_3m = self.simulator.evaluate_payment_plan_safety(
                profile, request.request_date, plan_3m
            )
            steps.append(f"Evaluated INSTALLMENTS_3M plan (3 payments totaling ${request.total_cost:.2f}): is_safe={is_3m_safe}, min_headroom=${headroom_3m:.2f}")

            if is_3m_safe:
                earliest_full_date = self.simulator.find_earliest_safe_full_payment_date(
                    profile, request.request_date, request.total_cost
                )
                steps.append(f"Earliest safe date for full lump sum payment: {earliest_full_date}")
                decision = AgentDecision(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    amount_safe_to_pay=min(base_m_amt, max_safe_today),
                    affordability_status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                    recommended_payment_method=RecommendedPaymentMethod.INSTALLMENTS_3M,
                    payment_plan=plan_3m,
                    earliest_date_for_full_payment=earliest_full_date,
                    spending_changes_needed=[],
                    decision_explanation=(
                        f"Affordable with plan. Splitting ${request.total_cost:.2f} into 3 monthly installments "
                        f"keeps your account balance safe with a minimum cushion of ${headroom_3m + profile.min_buffer_balance:.2f}."
                    )
                )
                transcript = RequestTranscript(
                    timestamp=eval_timestamp, request_id=request.request_id, user_id=request.user_id,
                    item_description=request.item_description, total_cost=request.total_cost,
                    user_prompt=request.user_prompt, image_path=request.image_path, context=context,
                    steps=steps, decision=decision
                )
                return decision, transcript

        if "INSTALLMENTS_6M" in available_opts:
            base_m_amt = round(request.total_cost / 6.0, 2)
            plan_6m = []
            running_sum = 0.0
            for i in range(6):
                p_date = (req_dt + timedelta(days=i*30)).strftime("%Y-%m-%d")
                if i < 5:
                    amt = base_m_amt
                    running_sum += amt
                else:
                    amt = round(request.total_cost - running_sum, 2)
                plan_6m.append(PaymentPlanItem(date=p_date, amount=amt))

            is_6m_safe, min_bal_6m, headroom_6m = self.simulator.evaluate_payment_plan_safety(
                profile, request.request_date, plan_6m
            )
            steps.append(f"Evaluated INSTALLMENTS_6M plan (6 payments totaling ${request.total_cost:.2f}): is_safe={is_6m_safe}, min_headroom=${headroom_6m:.2f}")

            if is_6m_safe:
                earliest_full_date = self.simulator.find_earliest_safe_full_payment_date(
                    profile, request.request_date, request.total_cost
                )
                steps.append(f"Earliest safe date for full lump sum payment: {earliest_full_date}")
                decision = AgentDecision(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    amount_safe_to_pay=min(base_m_amt, max_safe_today),
                    affordability_status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                    recommended_payment_method=RecommendedPaymentMethod.INSTALLMENTS_6M,
                    payment_plan=plan_6m,
                    earliest_date_for_full_payment=earliest_full_date,
                    spending_changes_needed=[],
                    decision_explanation=(
                        f"Affordable with plan. Splitting ${request.total_cost:.2f} into 6 monthly payments "
                        f"protects your liquidity reserve and maintains your minimum cushion."
                    )
                )
                transcript = RequestTranscript(
                    timestamp=eval_timestamp, request_id=request.request_id, user_id=request.user_id,
                    item_description=request.item_description, total_cost=request.total_cost,
                    user_prompt=request.user_prompt, image_path=request.image_path, context=context,
                    steps=steps, decision=decision
                )
                return decision, transcript

        # 3. If lump sum is safe (even if prefer_installments was true, but no installment was safe), return PAY_IN_FULL
        if is_lump_safe:
            decision = AgentDecision(
                request_id=request.request_id,
                user_id=request.user_id,
                amount_safe_to_pay=min(request.total_cost, max_safe_today),
                affordability_status=AffordabilityStatus.AFFORDABLE_NOW,
                recommended_payment_method=RecommendedPaymentMethod.PAY_IN_FULL,
                payment_plan=lump_plan,
                earliest_date_for_full_payment=request.request_date,
                spending_changes_needed=[],
                decision_explanation=(
                    f"Affordable now! Paying ${request.total_cost:.2f} in full today leaves a healthy "
                    f"minimum balance cushion of at least ${lump_min_headroom + profile.min_buffer_balance:.2f}."
                )
            )
            transcript = RequestTranscript(
                timestamp=eval_timestamp, request_id=request.request_id, user_id=request.user_id,
                item_description=request.item_description, total_cost=request.total_cost,
                user_prompt=request.user_prompt, image_path=request.image_path, context=context,
                steps=steps, decision=decision
            )
            return decision, transcript

        # 4. Earliest Date for Full Lump Sum Payment
        earliest_full_date = self.simulator.find_earliest_safe_full_payment_date(
            profile, request.request_date, request.total_cost
        )
        steps.append(f"Evaluated earliest safe full lump-sum payment date across 60-day horizon: {earliest_full_date}")
        
        if earliest_full_date != "N/A":
            earliest_dt = datetime.strptime(earliest_full_date, "%Y-%m-%d")
            if earliest_dt <= req_dt + timedelta(days=60):
                later_plan = [PaymentPlanItem(date=earliest_full_date, amount=request.total_cost)]
                is_later_safe, _, _ = self.simulator.evaluate_payment_plan_safety(
                    profile, request.request_date, later_plan, spending_reduction_pct=0.0
                )
                spending_changes = []
                if not is_later_safe and profile.flexible_monthly_spending > 50.0:
                    rec_cut = min(100.0, round(profile.flexible_monthly_spending * 0.4, 2))
                    spending_changes = [SpendingChange(category="Dining & Subscriptions", reduction_amount=rec_cut)]

                decision = AgentDecision(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    amount_safe_to_pay=max_safe_today,
                    affordability_status=AffordabilityStatus.AFFORDABLE_LATER,
                    recommended_payment_method=RecommendedPaymentMethod.WAIT_FOR_INCOME,
                    payment_plan=later_plan,
                    earliest_date_for_full_payment=earliest_full_date,
                    spending_changes_needed=spending_changes,
                    decision_explanation=(
                        f"Affordable later. Purchasing today would violate your ${profile.min_buffer_balance:.2f} minimum buffer. "
                        f"Wait until {earliest_full_date} after your upcoming paycheck to safely complete full payment."
                    )
                )
                transcript = RequestTranscript(
                    timestamp=eval_timestamp, request_id=request.request_id, user_id=request.user_id,
                    item_description=request.item_description, total_cost=request.total_cost,
                    user_prompt=request.user_prompt, image_path=request.image_path, context=context,
                    steps=steps, decision=decision
                )
                return decision, transcript

        # 5. Not Affordable
        decision = AgentDecision(
            request_id=request.request_id,
            user_id=request.user_id,
            amount_safe_to_pay=max_safe_today,
            affordability_status=AffordabilityStatus.NOT_AFFORDABLE,
            recommended_payment_method=RecommendedPaymentMethod.DO_NOT_PROCEED,
            payment_plan=[],
            earliest_date_for_full_payment="N/A",
            spending_changes_needed=[
                SpendingChange(category="Flexible Spending", reduction_amount=round(profile.flexible_monthly_spending * 0.5, 2))
            ] if profile.flexible_monthly_spending > 0 else [],
            decision_explanation=(
                f"Not affordable. Cost of ${request.total_cost:.2f} exceeds your cashflow capacity and buffer reserve "
                f"across the forecast horizon. We recommend postponing this expense."
            )
        )
        transcript = RequestTranscript(
            timestamp=eval_timestamp, request_id=request.request_id, user_id=request.user_id,
            item_description=request.item_description, total_cost=request.total_cost,
            user_prompt=request.user_prompt, image_path=request.image_path, context=context,
            steps=steps, decision=decision
        )
        return decision, transcript
