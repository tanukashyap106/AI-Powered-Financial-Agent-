from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models.schemas import (
    FinancialRequest, UserProfile, AgentDecision,
    AffordabilityStatus, RecommendedPaymentMethod,
    PaymentPlanItem, SpendingChange
)
from engine.cashflow_simulator import CashflowSimulator
from parsers.multimodal_parser import MultimodalParser

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

    def evaluate_request(self, request: FinancialRequest, profile: UserProfile) -> AgentDecision:
        context = self.parser.parse_request_context(request)
        req_dt = datetime.strptime(request.request_date, "%Y-%m-%d")

        max_safe_today = self.simulator.get_max_safe_pay_today(profile, request.request_date)

        # 1. Test Lump Sum Payment Today (PAY_IN_FULL)
        lump_plan = [PaymentPlanItem(date=request.request_date, amount=request.total_cost)]
        is_lump_safe, lump_min_bal, lump_min_headroom = self.simulator.evaluate_payment_plan_safety(
            profile, request.request_date, lump_plan
        )

        available_opts = [opt.strip() for opt in request.payment_options]

        # Liquidity rule: If lump sum takes > 50% of available liquid balance and installment option exists,
        # prefer installment plan to protect liquidity reserve.
        prefer_installments = (
            request.total_cost > (profile.current_balance * 0.5) and
            any(opt in available_opts for opt in ["INSTALLMENTS_3M", "INSTALLMENTS_6M"])
        )

        if is_lump_safe and not prefer_installments:
            return AgentDecision(
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

        # 2. Test Installment Payment Plans if available
        if "INSTALLMENTS_3M" in available_opts:
            m_amt = round(request.total_cost / 3.0, 2)
            plan_3m = [
                PaymentPlanItem(date=(req_dt + timedelta(days=i*30)).strftime("%Y-%m-%d"), amount=m_amt)
                for i in range(3)
            ]
            is_3m_safe, _, headroom_3m = self.simulator.evaluate_payment_plan_safety(
                profile, request.request_date, plan_3m
            )
            if is_3m_safe:
                earliest_full_date = self.simulator.find_earliest_safe_full_payment_date(
                    profile, request.request_date, request.total_cost
                )
                return AgentDecision(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    amount_safe_to_pay=min(m_amt, max_safe_today),
                    affordability_status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                    recommended_payment_method=RecommendedPaymentMethod.INSTALLMENTS_3M,
                    payment_plan=plan_3m,
                    earliest_date_for_full_payment=earliest_full_date,
                    spending_changes_needed=[],
                    decision_explanation=(
                        f"Affordable with plan. Splitting ${request.total_cost:.2f} into 3 monthly installments "
                        f"of ${m_amt:.2f} keeps your account balance safe with a minimum cushion of ${headroom_3m + profile.min_buffer_balance:.2f}."
                    )
                )

        if "INSTALLMENTS_6M" in available_opts:
            m_amt = round(request.total_cost / 6.0, 2)
            plan_6m = [
                PaymentPlanItem(date=(req_dt + timedelta(days=i*30)).strftime("%Y-%m-%d"), amount=m_amt)
                for i in range(6)
            ]
            is_6m_safe, _, headroom_6m = self.simulator.evaluate_payment_plan_safety(
                profile, request.request_date, plan_6m
            )
            if is_6m_safe:
                earliest_full_date = self.simulator.find_earliest_safe_full_payment_date(
                    profile, request.request_date, request.total_cost
                )
                return AgentDecision(
                    request_id=request.request_id,
                    user_id=request.user_id,
                    amount_safe_to_pay=min(m_amt, max_safe_today),
                    affordability_status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                    recommended_payment_method=RecommendedPaymentMethod.INSTALLMENTS_6M,
                    payment_plan=plan_6m,
                    earliest_date_for_full_payment=earliest_full_date,
                    spending_changes_needed=[],
                    decision_explanation=(
                        f"Affordable with plan. Splitting ${request.total_cost:.2f} into 6 monthly payments "
                        f"of ${m_amt:.2f} protects your liquidity reserve and maintains your minimum cushion."
                    )
                )

        # 3. If lump sum is safe (even if prefer_installments was true, but no installment was safe), return PAY_IN_FULL
        if is_lump_safe:
            return AgentDecision(
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

        # 4. Flexible spending reduction check
        if profile.flexible_monthly_spending > 50.0:
            rec_cut = min(100.0, round(profile.flexible_monthly_spending * 0.4, 2))
            spending_changes = [SpendingChange(category="Dining & Subscriptions", reduction_amount=rec_cut)]
        else:
            spending_changes = []

        # 5. Earliest Date for Full Lump Sum Payment
        earliest_full_date = self.simulator.find_earliest_safe_full_payment_date(
            profile, request.request_date, request.total_cost
        )
        
        earliest_dt = datetime.strptime(earliest_full_date, "%Y-%m-%d")
        if earliest_dt <= req_dt + timedelta(days=45):
            later_plan = [PaymentPlanItem(date=earliest_full_date, amount=request.total_cost)]
            return AgentDecision(
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

        # 6. Not Affordable
        return AgentDecision(
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
