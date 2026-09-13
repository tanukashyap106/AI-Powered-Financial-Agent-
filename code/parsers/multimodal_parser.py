import os
import re
from typing import Dict, Any, Optional
from models.schemas import FinancialRequest

class MultimodalParser:
    """
    Parses prompt text and associated media metadata (invoices, paystubs, doctor estimates, screenshots)
    to extract contextual financial constraints, promotional installment terms, and urgency indicators.
    """

    def parse_request_context(self, request: FinancialRequest) -> Dict[str, Any]:
        context = {
            "has_media": False,
            "media_text": "",
            "promo_installment_3m": False,
            "promo_installment_6m": False,
            "urgency": "NORMAL",
            "extracted_notes": []
        }

        if request.image_path:
            txt_path = request.image_path.rsplit('.', 1)[0] + ".txt"
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, "r", encoding="utf-8") as f:
                        media_content = f.read()
                        context["has_media"] = True
                        context["media_text"] = media_content

                        if "0% APR 3-month" in media_content or "3-month" in media_content:
                            context["promo_installment_3m"] = True
                        if "0% APR 6-month" in media_content or "6-month" in media_content:
                            context["promo_installment_6m"] = True
                        if "doctor" in media_content.lower() or "medical" in media_content.lower():
                            context["urgency"] = "HIGH"
                except Exception as e:
                    context["extracted_notes"].append(f"Error reading media text: {str(e)}")

        prompt_lower = request.user_prompt.lower()
        if any(w in prompt_lower for w in ["urgent", "broke", "doctor", "need", "essential"]):
            context["urgency"] = "HIGH"
        if any(w in prompt_lower for w in ["split", "installments", "monthly"]):
            context["user_open_to_installments"] = True

        return context
