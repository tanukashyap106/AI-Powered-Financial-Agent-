from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from models.schemas import UserProfile, PaymentPlanItem

class CashflowSimulator:
    """
    Time-series cashflow simulator over a 60-day forecast horizon.
    Calculates daily balances, buffer headroom, safe out-of-pocket pay amount today,
    installment plan feasibility, and earliest safe date for full payment.
    """

    def __init__(self, forecast_days: int = 60):
        self.forecast_days = forecast_days

    def simulate_base_cashflow(
        self, profile: UserProfile, start_date_str: str, spending_reduction_pct: float = 0.0
    ) -> List[Dict]:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        balance = profile.current_balance
        daily_log = []

        eff_flexible = profile.flexible_monthly_spending * (1.0 - spending_reduction_pct)
        daily_flex = eff_flexible / 30.0

        for day_offset in range(self.forecast_days):
            current_dt = start_dt + timedelta(days=day_offset)
            date_str = current_dt.strftime("%Y-%m-%d")
            day_of_month = current_dt.day

            income_today = 0.0
            essential_today = 0.0
            recurring_today = 0.0
            pending_today = 0.0

            if profile.pay_day_1 == day_of_month:
                income_today += profile.paycheck_amount
            if profile.pay_day_2 and profile.pay_day_2 == day_of_month:
                income_today += profile.paycheck_amount

            for exp in profile.essential_expenses:
                if exp.due_day == day_of_month:
                    essential_today += exp.amount

            for sub in profile.recurring_subscriptions:
                if sub.due_day == day_of_month:
                    recurring_today += sub.amount

            for pend in profile.pending_commitments:
                if pend.due_date == date_str:
                    pending_today += pend.amount

            balance += income_today - essential_today - recurring_today - pending_today - daily_flex
            headroom = balance - profile.min_buffer_balance

            daily_log.append({
                "day_offset": day_offset,
                "date": date_str,
                "balance": balance,
                "headroom": headroom,
                "income": income_today,
                "outflow": essential_today + recurring_today + pending_today + daily_flex
            })

        return daily_log

    def get_max_safe_pay_today(self, profile: UserProfile, start_date_str: str, spending_reduction_pct: float = 0.0) -> float:
        base_log = self.simulate_base_cashflow(profile, start_date_str, spending_reduction_pct)
        min_headroom = min(item["headroom"] for item in base_log)
        return max(0.0, min_headroom)

    def evaluate_payment_plan_safety(
        self, profile: UserProfile, start_date_str: str, plan: List[PaymentPlanItem], spending_reduction_pct: float = 0.0
    ) -> Tuple[bool, float, float]:
        plan_dict = {p.date: p.amount for p in plan}
        base_log = self.simulate_base_cashflow(profile, start_date_str, spending_reduction_pct)
        lowest_headroom = float("inf")
        lowest_balance = float("inf")

        for item in base_log:
            d_str = item["date"]
            cum_deduction = sum(amt for p_date, amt in plan_dict.items() if p_date <= d_str)
            adj_balance = item["balance"] - cum_deduction
            adj_headroom = adj_balance - profile.min_buffer_balance

            if adj_headroom < lowest_headroom:
                lowest_headroom = adj_headroom
            if adj_balance < lowest_balance:
                lowest_balance = adj_balance

        is_safe = lowest_headroom >= 0.0
        return is_safe, lowest_balance, lowest_headroom

    def find_earliest_safe_full_payment_date(
        self, profile: UserProfile, start_date_str: str, total_cost: float
    ) -> str:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        for offset in range(self.forecast_days):
            cand_dt = start_dt + timedelta(days=offset)
            cand_date_str = cand_dt.strftime("%Y-%m-%d")
            
            plan = [PaymentPlanItem(date=cand_date_str, amount=total_cost)]
            is_safe, _, _ = self.evaluate_payment_plan_safety(profile, start_date_str, plan)
            if is_safe:
                return cand_date_str

        return (start_dt + timedelta(days=60)).strftime("%Y-%m-%d")
