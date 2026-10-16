"""Eligibility Matching Engine for Government Welfare Schemes.

Compares citizen demographic, economic, and occupational attributes against
scheme criteria to determine eligibility, compute match confidence scores,
and detail satisfied vs unsatisfied requirements.
"""

from typing import Any, Dict, List, Optional, Tuple
from models import Scheme, UserProfile


def _check(value: Optional[str], allowed_csv: Optional[str]) -> bool:
    """Check if value matches allowed comma-separated values (case-insensitive).

    Returns True if allowed_csv is None or empty (implying open to all).
    """
    if allowed_csv is None or not str(allowed_csv).strip():
        return True
    if value is None:
        return False

    allowed_items = [
        item.strip().lower()
        for item in str(allowed_csv).split(",")
        if item.strip()
    ]
    return str(value).strip().lower() in allowed_items


def match_scheme(
    profile: UserProfile, scheme: Scheme
) -> Tuple[bool, float, List[str], List[str]]:
    """Evaluates citizen profile against all criteria of a government scheme.

    Checks:
    - Age (min_age, max_age)
    - Income (max_income)
    - Caste category (allowed_castes)
    - Gender (allowed_genders)
    - State (scheme.state and allowed_states)
    - Occupation (allowed_occupations)
    - Education level (allowed_education)

    Returns:
        tuple: (is_eligible: bool, score: float, matched: List[str], failed: List[str])
    """
    matched: List[str] = []
    failed: List[str] = []

    # 1. Age Criteria
    if scheme.min_age is not None:
        if profile.age >= scheme.min_age:
            matched.append(f"Age {profile.age} ≥ minimum age {scheme.min_age}")
        else:
            failed.append(f"Age {profile.age} < minimum age {scheme.min_age}")

    if scheme.max_age is not None:
        if profile.age <= scheme.max_age:
            matched.append(f"Age {profile.age} ≤ maximum age {scheme.max_age}")
        else:
            failed.append(f"Age {profile.age} > maximum age {scheme.max_age}")

    # 2. Income Criteria
    if scheme.max_income is not None:
        if profile.annual_income <= scheme.max_income:
            matched.append(f"Income ₹{profile.annual_income:,.0f} ≤ ₹{scheme.max_income:,.0f}")
        else:
            failed.append(f"Income ₹{profile.annual_income:,.0f} > ₹{scheme.max_income:,.0f}")

    # 3. Caste Category
    if scheme.allowed_castes is not None:
        if _check(profile.caste_category, scheme.allowed_castes):
            matched.append(f"Caste category '{profile.caste_category.upper()}' eligible")
        else:
            failed.append(
                f"Caste category '{profile.caste_category.upper()}' not in allowed categories [{scheme.allowed_castes.upper()}]"
            )

    # 4. Gender
    if scheme.allowed_genders is not None:
        if _check(profile.gender, scheme.allowed_genders):
            matched.append(f"Gender '{profile.gender.title()}' eligible")
        else:
            failed.append(
                f"Gender '{profile.gender.title()}' not eligible (requires: {scheme.allowed_genders})"
            )

    # 5. State / Domicile
    if scheme.state is not None:
        if profile.state.strip().lower() == scheme.state.strip().lower():
            matched.append(f"State resident of {scheme.state}")
        else:
            failed.append(
                f"Resident of {profile.state} (scheme restricted to {scheme.state})"
            )

    if scheme.allowed_states is not None:
        if _check(profile.state, scheme.allowed_states):
            matched.append(f"State '{profile.state}' eligible")
        else:
            failed.append(
                f"State '{profile.state}' not in allowed states [{scheme.allowed_states}]"
            )

    # 6. Occupation
    if scheme.allowed_occupations is not None:
        if _check(profile.occupation, scheme.allowed_occupations):
            matched.append(f"Occupation '{profile.occupation.replace('_', ' ').title()}' eligible")
        else:
            failed.append(
                f"Occupation '{profile.occupation.replace('_', ' ').title()}' not in eligible occupations [{scheme.allowed_occupations}]"
            )

    # 7. Education Level
    if scheme.allowed_education is not None:
        if _check(profile.education_level, scheme.allowed_education):
            matched.append(f"Education level '{profile.education_level.title()}' eligible")
        else:
            failed.append(
                f"Education level '{profile.education_level.title()}' not in required levels [{scheme.allowed_education}]"
            )

    total_criteria = len(matched) + len(failed)
    score = round(len(matched) / total_criteria, 2) if total_criteria > 0 else 1.0
    is_eligible = len(failed) == 0

    return is_eligible, score, matched, failed


def find_matching_schemes(
    profile: UserProfile, schemes: List[Scheme]
) -> List[Dict[str, Any]]:
    """Evaluates all schemes against the profile and returns list sorted by (is_eligible desc, score desc)."""
    results: List[Dict[str, Any]] = []

    for scheme in schemes:
        is_eligible, score, matched, failed = match_scheme(profile, scheme)
        results.append({
            "scheme": scheme,
            "is_eligible": is_eligible,
            "match_score": score,
            "matched_criteria": matched,
            "failed_criteria": failed,
        })

    # Sort: Eligible first, then descending by match score
    results.sort(
        key=lambda item: (item["is_eligible"], item["match_score"]),
        reverse=True,
    )
    return results
