"""Pydantic schemas and validation rules for Government Scheme Auto-Apply Agent.

Provides strict request/response data models with Indian demographic standards.
"""

from datetime import datetime
import re
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# 28 Indian States + 8 Union Territories
INDIAN_STATES_AND_UTS: List[str] = [
    # 28 States
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    # 8 Union Territories
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi (NCT)",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

# Lookup dictionary for fast case-insensitive normalization of Indian states
STATE_LOOKUP = {s.lower(): s for s in INDIAN_STATES_AND_UTS}
STATE_LOOKUP["delhi"] = "Delhi (NCT)"
STATE_LOOKUP["nct of delhi"] = "Delhi (NCT)"
STATE_LOOKUP["dadra and nagar haveli"] = "Dadra and Nagar Haveli and Daman and Diu"
STATE_LOOKUP["daman and diu"] = "Dadra and Nagar Haveli and Daman and Diu"
STATE_LOOKUP["orissa"] = "Odisha"
STATE_LOOKUP["pondicherry"] = "Puducherry"

VALID_GENDERS = {"male", "female", "other"}
VALID_CASTES = {"general", "obc", "sc", "st"}
VALID_EDUCATION = {"10th", "12th", "graduate", "postgraduate"}
VALID_OCCUPATIONS = {"student", "farmer", "laborer", "self_employed", "other"}


class UserProfileBase(BaseModel):
    """Base schema containing common citizen profile attributes."""

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Full legal name of the citizen",
        examples=["Rahul Kumar Sharma"],
    )
    age: int = Field(
        ...,
        ge=0,
        le=120,
        description="Age between 0 and 120",
        examples=[22],
    )
    gender: str = Field(
        ...,
        description="Gender: male, female, or other",
        examples=["male"],
    )
    state: str = Field(
        ...,
        description="Valid Indian State or Union Territory",
        examples=["Bihar"],
    )
    annual_income: float = Field(
        ...,
        ge=0.0,
        description="Gross annual household income in INR",
        examples=[180000.0],
    )
    caste_category: str = Field(
        ...,
        description="Caste category: general, obc, sc, or st",
        examples=["sc"],
    )
    education_level: str = Field(
        ...,
        description="Highest education: 10th, 12th, graduate, or postgraduate",
        examples=["graduate"],
    )
    occupation: str = Field(
        ...,
        description="Primary occupation: student, farmer, laborer, self_employed, or other",
        examples=["student"],
    )
    email: EmailStr = Field(
        ...,
        description="Unique contact email address",
        examples=["rahul.sharma@example.com"],
    )
    phone: Optional[str] = Field(
        default=None,
        description="Optional 10-digit Indian mobile number",
        examples=["9876543210"],
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        name = v.strip()
        if len(name) < 2:
            raise ValueError("Full name must be at least 2 characters long.")
        return name

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in VALID_GENDERS:
            raise ValueError(f"Invalid gender '{v}'. Must be one of: {', '.join(sorted(VALID_GENDERS))}")
        return cleaned

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned in STATE_LOOKUP:
            return STATE_LOOKUP[cleaned]
        raise ValueError(
            f"Invalid state or UT '{v}'. Please provide a valid Indian State or Union Territory."
        )

    @field_validator("caste_category")
    @classmethod
    def validate_caste(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in VALID_CASTES:
            raise ValueError(
                f"Invalid caste category '{v}'. Must be one of: {', '.join(sorted(VALID_CASTES))}"
            )
        return cleaned

    @field_validator("education_level")
    @classmethod
    def validate_education(cls, v: str) -> str:
        cleaned = v.strip().lower().replace(" ", "")
        if cleaned in ["post-graduate", "post_graduate"]:
            cleaned = "postgraduate"
        if cleaned not in VALID_EDUCATION:
            raise ValueError(
                f"Invalid education level '{v}'. Must be one of: {', '.join(sorted(VALID_EDUCATION))}"
            )
        return cleaned

    @field_validator("occupation")
    @classmethod
    def validate_occupation(cls, v: str) -> str:
        cleaned = v.strip().lower().replace("-", "_").replace(" ", "_")
        if cleaned not in VALID_OCCUPATIONS:
            raise ValueError(
                f"Invalid occupation '{v}'. Must be one of: {', '.join(sorted(VALID_OCCUPATIONS))}"
            )
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        cleaned = re.sub(r"[^\d]", "", str(v))
        # Strip country code +91 or leading 0 if 12 or 11 digits
        if len(cleaned) == 12 and cleaned.startswith("91"):
            cleaned = cleaned[2:]
        elif len(cleaned) == 11 and cleaned.startswith("0"):
            cleaned = cleaned[1:]

        if not re.fullmatch(r"^[6-9]\d{9}$", cleaned):
            raise ValueError(
                "Phone number must be a valid 10-digit Indian mobile number (starting with 6-9)."
            )
        return cleaned


class UserProfileCreate(UserProfileBase):
    """Payload schema for profile creation (POST /api/profile)."""
    pass


class UserProfileUpdate(BaseModel):
    """Payload schema for profile update (PUT /api/profile/{id}).

    All fields are optional to allow partial updates.
    """

    full_name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[str] = None
    state: Optional[str] = None
    annual_income: Optional[float] = Field(default=None, ge=0.0)
    caste_category: Optional[str] = None
    education_level: Optional[str] = None
    occupation: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            name = v.strip()
            if len(name) < 2:
                raise ValueError("Full name must be at least 2 characters long.")
            return name
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().lower()
            if cleaned not in VALID_GENDERS:
                raise ValueError(f"Invalid gender '{v}'. Must be one of: {', '.join(sorted(VALID_GENDERS))}")
            return cleaned
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().lower()
            if cleaned in STATE_LOOKUP:
                return STATE_LOOKUP[cleaned]
            raise ValueError(f"Invalid state or UT '{v}'.")
        return v

    @field_validator("caste_category")
    @classmethod
    def validate_caste(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().lower()
            if cleaned not in VALID_CASTES:
                raise ValueError(f"Invalid caste category '{v}'.")
            return cleaned
        return v

    @field_validator("education_level")
    @classmethod
    def validate_education(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().lower().replace(" ", "")
            if cleaned in ["post-graduate", "post_graduate"]:
                cleaned = "postgraduate"
            if cleaned not in VALID_EDUCATION:
                raise ValueError(f"Invalid education level '{v}'.")
            return cleaned
        return v

    @field_validator("occupation")
    @classmethod
    def validate_occupation(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip().lower().replace("-", "_").replace(" ", "_")
            if cleaned not in VALID_OCCUPATIONS:
                raise ValueError(f"Invalid occupation '{v}'.")
            return cleaned
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        cleaned = re.sub(r"[^\d]", "", str(v))
        if len(cleaned) == 12 and cleaned.startswith("91"):
            cleaned = cleaned[2:]
        elif len(cleaned) == 11 and cleaned.startswith("0"):
            cleaned = cleaned[1:]
        if not re.fullmatch(r"^[6-9]\d{9}$", cleaned):
            raise ValueError("Phone number must be a valid 10-digit Indian mobile number.")
        return cleaned


class UserProfileResponse(UserProfileBase):
    """Response schema returned to clients."""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationalInput(BaseModel):
    """Input payload for conversational profile extraction."""

    text: str = Field(
        ...,
        min_length=5,
        description="Natural language statement by the citizen",
        examples=["I am a 19-year-old SC student from Bihar, family income 2 lakh, email rahul@gmail.com"],
    )


class ExtractedProfileData(BaseModel):
    """Structured extraction target for LangChain Google Gemini structured output."""

    full_name: Optional[str] = Field(
        default=None,
        description="Citizen's full name if mentioned or implied",
    )
    age: Optional[int] = Field(
        default=None,
        description="Citizen's age in years (0-120)",
    )
    gender: Optional[str] = Field(
        default=None,
        description="male, female, or other",
    )
    state: Optional[str] = Field(
        default=None,
        description="Indian State or Union Territory",
    )
    annual_income: Optional[float] = Field(
        default=None,
        description="Annual household income in Indian Rupees (e.g. 2 lakh = 200000)",
    )
    caste_category: Optional[str] = Field(
        default=None,
        description="general, obc, sc, or st",
    )
    education_level: Optional[str] = Field(
        default=None,
        description="10th, 12th, graduate, or postgraduate",
    )
    occupation: Optional[str] = Field(
        default=None,
        description="student, farmer, laborer, self_employed, or other",
    )
    email: Optional[str] = Field(
        default=None,
        description="Email address if provided",
    )
    phone: Optional[str] = Field(
        default=None,
        description="10-digit phone number if provided",
    )


class ConversationalResponse(BaseModel):
    """API response for conversational extraction endpoint."""

    status: str
    message: str
    extracted_data: ExtractedProfileData
    confidence_notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# STAGE 2 SCHEMAS: Scheme Matching & TinyFish Auto-Apply
# ---------------------------------------------------------------------------


class SchemeResponse(BaseModel):
    """Response schema for government schemes."""

    id: int
    name: str
    description: str
    ministry: Optional[str] = None
    state: Optional[str] = None
    category: str
    official_url: str
    application_url: Optional[str] = None
    eligibility_text: str
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    max_income: Optional[float] = None
    allowed_castes: Optional[str] = None
    allowed_genders: Optional[str] = None
    allowed_states: Optional[str] = None
    allowed_occupations: Optional[str] = None
    allowed_education: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SchemeMatchResponse(BaseModel):
    """Response schema for matched scheme eligibility evaluation."""

    scheme: SchemeResponse
    match_score: float = Field(..., description="Eligibility match score between 0.0 and 1.0")
    matched_criteria: List[str] = Field(default_factory=list, description="Criteria satisfied by citizen")
    failed_criteria: List[str] = Field(default_factory=list, description="Criteria unmet by citizen")


class ApplyRequest(BaseModel):
    """Payload schema to trigger auto-apply for a scheme."""

    profile_id: int = Field(..., description="Target citizen profile ID")
    scheme_id: int = Field(..., description="Target government scheme ID")


class ApplyResponse(BaseModel):
    """Response schema returned upon initiating scheme application."""

    application_id: int
    status: str
    message: str
    tinyfish_run_id: Optional[str] = None
    mode: str = "dry_run"
    screenshot_url: Optional[str] = None


class ApplicationResponse(BaseModel):
    """Response schema for application tracking records."""

    id: int
    profile_id: int
    scheme_id: int
    status: str
    mode: str = "dry_run"
    tinyfish_run_id: Optional[str] = None
    screenshot_url: Optional[str] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationDetailedResponse(BaseModel):
    """Joined details of application and target government scheme."""

    id: int
    profile_id: int
    scheme_id: int
    scheme_name: str
    scheme_category: str
    ministry: Optional[str] = None
    status: str
    mode: str = "dry_run"
    tinyfish_run_id: Optional[str] = None
    screenshot_url: Optional[str] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EligibilityRules(BaseModel):
    """Structured eligibility parameters extracted from text via Gemini LLM."""

    min_age: Optional[int] = None
    max_age: Optional[int] = None
    max_income: Optional[float] = None
    allowed_castes: Optional[str] = None
    allowed_genders: Optional[str] = None
    allowed_states: Optional[str] = None
    allowed_occupations: Optional[str] = None
    allowed_education: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response schema for uploaded citizen documents."""

    id: int
    profile_id: int
    doc_type: str
    filename: str
    content_type: str
    uploaded_at: datetime
    extracted_fields: Optional[Any] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
