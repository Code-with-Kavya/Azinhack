"""LLM-assisted eligibility rules extractor using Google Gemini via LangChain.

Extracts structured demographic, economic, and occupational criteria
from free-form government scheme guidelines and notifications.
"""

import logging
import os
import re
from typing import Any, Dict, Optional
from schemas import EligibilityRules

logger = logging.getLogger("gov_scheme_agent")

EXTRACTION_SYSTEM_PROMPT = """You are an expert civic-tech policy analyst specializing in Indian government welfare schemes.
Given the eligibility guidelines or summary of a scheme, extract the structured qualifying rules into JSON.

RULES & CONSTRAINTS:
- `min_age`: Minimum qualifying age in years (integer) or null if unspecified.
- `max_age`: Maximum qualifying age in years (integer) or null if unspecified.
- `max_income`: Maximum gross household annual income in Indian Rupees (float).
  Convert Indian numbering: e.g. '2.5 lakh' -> 250000.0, '3 lakh' -> 300000.0, '1.5 Lakh' -> 150000.0, or null if no ceiling.
- `allowed_castes`: Comma-separated categories from ['general', 'obc', 'sc', 'st']. Leave null if open to all castes.
- `allowed_genders`: 'female', 'male', or null if open to all genders.
- `allowed_states`: Comma-separated Indian state/UT names, or null if pan-India / central.
- `allowed_occupations`: Comma-separated from ['student', 'farmer', 'laborer', 'self_employed', 'other'], or null if open to all occupations.
- `allowed_education`: Comma-separated from ['10th', '12th', 'graduate', 'postgraduate'], or null if no minimum education.

If a requirement is not mentioned or has no restrictions, set its value to null."""


def _heuristic_extract_rules(text: str) -> Dict[str, Any]:
    """Fallback rule extraction engine using regex patterns.

    Operates deterministically if GEMINI_API_KEY is unavailable.
    """
    data: Dict[str, Any] = {}
    lower = text.lower()

    # Minimum age
    min_age_m = re.search(r"(?:at least|min(?:imum)?|aged?|above)\s*(\d{1,2})\s*(?:years?|yrs)", lower)
    if min_age_m:
        data["min_age"] = int(min_age_m.group(1))

    # Maximum age
    max_age_m = re.search(r"(?:up to|under|max(?:imum)?|below)\s*(\d{1,2})\s*(?:years?|yrs)", lower)
    if max_age_m:
        data["max_age"] = int(max_age_m.group(1))

    # Income cap
    income_lakh_m = re.search(r"(?:income|ceiling|not exceeding|under|up to)?\s*(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|l\b)", lower)
    if income_lakh_m:
        data["max_income"] = float(income_lakh_m.group(1)) * 100000.0

    # Castes
    castes = []
    if re.search(r"\b(sc|scheduled caste)\b", lower):
        castes.append("sc")
    if re.search(r"\b(st|scheduled tribe)\b", lower):
        castes.append("st")
    if re.search(r"\b(obc|other backward class)\b", lower):
        castes.append("obc")
    if castes:
        data["allowed_castes"] = ",".join(castes)

    # Gender
    if re.search(r"\b(female|women|woman|girl|mother)\b", lower) and not re.search(r"\bmale and female\b", lower):
        data["allowed_genders"] = "female"
    elif re.search(r"\b(male|boy|man)\b", lower) and not re.search(r"\bfemale\b", lower):
        data["allowed_genders"] = "male"

    # Occupations
    occs = []
    if re.search(r"\b(farmer|kisan|cultivator)\b", lower):
        occs.append("farmer")
    if re.search(r"\b(student|scholar)\b", lower):
        occs.append("student")
    if re.search(r"\b(laborer|labourer|mazdoor|unskilled worker)\b", lower):
        occs.append("laborer")
    if re.search(r"\b(self-employed|vendor|hawker|artisan|entrepreneur)\b", lower):
        occs.append("self_employed")
    if occs:
        data["allowed_occupations"] = ",".join(occs)

    # Education
    edu = []
    if re.search(r"\b(10th|matric)\b", lower):
        edu.append("10th")
    if re.search(r"\b(12th|intermediate|10\+2)\b", lower):
        edu.append("12th")
    if re.search(r"\b(graduate|degree|bachelor)\b", lower):
        edu.append("graduate")
    if re.search(r"\b(postgraduate|master|phd)\b", lower):
        edu.append("postgraduate")
    if edu:
        data["allowed_education"] = ",".join(edu)

    return data


async def extract_rules_from_text(eligibility_text: str) -> Dict[str, Any]:
    """Extracts structured eligibility rules from guidelines text using Gemini or fallback.

    Returns dict matching EligibilityRules schema.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not gemini_key or gemini_key.strip() in ("", "your_gemini_api_key_here"):
        logger.info("Using regex rule extractor (GEMINI_API_KEY not configured).")
        raw_dict = _heuristic_extract_rules(eligibility_text)
        return EligibilityRules(**raw_dict).model_dump()

    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.0,
            google_api_key=gemini_key,
        )

        structured_llm = llm.with_structured_output(EligibilityRules)
        prompt = ChatPromptTemplate.from_messages([
            ("system", EXTRACTION_SYSTEM_PROMPT),
            ("human", "Government Scheme Eligibility Guidelines:\n{text}"),
        ])

        chain = prompt | structured_llm
        result: EligibilityRules = await chain.ainvoke({"text": eligibility_text})

        # Merge with heuristic fallback if any key fields are missing
        heuristics = _heuristic_extract_rules(eligibility_text)
        res_dict = result.model_dump()
        for k, v in heuristics.items():
            if res_dict.get(k) is None and v is not None:
                res_dict[k] = v

        return EligibilityRules(**res_dict).model_dump()

    except Exception as exc:
        logger.warning(f"Gemini rule extraction encountered error: {exc}. Using heuristic fallback.")
        raw_dict = _heuristic_extract_rules(eligibility_text)
        return EligibilityRules(**raw_dict).model_dump()
