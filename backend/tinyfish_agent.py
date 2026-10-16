"""TinyFish Web Agent Integration for Government Welfare Scheme Auto-Apply.

Automates online government portal application form-filling using TinyFish web agent API,
supporting both demo-safe dry-run mode and live portal submission.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional
from tinyfish import RunStatus, TinyFish

from models import Scheme, UserProfile

logger = logging.getLogger("gov_scheme_agent")


def is_dry_run() -> bool:
    """Returns True if TinyFish execution is in demo-safe dry-run mode (default: True).

    In dry-run mode, the agent navigates and fills all visible fields, takes a full-page
    screenshot, and stops BEFORE clicking final submit/register buttons.
    """
    val = os.getenv("TINYFISH_DRY_RUN", "true").strip().lower()
    return val in ("true", "1", "yes", "on")


# Initialize TinyFish client at module level with guard for missing key
_raw_key: Optional[str] = os.getenv("TINYFISH_API_KEY")
client: Optional[TinyFish] = (
    TinyFish(api_key=_raw_key)
    if _raw_key and _raw_key.strip() and _raw_key.strip() != "PASTE_YOUR_KEY_HERE"
    else None
)


def build_application_goal(profile: UserProfile, scheme: Scheme) -> str:
    """Builds natural-language goal instructing TinyFish web agent.

    Adapts instructions based on whether dry-run mode is active.
    """
    dry_run = is_dry_run()
    phone_display = profile.phone if profile.phone else "Not provided"

    base_citizen_info = (
        f"Citizen Profile Information:\n"
        f"- Full Legal Name: {profile.full_name}\n"
        f"- Age: {profile.age} years\n"
        f"- Gender: {profile.gender}\n"
        f"- Domicile / State: {profile.state}\n"
        f"- Gross Annual Household Income: ₹{profile.annual_income:,.2f}\n"
        f"- Caste Category: {profile.caste_category.upper()}\n"
        f"- Education Level: {profile.education_level.title()}\n"
        f"- Primary Occupation: {profile.occupation.replace('_', ' ').title()}\n"
        f"- Contact Email: {profile.email}\n"
        f"- Mobile Number: {phone_display}\n"
    )

    if dry_run:
        goal = (
            f"Navigate to {scheme.application_url} for the government scheme '{scheme.name}'.\n"
            f"{base_citizen_info}\n"
            f"CRITICAL DEMO INSTRUCTIONS (DRY RUN MODE):\n"
            f"1. Navigate to the online application/registration form.\n"
            f"2. Fill in every visible form field you can find using the citizen profile data above.\n"
            f"3. Take a full-page screenshot showing all the populated fields.\n"
            f"4. STOP IMMEDIATELY BEFORE clicking any final 'Submit', 'Apply', 'Register', or 'Proceed' button.\n"
            f"   DO NOT SUBMIT THE APPLICATION.\n"
            f"5. Return structured JSON output containing: status ('dry_run_completed'), screenshot_url, "
            f"fields_filled (list of field names filled), and form_url."
        )
    else:
        goal = (
            f"Navigate to {scheme.application_url} and apply for the government scheme '{scheme.name}'.\n"
            f"{base_citizen_info}\n"
            f"LIVE SUBMISSION INSTRUCTIONS:\n"
            f"1. Complete each input field matching the citizen attributes above.\n"
            f"2. Check and agree to standard terms and declarations if presented.\n"
            f"3. Submit the form if all required information is verified.\n"
            f"4. Capture and return the resulting application reference number / confirmation ID, "
            f"submission status, and confirmation message."
        )

    return goal


async def apply_to_scheme(
    profile: UserProfile, scheme: Scheme
) -> Dict[str, Any]:
    """Asynchronously executes TinyFish browser agent to apply for a scheme.

    Supports dry-run and live modes according to TINYFISH_DRY_RUN environment flag.

    Returns:
        dict:
            - If success (live): {"status": "submitted", "mode": "live", "run_id": str, "result": dict}
            - If success (dry_run): {"status": "dry_run", "mode": "dry_run", "run_id": str, "result": dict, "screenshot_url": str}
            - If failure: {"status": "failed", "mode": str, "run_id": Optional[str], "error": str}
    """
    dry_run = is_dry_run()
    mode_str = "dry_run" if dry_run else "live"

    if not scheme.application_url:
        return {
            "status": "failed",
            "mode": mode_str,
            "error": f"Scheme '{scheme.name}' does not have an online application URL.",
        }

    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key or api_key.strip() in ("", "PASTE_YOUR_KEY_HERE", "your_key_here"):
        return {
            "status": "failed",
            "mode": mode_str,
            "error": (
                "TINYFISH_API_KEY is not configured in backend/.env. "
                "Please configure a valid TinyFish API key to enable autonomous browser form submission."
            ),
        }

    try:
        active_client = client or TinyFish(api_key=api_key)
        goal = build_application_goal(profile, scheme)

        if dry_run:
            output_schema = {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "screenshot_url": {"type": "string"},
                    "fields_filled": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "form_url": {"type": "string"},
                },
                "required": ["status"],
            }
        else:
            output_schema = {
                "type": "object",
                "properties": {
                    "confirmation_id": {"type": "string"},
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["status"],
            }
        logger.info(
            f"Invoking TinyFish agent [mode={mode_str}] for profile #{profile.id} on scheme #{scheme.id} ({scheme.name})..."
        )

        # Run synchronous SDK call in thread pool to prevent blocking async event loop
        run_response = await asyncio.wait_for(
            asyncio.to_thread(
                active_client.agent.run,
                goal=goal,
                url=scheme.application_url,
                output_schema=output_schema,
            ),
            timeout=120,
        )

        if run_response.status == RunStatus.COMPLETED:
            res_data = getattr(run_response, "result", None) or {}
            screenshot = res_data.get("screenshot_url") if isinstance(res_data, dict) else None

            logger.info(
                f"TinyFish run {run_response.run_id} completed successfully in {mode_str} mode"
            )
            return {
                "status": "dry_run" if dry_run else "submitted",
                "mode": mode_str,
                "run_id": getattr(run_response, "run_id", None),
                "result": res_data,
                "screenshot_url": screenshot,
            }
        else:
            err_msg = getattr(run_response, "error", None) or f"Run status: {run_response.status}"
            logger.warning(f"TinyFish run {run_response.run_id} failed: {err_msg}")
            return {
                "status": "failed",
                "mode": mode_str,
                "run_id": getattr(run_response, "run_id", None),
                "error": str(err_msg),
            }

    except asyncio.TimeoutError:
        logger.error(f"TinyFish agent timed out after 120s for scheme {scheme.id}")
        return {
            "status": "failed",
            "mode": mode_str,
            "error": "Agent timed out after 120 seconds. Site may be slow or blocking automation.",
        }
    except Exception as exc:
        logger.error(f"Error executing TinyFish agent: {exc}")
        return {
            "status": "failed",
            "mode": mode_str,
            "error": str(exc),
        }