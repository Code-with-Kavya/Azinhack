"""Government Scheme Auto-Apply Agent - Stage 1 Backend API.

FastAPI application providing user profile registration, validation, SQLite persistence,
and an AI-powered conversational demographic extraction engine using LangChain + Google Gemini.
"""

from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel import Session, func, select

from database import engine, get_session, init_db
from eligibility_extractor import extract_rules_from_text
from matcher import find_matching_schemes
from models import Application, Document, Scheme, UserProfile
from schemas import (
    ApplicationDetailedResponse,
    ApplicationResponse,
    ApplyRequest,
    ApplyResponse,
    ConversationalInput,
    ConversationalResponse,
    DocumentResponse,
    EligibilityRules,
    ExtractedProfileData,
    INDIAN_STATES_AND_UTS,
    SchemeMatchResponse,
    SchemeResponse,
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
)
from scheme_database import seed_schemes
from tinyfish_agent import apply_to_scheme, is_dry_run

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gov_scheme_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to initialize DB tables and seed schemes on startup."""
    logger.info("Initializing database tables in profiles.db...")
    init_db()
    logger.info("Database initialized successfully.")
    logger.info("Seeding initial government schemes...")
    seed_schemes()
    logger.info("Schemes verified/seeded.")
    yield
    logger.info("Shutting down Government Scheme API...")


app = FastAPI(
    title="Government Scheme Auto-Apply Agent - Stage 1 API",
    description=(
        "Production-ready Stage 1 API for capturing, validating, and managing citizen profiles "
        "for automated government welfare scheme applications (prior to TinyFish web agent integration)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for React frontend (Vite default :5173, Create-React-App default :3000)
# Allow localhost AND any LAN IP (e.g. 172.17.0.52, 192.168.x.x) on ports 3000/5173/4173
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"http://[\d.]+:(3000|5173|4173)",   # any IP on these ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint providing API metadata."""
    return {
        "status": "healthy",
        "service": "Government Scheme Auto-Apply Agent - Stage 1",
        "version": "1.0.0",
        "docs_url": "/docs",
    }


@app.post(
    "/api/profile",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["User Profile"],
    summary="Create a new citizen user profile",
)
def create_profile(
    profile_in: UserProfileCreate,
    session: Session = Depends(get_session),
):
    """Create and validate a new citizen profile.

    - Validates age (0-120), state (valid Indian state/UT), caste, income, email, etc.
    - Prevents duplicate registration with the same email.
    - Persists record into `profiles.db`.
    """
    # Check for existing email to avoid SQLite unique constraint crash
    existing = session.exec(
        select(UserProfile).where(UserProfile.email == profile_in.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A citizen profile with email '{profile_in.email}' already exists (Profile ID: {existing.id}).",
        )

    db_profile = UserProfile.model_validate(profile_in)
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    logger.info(f"Created profile ID {db_profile.id} for {db_profile.full_name} ({db_profile.email})")
    return db_profile


@app.get(
    "/api/profile/{profile_id}",
    response_model=UserProfileResponse,
    tags=["User Profile"],
    summary="Get citizen profile by ID",
)
def get_profile(
    profile_id: int,
    session: Session = Depends(get_session),
):
    """Retrieve full citizen profile by unique profile ID."""
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )
    return profile


@app.put(
    "/api/profile/{profile_id}",
    response_model=UserProfileResponse,
    tags=["User Profile"],
    summary="Update citizen profile by ID",
)
def update_profile(
    profile_id: int,
    profile_update: UserProfileUpdate,
    session: Session = Depends(get_session),
):
    """Update existing profile fields (partial update supported).

    - If email is being changed, ensures the new email is not in use by another user.
    """
    db_profile = session.get(UserProfile, profile_id)
    if not db_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )

    update_data = profile_update.model_dump(exclude_unset=True)

    # Check email conflict if email is updated
    if "email" in update_data and update_data["email"] != db_profile.email:
        conflict = session.exec(
            select(UserProfile).where(
                UserProfile.email == update_data["email"],
                UserProfile.id != profile_id,
            )
        ).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{update_data['email']}' is already in use by another profile.",
            )

    for field_name, value in update_data.items():
        setattr(db_profile, field_name, value)

    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    logger.info(f"Updated profile ID {profile_id}")
    return db_profile


@app.get(
    "/api/profiles",
    response_model=List[UserProfileResponse],
    tags=["Admin"],
    summary="List all citizen profiles",
)
def list_profiles(
    skip: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum records to return"),
    session: Session = Depends(get_session),
):
    """List registered citizen profiles with pagination (for administrative/auditing use)."""
    total_count = session.exec(select(func.count(UserProfile.id))).one()
    query = select(UserProfile).offset(skip).limit(limit).order_by(UserProfile.id.desc())
    profiles = session.exec(query).all()

    return JSONResponse(
        content=[p.model_dump(mode="json") for p in profiles],
        headers={"X-Total-Count": str(total_count)},
    )


# ---------------------------------------------------------------------------
# BONUS: Conversational Intake Endpoint using LangChain + Google Gemini
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You are an expert civic-tech demographic data extraction AI for Indian Government Welfare Scheme applications.
Given natural language input provided by an Indian citizen, extract demographic, economic, and contact attributes into structured JSON.

MAPPING & NORMALIZATION RULES:
1. `full_name`: Legal name of the citizen if stated or clearly identifiable (e.g., 'Rahul Sharma', 'Pooja Devi'). Otherwise null.
2. `age`: Integer between 0 and 120. Convert phrases like '19-year-old' -> 19, 'nineteen' -> 19.
3. `gender`: Must be one of ['male', 'female', 'other']. If uncertain, null.
4. `state`: Official Indian State or Union Territory name (e.g. 'Bihar', 'Uttar Pradesh', 'Maharashtra', 'Delhi (NCT)').
5. `annual_income`: Household annual income in Indian Rupees as a float.
   - Convert Indian numbering: '2 lakh' or '2L' -> 200000.0, '1.5 lakh' -> 150000.0, '50k' -> 50000.0, '3 LPA' -> 300000.0.
6. `caste_category`: Must be one of:
   - 'sc' (Scheduled Caste, Dalit)
   - 'st' (Scheduled Tribe, Adivasi)
   - 'obc' (Other Backward Class, BC)
   - 'general' (General, Open, Unreserved)
7. `education_level`: Must be one of:
   - '10th' (matriculation, SSC, secondary)
   - '12th' (intermediate, HSC, higher secondary, 10+2)
   - 'graduate' (BA, BSc, BTech, BCom, MBBS, bachelor's degree, college graduate)
   - 'postgraduate' (MA, MSc, MTech, MBA, PhD, master's degree)
8. `occupation`: Must be one of:
   - 'student' (studying in school/college)
   - 'farmer' (kisan, agriculture, farming)
   - 'laborer' (mazdoor, daily wage worker, construction worker)
   - 'self_employed' (shopkeeper, artisan, freelancer, business)
   - 'other'
9. `email`: Valid email address if mentioned.
10. `phone`: 10-digit mobile number if mentioned.

If any field is missing or ambiguous in the text, leave it as null."""


def _heuristic_fallback_extraction(text: str) -> ExtractedProfileData:
    """Deterministic regex-based heuristic extractor used as a robust fallback.

    Ensures the conversational feature functions smoothly even in offline environments
    or when GEMINI_API_KEY is not configured.
    """
    data: Dict[str, Any] = {}
    lower = text.lower()

    # Extract age (e.g. '19-year-old', 'age 24', '20 yrs')
    age_match = re.search(r"\b(\d{1,2})\s*(?:-| )(?:year(?:s)?(?:-old)?|yo|yrs)\b", lower)
    if age_match:
        data["age"] = int(age_match.group(1))

    # Extract income (e.g. '2 lakh', '2.5 lakh', '150000', '2lpa')
    income_lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|l\b)", lower)
    if income_lakh_match:
        data["annual_income"] = float(income_lakh_match.group(1)) * 100000.0
    else:
        num_match = re.search(r"(?:income|earning|salary)(?:\s*(?:is|of|:)?\s*(?:rs\.?|inr|₹)?\s*)(\d{4,8})", lower)
        if num_match:
            data["annual_income"] = float(num_match.group(1))

    # Extract caste
    if re.search(r"\b(sc|scheduled caste|dalit)\b", lower):
        data["caste_category"] = "sc"
    elif re.search(r"\b(st|scheduled tribe|adivasi)\b", lower):
        data["caste_category"] = "st"
    elif re.search(r"\b(obc|other backward class|bc)\b", lower):
        data["caste_category"] = "obc"
    elif re.search(r"\b(general|open|unreserved)\b", lower):
        data["caste_category"] = "general"

    # Extract occupation
    if re.search(r"\b(student|studying|scholar)\b", lower):
        data["occupation"] = "student"
    elif re.search(r"\b(farmer|kisan|agriculture|cultivator)\b", lower):
        data["occupation"] = "farmer"
    elif re.search(r"\b(laborer|labourer|mazdoor|daily wage|worker)\b", lower):
        data["occupation"] = "laborer"
    elif re.search(r"\b(self-employed|self employed|shopkeeper|business)\b", lower):
        data["occupation"] = "self_employed"

    # Extract education
    if re.search(r"\b(10th|matric|matriculation|ssc)\b", lower):
        data["education_level"] = "10th"
    elif re.search(r"\b(12th|intermediate|hsc|10\+2)\b", lower):
        data["education_level"] = "12th"
    elif re.search(r"\b(postgraduate|post-graduate|m\.?tech|m\.?a|m\.?sc|mba|master)\b", lower):
        data["education_level"] = "postgraduate"
    elif re.search(r"\b(graduate|b\.?tech|b\.?a|b\.?sc|b\.?com|bachelor|degree)\b", lower):
        data["education_level"] = "graduate"

    # Extract state from predefined list
    for state_name in INDIAN_STATES_AND_UTS:
        if state_name.lower() in lower:
            data["state"] = state_name
            break

    # Extract gender
    if re.search(r"\b(male|boy|man)\b", lower) and not re.search(r"\bfemale\b", lower):
        data["gender"] = "male"
    elif re.search(r"\b(female|girl|woman)\b", lower):
        data["gender"] = "female"

    # Extract email
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    if email_match:
        data["email"] = email_match.group(0)

    # Extract phone
    phone_match = re.search(r"\b[6-9]\d{9}\b", text)
    if phone_match:
        data["phone"] = phone_match.group(0)

    # Extract name (e.g. "My name is Rahul Kumar", "I am Rahul")
    name_match = re.search(r"(?:my name is|i am|myself)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text, re.IGNORECASE)
    if name_match:
        candidate = name_match.group(1).strip()
        # Avoid common non-name words
        if candidate.lower() not in {"a", "an", "the", "from", "in", "student", "farmer"}:
            data["full_name"] = candidate

    return ExtractedProfileData(**data)


@app.post(
    "/api/profile/conversational",
    response_model=ConversationalResponse,
    tags=["Conversational Intake (Bonus)"],
    summary="Extract structured profile fields from natural language text",
)
def extract_conversational_profile(payload: ConversationalInput):
    """Extracts demographic fields from free-form citizen text using LangChain and Google Gemini.

    Example input:
    "I am a 19-year-old SC student from Bihar, family income 2 lakh, email rahul@gmail.com"

    Extracts:
    - age: 19
    - caste_category: "sc"
    - occupation: "student"
    - state: "Bihar"
    - annual_income: 200000.0
    - email: "rahul@gmail.com"
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not gemini_key:
        logger.warning("GEMINI_API_KEY not set. Using smart rule-based fallback extractor.")
        fallback_data = _heuristic_fallback_extraction(payload.text)
        return ConversationalResponse(
            status="success",
            message="Extracted fields using built-in civic-tech pattern extractor (set GEMINI_API_KEY for Gemini LLM model).",
            extracted_data=fallback_data,
            confidence_notes=[
                "Processed via offline rule engine.",
                "Set GEMINI_API_KEY in backend/.env for deep reasoning with Google Gemini.",
            ],
        )

    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_google_genai import ChatGoogleGenerativeAI

        # Initialize Google Gemini via LangChain
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.0,
            google_api_key=gemini_key,
        )

        # Enforce structured Pydantic output
        structured_llm = llm.with_structured_output(ExtractedProfileData)

        prompt = ChatPromptTemplate.from_messages([
            ("system", EXTRACTION_SYSTEM_PROMPT),
            ("human", "Citizen Input Statement: {citizen_text}"),
        ])

        chain = prompt | structured_llm
        extracted: ExtractedProfileData = chain.invoke({"citizen_text": payload.text})

        # Fill any missing gaps with fallback heuristics (e.g. regex for email/phone)
        fallback = _heuristic_fallback_extraction(payload.text)
        merged_dict = extracted.model_dump()
        for k, v in fallback.model_dump().items():
            if merged_dict.get(k) is None and v is not None:
                merged_dict[k] = v

        final_extracted = ExtractedProfileData(**merged_dict)

        return ConversationalResponse(
            status="success",
            message="Successfully extracted structured demographic attributes using Google Gemini.",
            extracted_data=final_extracted,
            confidence_notes=["Extracted via LangChain Google Gemini with_structured_output."],
        )

    except Exception as exc:
        logger.error(f"Error invoking LangChain Gemini: {exc}. Falling back to heuristic extractor.")
        fallback_data = _heuristic_fallback_extraction(payload.text)
        return ConversationalResponse(
            status="success_fallback",
            message=f"Gemini extraction encountered an issue ({str(exc)}). Retrieved fields via fallback extractor.",
            extracted_data=fallback_data,
            confidence_notes=["Fallback extractor utilized."],
        )


# ---------------------------------------------------------------------------
# STAGE 2: Government Scheme Matching & TinyFish Auto-Apply Endpoints
# ---------------------------------------------------------------------------


async def _run_tinyfish_background_task(
    application_id: int, profile_id: int, scheme_id: int
):
    """Background task executing TinyFish browser agent and updating Application record."""
    with Session(engine) as bg_session:
        app_record = bg_session.get(Application, application_id)
        profile = bg_session.get(UserProfile, profile_id)
        scheme = bg_session.get(Scheme, scheme_id)

        if not app_record or not profile or not scheme:
            logger.error(
                f"Background task aborted: application #{application_id}, profile #{profile_id}, or scheme #{scheme_id} missing."
            )
            return

        # Mark application as running
        app_record.status = "running"
        app_record.updated_at = datetime.now(timezone.utc)
        bg_session.add(app_record)
        bg_session.commit()

        try:
            result = await apply_to_scheme(profile, scheme)
            app_record.tinyfish_run_id = result.get("run_id")
            app_record.screenshot_url = result.get("screenshot_url")
            app_record.mode = result.get("mode", app_record.mode)

            if result.get("status") in ("submitted", "dry_run"):
                app_record.status = result.get("status")
                res_payload = result.get("result") or {}
                if isinstance(res_payload, dict):
                    app_record.result_url = res_payload.get("result_url") or scheme.application_url
            else:
                app_record.status = "failed"
                app_record.error_message = result.get("error")

        except Exception as exc:
            logger.error(f"Error in background TinyFish application #{application_id}: {exc}")
            app_record.status = "failed"
            app_record.error_message = str(exc)

        app_record.updated_at = datetime.now(timezone.utc)
        bg_session.add(app_record)
        bg_session.commit()
        logger.info(
            f"Application #{application_id} finalized with status: {app_record.status} [mode={app_record.mode}]"
        )


@app.get(
    "/api/schemes",
    response_model=List[SchemeResponse],
    tags=["Schemes"],
    summary="List all available government welfare schemes",
)
def list_schemes(session: Session = Depends(get_session)):
    """Retrieve full catalog of government welfare schemes from database."""
    schemes = session.exec(select(Scheme).order_by(Scheme.id.asc())).all()
    return schemes


@app.get(
    "/api/schemes/{scheme_id}",
    response_model=SchemeResponse,
    tags=["Schemes"],
    summary="Get government scheme details by ID",
)
def get_scheme(scheme_id: int, session: Session = Depends(get_session)):
    """Retrieve details and eligibility criteria for a specific government scheme."""
    scheme = session.get(Scheme, scheme_id)
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Government scheme with ID {scheme_id} was not found.",
        )
    return scheme


@app.get(
    "/api/match/{profile_id}",
    response_model=List[SchemeMatchResponse],
    tags=["Scheme Matching"],
    summary="Find eligible government schemes for a citizen profile",
)
def match_profile_schemes(
    profile_id: int, session: Session = Depends(get_session)
):
    """Matches citizen profile against all government schemes.

    Evaluates demographic, socio-economic, occupational, and domicile criteria.
    Returns ONLY eligible schemes, sorted descending by match score.
    """
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )

    schemes = session.exec(select(Scheme)).all()
    evaluations = find_matching_schemes(profile, schemes)

    # Return only eligible schemes sorted descending by score
    eligible_matches = [
        SchemeMatchResponse(
            scheme=SchemeResponse.model_validate(ev["scheme"]),
            match_score=ev["match_score"],
            matched_criteria=ev["matched_criteria"],
            failed_criteria=ev["failed_criteria"],
        )
        for ev in evaluations
        if ev["is_eligible"]
    ]
    return eligible_matches


@app.post(
    "/api/apply",
    response_model=ApplyResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Auto-Apply (TinyFish)"],
    summary="Auto-apply to a government scheme via TinyFish agent",
)
def apply_scheme(
    payload: ApplyRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Initiates automated form application for a government scheme using TinyFish web agent.

    Creates an Application row with status 'pending' and executes browser automation
    in background tasks. Supports demo-safe dry-run mode (default) and live submission.
    """
    profile = session.get(UserProfile, payload.profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {payload.profile_id} was not found.",
        )

    scheme = session.get(Scheme, payload.scheme_id)
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Government scheme with ID {payload.scheme_id} was not found.",
        )

    current_mode = "dry_run" if is_dry_run() else "live"

    # Create application record
    now_utc = datetime.now(timezone.utc)
    app_record = Application(
        profile_id=payload.profile_id,
        scheme_id=payload.scheme_id,
        status="pending",
        mode=current_mode,
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(app_record)
    session.commit()
    session.refresh(app_record)

    # Trigger background TinyFish web agent execution
    background_tasks.add_task(
        _run_tinyfish_background_task,
        application_id=app_record.id,
        profile_id=payload.profile_id,
        scheme_id=payload.scheme_id,
    )

    mode_label = "Demo Dry-Run (Filling fields & capturing screenshot)" if current_mode == "dry_run" else "Live Submission"
    return ApplyResponse(
        application_id=app_record.id,
        status="pending",
        mode=current_mode,
        screenshot_url=None,
        message=(
            f"Application #{app_record.id} for '{scheme.name}' initiated in {mode_label} mode. "
            "TinyFish web agent is automating portal interaction in background."
        ),
        tinyfish_run_id=None,
    )


@app.get(
    "/api/applications/{profile_id}",
    response_model=List[ApplicationResponse],
    tags=["Auto-Apply (TinyFish)"],
    summary="List all applications submitted for a citizen profile",
)
def get_profile_applications(
    profile_id: int, session: Session = Depends(get_session)
):
    """Retrieve history and execution status of all scheme applications for a citizen profile."""
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )

    applications = session.exec(
        select(Application)
        .where(Application.profile_id == profile_id)
        .order_by(Application.created_at.desc())
    ).all()
    return applications


# ---------------------------------------------------------------------------
# STAGE 3: Application Tracking Dashboard, Live SSE Stream & Document Upload
# ---------------------------------------------------------------------------


@app.get(
    "/api/applications/{profile_id}/detailed",
    response_model=List[ApplicationDetailedResponse],
    tags=["Auto-Apply (TinyFish)"],
    summary="Get detailed application tracking records with joined scheme metadata",
)
def get_detailed_applications(
    profile_id: int, session: Session = Depends(get_session)
):
    """Joins Application + Scheme to provide comprehensive status timeline, mode,

    screenshot URL, error messages, and timestamps for dashboard tracking.
    """
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )

    query = (
        select(Application, Scheme)
        .join(Scheme, Application.scheme_id == Scheme.id)
        .where(Application.profile_id == profile_id)
        .order_by(Application.created_at.desc())
    )
    records = session.exec(query).all()

    detailed_list = []
    for app_row, scheme_row in records:
        detailed_list.append(
            ApplicationDetailedResponse(
                id=app_row.id,
                profile_id=app_row.profile_id,
                scheme_id=app_row.scheme_id,
                scheme_name=scheme_row.name,
                scheme_category=scheme_row.category,
                ministry=scheme_row.ministry,
                status=app_row.status,
                mode=getattr(app_row, "mode", "dry_run"),
                tinyfish_run_id=app_row.tinyfish_run_id,
                screenshot_url=getattr(app_row, "screenshot_url", None),
                result_url=app_row.result_url,
                error_message=app_row.error_message,
                created_at=app_row.created_at,
                updated_at=getattr(app_row, "updated_at", app_row.created_at),
            )
        )
    return detailed_list


@app.get(
    "/api/apply/stream/{application_id}",
    tags=["Auto-Apply (TinyFish)"],
    summary="Server-Sent Events stream for live TinyFish application progress",
)
async def stream_application_progress(
    application_id: int, session: Session = Depends(get_session)
):
    """Server-Sent Events (SSE) stream providing real-time execution steps and status

    updates for an ongoing TinyFish browser agent run.
    """
    app_record = session.get(Application, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {application_id} was not found.",
        )

    async def event_generator():
        start_time = asyncio.get_event_loop().time()
        max_duration = 300  # 5 minutes maximum stream duration

        steps_sequence = [
            "Initializing TinyFish browser sandbox...",
            "Navigating to official scheme application portal...",
            "Analyzing form fields and security tokens...",
            "Populating citizen demographic and identity parameters...",
            "Validating filled fields and calculating declarations...",
            "Executing action: capturing full-page screenshot...",
            "Finalizing application verification...",
        ]

        step_idx = 0
        while True:
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed > max_duration:
                payload = json.dumps({
                    "status": "timeout",
                    "step": "Stream closed after 300s timeout.",
                    "elapsed_s": elapsed,
                })
                yield f"data: {payload}\n\n"
                break

            # Poll latest DB status
            with Session(engine) as poll_session:
                current_app = poll_session.get(Application, application_id)
                current_status = current_app.status if current_app else "unknown"
                current_mode = getattr(current_app, "mode", "dry_run")
                error_msg = current_app.error_message if current_app else None
                screenshot = getattr(current_app, "screenshot_url", None)

            current_step = steps_sequence[min(step_idx, len(steps_sequence) - 1)]
            if current_status in ("submitted", "dry_run"):
                current_step = (
                    "✓ Demo dry-run completed! Full-page screenshot captured."
                    if current_status == "dry_run"
                    else "✓ Application successfully submitted to portal!"
                )
            elif current_status == "failed":
                current_step = f"Execution stopped: {error_msg or 'Portal error'}"

            data_obj = {
                "application_id": application_id,
                "status": current_status,
                "mode": current_mode,
                "step": current_step,
                "elapsed_s": elapsed,
                "screenshot_url": screenshot,
            }
            yield f"data: {json.dumps(data_obj)}\n\n"

            if current_status in ("submitted", "dry_run", "failed"):
                break

            step_idx += 1
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/api/admin/backfill-rules",
    tags=["Admin"],
    summary="Backfill scheme eligibility criteria using Gemini LLM rule extractor",
)
async def backfill_scheme_rules(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    session: Session = Depends(get_session),
):
    """Protected admin endpoint that iterates over schemes with incomplete criteria

    and uses Google Gemini to extract structured eligibility rules from their description.
    """
    admin_token = os.getenv("ADMIN_TOKEN", "dev-token")
    if not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Token header.",
        )

    schemes = session.exec(select(Scheme)).all()
    updated_count = 0
    details = []

    for scheme in schemes:
        needs_backfill = (
            scheme.min_age is None
            and scheme.max_age is None
            and scheme.max_income is None
            and scheme.allowed_castes is None
            and scheme.allowed_occupations is None
            and scheme.allowed_education is None
        )
        if needs_backfill and scheme.eligibility_text:
            extracted = await extract_rules_from_text(scheme.eligibility_text)
            modified = False
            for field, val in extracted.items():
                if val is not None and getattr(scheme, field) is None:
                    setattr(scheme, field, val)
                    modified = True
            if modified:
                session.add(scheme)
                updated_count += 1
                details.append({
                    "scheme_id": scheme.id,
                    "name": scheme.name,
                    "rules": extracted,
                })

    session.commit()
    return {
        "status": "success",
        "schemes_updated": updated_count,
        "details": details,
    }


VALID_DOC_TYPES = {"aadhaar", "income_cert", "bank_passbook", "caste_cert"}


@app.post(
    "/api/profile/{profile_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Citizen Documents"],
    summary="Upload citizen document with OCR processing (stub)",
)
async def upload_citizen_document(
    profile_id: int,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    session: Session = Depends(get_session),
):
    """Uploads a citizen document (Aadhaar, income cert, bank passbook, or caste cert)

    stores it under `backend/uploads/{profile_id}/` and records a Document row with OCR metadata.
    """
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )

    cleaned_doc_type = doc_type.strip().lower()
    if cleaned_doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid doc_type '{doc_type}'. Must be one of: {', '.join(sorted(VALID_DOC_TYPES))}",
        )

    # Save to disk
    upload_dir = Path(__file__).resolve().parent / "uploads" / str(profile_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest_path = upload_dir / file.filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc_record = Document(
        profile_id=profile_id,
        doc_type=cleaned_doc_type,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        uploaded_at=datetime.now(timezone.utc),
        extracted_fields=None,
    )
    session.add(doc_record)
    session.commit()
    session.refresh(doc_record)

    return DocumentResponse(
        id=doc_record.id,
        profile_id=doc_record.profile_id,
        doc_type=doc_record.doc_type,
        filename=doc_record.filename,
        content_type=doc_record.content_type,
        uploaded_at=doc_record.uploaded_at,
        extracted_fields=None,
        note="OCR not configured (stub active). Document stored securely.",
    )


@app.get(
    "/api/profile/{profile_id}/documents",
    response_model=List[DocumentResponse],
    tags=["Citizen Documents"],
    summary="List uploaded verification documents for citizen profile",
)
def list_citizen_documents(
    profile_id: int, session: Session = Depends(get_session)
):
    """Retrieve all uploaded verification documents for a citizen profile."""
    profile = session.get(UserProfile, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen profile with ID {profile_id} was not found.",
        )

    docs = session.exec(
        select(Document)
        .where(Document.profile_id == profile_id)
        .order_by(Document.uploaded_at.desc())
    ).all()

    return [
        DocumentResponse(
            id=d.id,
            profile_id=d.profile_id,
            doc_type=d.doc_type,
            filename=d.filename,
            content_type=d.content_type,
            uploaded_at=d.uploaded_at,
            extracted_fields=json.loads(d.extracted_fields) if d.extracted_fields else None,
            note="Document on file",
        )
        for d in docs
    ]
