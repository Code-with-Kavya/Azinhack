"""Database models for Government Scheme Auto-Apply Agent (Stage 1).

Defines the UserProfile SQLModel mapped to the SQLite database.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    """SQLModel table definition for citizen profiles.

    Stores demographic, socio-economic, and contact attributes required for
    matching and auto-applying to Indian government welfare schemes.
    """

    __tablename__ = "user_profiles"

    # Primary Key
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing unique identifier for user profile",
    )

    # Core Personal Details
    full_name: str = Field(
        nullable=False,
        max_length=150,
        description="Full legal name of the citizen as per Aadhaar/Govt ID",
    )
    age: int = Field(
        nullable=False,
        ge=0,
        le=120,
        description="Age of citizen in years (0 - 120)",
    )
    gender: str = Field(
        nullable=False,
        description="Gender: 'male', 'female', or 'other'",
    )
    state: str = Field(
        nullable=False,
        description="State or Union Territory of residence in India",
    )

    # Socio-Economic & Eligibility Parameters
    annual_income: float = Field(
        nullable=False,
        ge=0.0,
        description="Gross annual household income in Indian Rupees (₹)",
    )
    caste_category: str = Field(
        nullable=False,
        description="Caste category: 'general', 'obc', 'sc', or 'st'",
    )
    education_level: str = Field(
        nullable=False,
        description="Highest education attained: '10th', '12th', 'graduate', or 'postgraduate'",
    )
    occupation: str = Field(
        nullable=False,
        description="Primary occupation: 'student', 'farmer', 'laborer', 'self_employed', or 'other'",
    )

    # Contact Details (Indexed & Unique Email)
    email: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Unique email address of citizen (indexed for O(1) lookups)",
    )
    phone: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Optional 10-digit Indian mobile number",
    )

    # Audit & Metadata
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="UTC timestamp when the profile was registered",
    )


class Scheme(SQLModel, table=True):
    """SQLModel table definition for government schemes.

    Contains eligibility criteria parameters and portal URLs for automated
    matching and TinyFish web agent navigation.
    """

    __tablename__ = "schemes"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing unique identifier for scheme",
    )
    name: str = Field(
        index=True,
        nullable=False,
        description="Official scheme name",
    )
    description: str = Field(
        nullable=False,
        description="Detailed scheme description and benefits",
    )
    ministry: Optional[str] = Field(
        default=None,
        description="Administering ministry or department",
    )
    state: Optional[str] = Field(
        default=None,
        description="State/UT name, or NULL for Central/National schemes",
    )
    category: str = Field(
        nullable=False,
        description="Scheme domain (e.g. Agriculture, Healthcare, Education, Employment)",
    )
    official_url: str = Field(
        nullable=False,
        description="Official informational website URL",
    )
    application_url: Optional[str] = Field(
        default=None,
        description="Direct online application or registration portal URL",
    )
    eligibility_text: str = Field(
        nullable=False,
        description="Human-readable eligibility summary",
    )
    min_age: Optional[int] = Field(
        default=None,
        description="Minimum qualifying age in years",
    )
    max_age: Optional[int] = Field(
        default=None,
        description="Maximum qualifying age in years",
    )
    max_income: Optional[float] = Field(
        default=None,
        description="Maximum annual household income in INR",
    )
    allowed_castes: Optional[str] = Field(
        default=None,
        description="Comma-separated caste categories (e.g. 'general,obc,sc,st')",
    )
    allowed_genders: Optional[str] = Field(
        default=None,
        description="Comma-separated genders (e.g. 'male,female,other')",
    )
    allowed_states: Optional[str] = Field(
        default=None,
        description="Comma-separated Indian states/UTs (NULL = pan-India)",
    )
    allowed_occupations: Optional[str] = Field(
        default=None,
        description="Comma-separated occupations (e.g. 'farmer,student,laborer')",
    )
    allowed_education: Optional[str] = Field(
        default=None,
        description="Comma-separated education levels (e.g. '10th,12th,graduate,postgraduate')",
    )


class Application(SQLModel, table=True):
    """SQLModel table definition for citizen scheme applications.

    Tracks auto-apply status and TinyFish web agent execution run results.
    """

    __tablename__ = "applications"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing unique identifier for application",
    )
    profile_id: int = Field(
        foreign_key="user_profiles.id",
        nullable=False,
        description="Foreign key referencing user_profiles.id",
    )
    scheme_id: int = Field(
        foreign_key="schemes.id",
        nullable=False,
        description="Foreign key referencing schemes.id",
    )
    status: str = Field(
        default="pending",
        nullable=False,
        description="Application status: pending, running, submitted, failed",
    )
    mode: str = Field(
        default="dry_run",
        nullable=False,
        description="Execution mode: 'dry_run' or 'live'",
    )
    tinyfish_run_id: Optional[str] = Field(
        default=None,
        description="TinyFish web agent execution run ID",
    )
    screenshot_url: Optional[str] = Field(
        default=None,
        description="URL or path to captured full-page form screenshot in dry-run mode",
    )
    result_url: Optional[str] = Field(
        default=None,
        description="Submission confirmation/receipt URL",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Failure reason if web agent execution was unsuccessful",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="UTC timestamp when the application was recorded",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="UTC timestamp when the application was last updated",
    )


class Document(SQLModel, table=True):
    """SQLModel table definition for uploaded citizen documents.

    Stores document metadata and extracted OCR field results.
    """

    __tablename__ = "documents"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing unique identifier for document record",
    )
    profile_id: int = Field(
        foreign_key="user_profiles.id",
        nullable=False,
        description="Foreign key referencing user_profiles.id",
    )
    doc_type: str = Field(
        nullable=False,
        description="Document type: 'aadhaar', 'income_cert', 'bank_passbook', or 'caste_cert'",
    )
    filename: str = Field(
        nullable=False,
        description="Saved file name on disk",
    )
    content_type: str = Field(
        nullable=False,
        description="MIME type of the uploaded file",
    )
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        description="UTC timestamp when document was uploaded",
    )
    extracted_fields: Optional[str] = Field(
        default=None,
        description="JSON string representing extracted OCR key-values",
    )
