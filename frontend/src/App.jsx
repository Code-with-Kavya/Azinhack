import React, { useState, useEffect } from "react";
import axios from "axios";
import SchemeList from "./components/SchemeList.jsx";

// Auto-detect backend host from current page (works for localhost AND 172.17.0.52)
const API_BASE = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

// Comprehensive list of 28 Indian States and 8 Union Territories
const INDIAN_STATES_AND_UTS = [
  // 28 States
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
  // 8 Union Territories
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi (NCT)",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
];

const INITIAL_FORM = {
  full_name: "",
  age: "",
  gender: "male",
  state: "",
  annual_income: "",
  caste_category: "general",
  education_level: "graduate",
  occupation: "student",
  email: "",
  phone: "",
};

export default function App() {
  // Navigation Tabs: "profile" | "schemes"
  const [activeTab, setActiveTab] = useState("profile");
  const [savedProfileId, setSavedProfileId] = useState(null);

  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdProfile, setCreatedProfile] = useState(null);

  // Bonus AI Conversational Intake State
  const [aiText, setAiText] = useState("");
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [showAiBox, setShowAiBox] = useState(true);

  // Admin Profiles Drawer State
  const [adminProfiles, setAdminProfiles] = useState([]);
  const [showAdminDrawer, setShowAdminDrawer] = useState(false);
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false);

  // Handle generic field change
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    // Clear error for this field
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: "" }));
    }
  };

  // Step-by-step validation
  const validateStep = (step) => {
    const newErrors = {};

    if (step === 1) {
      if (!formData.full_name.trim()) {
        newErrors.full_name = "Full name is required.";
      } else if (formData.full_name.trim().length < 2) {
        newErrors.full_name = "Full name must be at least 2 characters.";
      }

      if (formData.age === "" || formData.age === null) {
        newErrors.age = "Age is required.";
      } else {
        const numAge = Number(formData.age);
        if (isNaN(numAge) || numAge < 0 || numAge > 120) {
          newErrors.age = "Age must be a valid number between 0 and 120.";
        }
      }

      if (!formData.gender) {
        newErrors.gender = "Please select a gender.";
      }

      if (!formData.state) {
        newErrors.state = "Please select an Indian State or UT.";
      }
    }

    if (step === 2) {
      if (formData.annual_income === "" || formData.annual_income === null) {
        newErrors.annual_income = "Annual household income is required.";
      } else {
        const numIncome = Number(formData.annual_income);
        if (isNaN(numIncome) || numIncome < 0) {
          newErrors.annual_income = "Income must be a non-negative number.";
        }
      }

      if (!formData.caste_category) {
        newErrors.caste_category = "Please select a caste category.";
      }

      if (!formData.education_level) {
        newErrors.education_level = "Please select your education level.";
      }

      if (!formData.occupation) {
        newErrors.occupation = "Please select your primary occupation.";
      }
    }

    if (step === 3) {
      if (!formData.email.trim()) {
        newErrors.email = "Email address is required.";
      } else {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(formData.email.trim())) {
          newErrors.email = "Please enter a valid email address.";
        }
      }

      if (formData.phone && formData.phone.trim()) {
        const cleanedPhone = formData.phone.replace(/\D/g, "");
        if (!/^[6-9]\d{9}$/.test(cleanedPhone)) {
          newErrors.phone = "Mobile number must be a 10-digit Indian number starting with 6, 7, 8, or 9.";
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setServerError("");
      setCurrentStep((prev) => Math.min(prev + 1, 3));
    }
  };

  const handlePrev = () => {
    setServerError("");
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  // Form Submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError("");

    if (!validateStep(1) || !validateStep(2) || !validateStep(3)) {
      setServerError("Please resolve all validation errors before submitting.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        full_name: formData.full_name.trim(),
        age: parseInt(formData.age, 10),
        gender: formData.gender.toLowerCase(),
        state: formData.state,
        annual_income: parseFloat(formData.annual_income),
        caste_category: formData.caste_category.toLowerCase(),
        education_level: formData.education_level.toLowerCase(),
        occupation: formData.occupation.toLowerCase(),
        email: formData.email.trim().toLowerCase(),
        phone: formData.phone.trim() ? formData.phone.trim() : null,
      };

      const response = await axios.post(`${API_BASE}/api/profile`, payload);
      setCreatedProfile(response.data);
      setSavedProfileId(response.data.id);
      setCurrentStep(4); // Success step
    } catch (err) {
      console.error("Submission error:", err);
      if (err.response && err.response.data && err.response.data.detail) {
        setServerError(
          typeof err.response.data.detail === "string"
            ? err.response.data.detail
            : JSON.stringify(err.response.data.detail)
        );
      } else {
        setServerError("Failed to connect to backend at " + API_BASE + ". Is the FastAPI server running?");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Bonus: AI Conversational Auto-Fill
  const handleConversationalExtract = async () => {
    if (!aiText.trim()) return;
    setIsAiLoading(true);
    setAiMessage("");
    setServerError("");

    try {
      const res = await axios.post(`${API_BASE}/api/profile/conversational`, {
        text: aiText.trim(),
      });

      const extracted = res.data.extracted_data;
      setFormData((prev) => ({
        ...prev,
        full_name: extracted.full_name || prev.full_name,
        age: extracted.age !== null && extracted.age !== undefined ? String(extracted.age) : prev.age,
        gender: extracted.gender || prev.gender,
        state: extracted.state || prev.state,
        annual_income:
          extracted.annual_income !== null && extracted.annual_income !== undefined
            ? String(extracted.annual_income)
            : prev.annual_income,
        caste_category: extracted.caste_category || prev.caste_category,
        education_level: extracted.education_level || prev.education_level,
        occupation: extracted.occupation || prev.occupation,
        email: extracted.email || prev.email,
        phone: extracted.phone || prev.phone,
      }));

      setAiMessage("✓ Demographic fields successfully extracted and populated into form!");
      setErrors({});
    } catch (err) {
      console.error("AI extraction error:", err);
      setAiMessage("Could not extract fields automatically. Please fill the form manually.");
    } finally {
      setIsAiLoading(false);
    }
  };

  // Fetch admin profiles
  const fetchProfiles = async () => {
    setIsLoadingProfiles(true);
    try {
      const res = await axios.get(`${API_BASE}/api/profiles?limit=50`);
      setAdminProfiles(res.data);
      setShowAdminDrawer(true);
    } catch (err) {
      alert("Error loading profiles: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsLoadingProfiles(false);
    }
  };

  const handleReset = () => {
    setFormData(INITIAL_FORM);
    setErrors({});
    setServerError("");
    setCreatedProfile(null);
    setCurrentStep(1);
    setAiText("");
    setAiMessage("");
  };

  return (
    <div className="gov-app">
      {/* Top Government Portal Header */}
      <header className="gov-header">
        <div className="container header-content">
          <div className="logo-group">
            <span className="emblem-badge">🇮🇳</span>
            <div>
              <h1 className="portal-title">Government Scheme Auto-Apply Agent</h1>
              <p className="portal-subtitle">Stage 1: Citizen Profile Intake & Validation Engine</p>
            </div>
          </div>
          <div className="header-actions">
            <button className="btn-secondary-sm" onClick={fetchProfiles}>
              📋 View DB Profiles ({adminProfiles.length > 0 ? adminProfiles.length : "Admin"})
            </button>
          </div>
        </div>
      </header>

      <main className="container main-content">
        {/* Stage 1 & 2 Tab Navigation Bar */}
        <div className="tab-nav-bar">
          <button
            type="button"
            className={`tab-btn ${activeTab === "profile" ? "active" : ""}`}
            onClick={() => setActiveTab("profile")}
          >
            📋 Profile
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === "schemes" ? "active" : ""}`}
            onClick={() => setActiveTab("schemes")}
          >
            🎯 My Schemes {savedProfileId ? `(#${savedProfileId})` : ""}
          </button>
        </div>

        {activeTab === "schemes" ? (
          <SchemeList
            profileId={savedProfileId}
            onNavigateToProfile={() => setActiveTab("profile")}
          />
        ) : (
          <>
            {/* Stage Context Banner */}
            <div className="stage-banner">
              <span className="stage-pill">STAGE 1 & 2 ACTIVE</span>
              <p>
                <strong>Citizen Profile & TinyFish Auto-Apply:</strong> Register your citizen profile here,
                then view eligible schemes and auto-apply via TinyFish web agent in the <strong>🎯 My Schemes</strong> tab.
              </p>
            </div>

        {/* AI Quick Fill Section (Bonus Feature) */}
        {currentStep < 4 && (
          <section className="ai-box">
            <div className="ai-box-header" onClick={() => setShowAiBox(!showAiBox)}>
              <div className="ai-box-title">
                <span className="sparkle-icon">✨</span>
                <strong>AI Quick-Fill with Google Gemini (Conversational Intake)</strong>
              </div>
              <button type="button" className="text-toggle-btn">
                {showAiBox ? "Hide ▲" : "Show ▼"}
              </button>
            </div>

            {showAiBox && (
              <div className="ai-box-body">
                <p className="ai-box-desc">
                  Type or paste free-form citizen text. The agent extracts structured demographic parameters
                  using <code>langchain-google-genai</code> and populates the form below:
                </p>
                <div className="ai-input-group">
                  <textarea
                    rows={2}
                    value={aiText}
                    onChange={(e) => setAiText(e.target.value)}
                    placeholder="e.g. I am Rahul Kumar, a 19-year-old SC student from Bihar, family income 2 lakh, email rahul.sharma@example.com"
                    className="ai-textarea"
                  />
                  <button
                    type="button"
                    className="btn-ai"
                    onClick={handleConversationalExtract}
                    disabled={isAiLoading || !aiText.trim()}
                  >
                    {isAiLoading ? "Extracting..." : "⚡ Auto-Fill Form"}
                  </button>
                </div>

                <div className="sample-prompts">
                  <span className="sample-label">Try sample:</span>
                  <button
                    type="button"
                    className="sample-chip"
                    onClick={() =>
                      setAiText(
                        "I am Rahul Sharma, a 19-year-old SC student from Bihar, family income 2 lakh, email rahul.sharma@example.com, phone 9876543210"
                      )
                    }
                  >
                    🎓 19yo SC Student (Bihar, ₹2L)
                  </button>
                  <button
                    type="button"
                    className="sample-chip"
                    onClick={() =>
                      setAiText(
                        "I am Sunita Devi, a 42-year-old female farmer from Punjab, OBC category, 10th pass, annual income 1.5 lakh, email sunita.punjab@gmail.com"
                      )
                    }
                  >
                    🌾 42yo OBC Farmer (Punjab, ₹1.5L)
                  </button>
                </div>

                {aiMessage && <div className="ai-feedback">{aiMessage}</div>}
              </div>
            )}
          </section>
        )}

        {/* Global Server Error Banner */}
        {serverError && (
          <div className="alert alert-danger" role="alert">
            <strong>Error:</strong> {serverError}
          </div>
        )}

        {/* Multi-step Form Card */}
        {currentStep < 4 ? (
          <div className="form-card">
            {/* Step Progress Tracker */}
            <div className="stepper-bar">
              <div className={`step-item ${currentStep >= 1 ? "active" : ""} ${currentStep > 1 ? "completed" : ""}`}>
                <div className="step-number">{currentStep > 1 ? "✓" : "1"}</div>
                <div className="step-label">Personal Identity</div>
              </div>
              <div className="step-line" />
              <div className={`step-item ${currentStep >= 2 ? "active" : ""} ${currentStep > 2 ? "completed" : ""}`}>
                <div className="step-number">{currentStep > 2 ? "✓" : "2"}</div>
                <div className="step-label">Socio-Economic</div>
              </div>
              <div className="step-line" />
              <div className={`step-item ${currentStep >= 3 ? "active" : ""}`}>
                <div className="step-number">3</div>
                <div className="step-label">Contact & Review</div>
              </div>
            </div>

            <form onSubmit={handleSubmit} noValidate>
              {/* STEP 1: Personal Details */}
              {currentStep === 1 && (
                <div className="step-content">
                  <h2 className="step-heading">Step 1: Personal Identity</h2>
                  <p className="step-subheading">Enter the citizen's legal demographic details as per official ID.</p>

                  <div className="form-grid">
                    {/* Full Name */}
                    <div className="form-group full-width">
                      <label htmlFor="full_name">
                        Full Legal Name <span className="req">*</span>
                      </label>
                      <input
                        type="text"
                        id="full_name"
                        name="full_name"
                        value={formData.full_name}
                        onChange={handleChange}
                        placeholder="e.g. Rahul Kumar Sharma"
                        className={errors.full_name ? "input-error" : ""}
                      />
                      {errors.full_name && <span className="error-text">{errors.full_name}</span>}
                    </div>

                    {/* Age */}
                    <div className="form-group">
                      <label htmlFor="age">
                        Age (0 - 120 yrs) <span className="req">*</span>
                      </label>
                      <input
                        type="number"
                        id="age"
                        name="age"
                        min="0"
                        max="120"
                        value={formData.age}
                        onChange={handleChange}
                        placeholder="e.g. 19"
                        className={errors.age ? "input-error" : ""}
                      />
                      {errors.age && <span className="error-text">{errors.age}</span>}
                    </div>

                    {/* Gender Radio Buttons */}
                    <div className="form-group">
                      <label>
                        Gender <span className="req">*</span>
                      </label>
                      <div className="radio-group">
                        <label className="radio-label">
                          <input
                            type="radio"
                            name="gender"
                            value="male"
                            checked={formData.gender === "male"}
                            onChange={handleChange}
                          />
                          Male
                        </label>
                        <label className="radio-label">
                          <input
                            type="radio"
                            name="gender"
                            value="female"
                            checked={formData.gender === "female"}
                            onChange={handleChange}
                          />
                          Female
                        </label>
                        <label className="radio-label">
                          <input
                            type="radio"
                            name="gender"
                            value="other"
                            checked={formData.gender === "other"}
                            onChange={handleChange}
                          />
                          Other
                        </label>
                      </div>
                      {errors.gender && <span className="error-text">{errors.gender}</span>}
                    </div>

                    {/* State Dropdown */}
                    <div className="form-group full-width">
                      <label htmlFor="state">
                        State / Union Territory <span className="req">*</span>
                      </label>
                      <select
                        id="state"
                        name="state"
                        value={formData.state}
                        onChange={handleChange}
                        className={errors.state ? "input-error" : ""}
                      >
                        <option value="">-- Select State or UT --</option>
                        {INDIAN_STATES_AND_UTS.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                      {errors.state && <span className="error-text">{errors.state}</span>}
                    </div>
                  </div>

                  <div className="form-actions right">
                    <button type="button" className="btn-primary" onClick={handleNext}>
                      Continue to Socio-Economic →
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 2: Socio-Economic Profile */}
              {currentStep === 2 && (
                <div className="step-content">
                  <h2 className="step-heading">Step 2: Socio-Economic & Eligibility Parameters</h2>
                  <p className="step-subheading">
                    These metrics determine welfare entitlement thresholds (BPL, scholarship brackets, affirmative quotas).
                  </p>

                  <div className="form-grid">
                    {/* Annual Income */}
                    <div className="form-group">
                      <label htmlFor="annual_income">
                        Annual Household Income (in ₹) <span className="req">*</span>
                      </label>
                      <div className="input-prefix-wrapper">
                        <span className="input-prefix">₹</span>
                        <input
                          type="number"
                          id="annual_income"
                          name="annual_income"
                          min="0"
                          step="1000"
                          value={formData.annual_income}
                          onChange={handleChange}
                          placeholder="e.g. 200000"
                          className={errors.annual_income ? "input-error has-prefix" : "has-prefix"}
                        />
                      </div>
                      <small className="field-hint">e.g. 2 Lakh = 200,000</small>
                      {errors.annual_income && <span className="error-text">{errors.annual_income}</span>}
                    </div>

                    {/* Caste Category Dropdown */}
                    <div className="form-group">
                      <label htmlFor="caste_category">
                        Caste Category <span className="req">*</span>
                      </label>
                      <select
                        id="caste_category"
                        name="caste_category"
                        value={formData.caste_category}
                        onChange={handleChange}
                        className={errors.caste_category ? "input-error" : ""}
                      >
                        <option value="general">General (Open / Unreserved)</option>
                        <option value="obc">OBC (Other Backward Class)</option>
                        <option value="sc">SC (Scheduled Caste)</option>
                        <option value="st">ST (Scheduled Tribe)</option>
                      </select>
                      {errors.caste_category && <span className="error-text">{errors.caste_category}</span>}
                    </div>

                    {/* Education Level Dropdown */}
                    <div className="form-group">
                      <label htmlFor="education_level">
                        Education Level <span className="req">*</span>
                      </label>
                      <select
                        id="education_level"
                        name="education_level"
                        value={formData.education_level}
                        onChange={handleChange}
                        className={errors.education_level ? "input-error" : ""}
                      >
                        <option value="10th">10th Standard (Matriculation)</option>
                        <option value="12th">12th Standard (Higher Secondary)</option>
                        <option value="graduate">Graduate (Bachelor's / Diploma)</option>
                        <option value="postgraduate">Postgraduate (Master's / Ph.D.)</option>
                      </select>
                      {errors.education_level && <span className="error-text">{errors.education_level}</span>}
                    </div>

                    {/* Occupation Dropdown */}
                    <div className="form-group">
                      <label htmlFor="occupation">
                        Primary Occupation <span className="req">*</span>
                      </label>
                      <select
                        id="occupation"
                        name="occupation"
                        value={formData.occupation}
                        onChange={handleChange}
                        className={errors.occupation ? "input-error" : ""}
                      >
                        <option value="student">Student</option>
                        <option value="farmer">Farmer (Kisan / Agriculture)</option>
                        <option value="laborer">Laborer (Daily Wage / Construction)</option>
                        <option value="self_employed">Self Employed / Artisan / Business</option>
                        <option value="other">Other</option>
                      </select>
                      {errors.occupation && <span className="error-text">{errors.occupation}</span>}
                    </div>
                  </div>

                  <div className="form-actions space-between">
                    <button type="button" className="btn-secondary" onClick={handlePrev}>
                      ← Back
                    </button>
                    <button type="button" className="btn-primary" onClick={handleNext}>
                      Continue to Contact & Review →
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 3: Contact & Review */}
              {currentStep === 3 && (
                <div className="step-content">
                  <h2 className="step-heading">Step 3: Contact & Final Review</h2>
                  <p className="step-subheading">Verify contact details for SMS/Email notifications on scheme progress.</p>

                  <div className="form-grid">
                    {/* Email */}
                    <div className="form-group">
                      <label htmlFor="email">
                        Email Address <span className="req">*</span>
                      </label>
                      <input
                        type="email"
                        id="email"
                        name="email"
                        value={formData.email}
                        onChange={handleChange}
                        placeholder="e.g. citizen@example.com"
                        className={errors.email ? "input-error" : ""}
                      />
                      <small className="field-hint">Unique identifier used for scheme notifications.</small>
                      {errors.email && <span className="error-text">{errors.email}</span>}
                    </div>

                    {/* Phone */}
                    <div className="form-group">
                      <label htmlFor="phone">
                        Mobile Number <span className="optional">(Optional)</span>
                      </label>
                      <input
                        type="tel"
                        id="phone"
                        name="phone"
                        maxLength="10"
                        value={formData.phone}
                        onChange={handleChange}
                        placeholder="10-digit number e.g. 9876543210"
                        className={errors.phone ? "input-error" : ""}
                      />
                      <small className="field-hint">10 digits, starts with 6, 7, 8, or 9.</small>
                      {errors.phone && <span className="error-text">{errors.phone}</span>}
                    </div>
                  </div>

                  {/* Summary Review Card */}
                  <div className="review-box">
                    <h3 className="review-title">Summary Review</h3>
                    <div className="review-grid">
                      <div>
                        <strong>Name:</strong> {formData.full_name || "-"}
                      </div>
                      <div>
                        <strong>Age / Gender:</strong> {formData.age || "-"} yrs / {formData.gender}
                      </div>
                      <div>
                        <strong>State:</strong> {formData.state || "-"}
                      </div>
                      <div>
                        <strong>Annual Income:</strong> ₹
                        {formData.annual_income ? Number(formData.annual_income).toLocaleString("en-IN") : "0"}
                      </div>
                      <div>
                        <strong>Caste:</strong> {formData.caste_category.toUpperCase()}
                      </div>
                      <div>
                        <strong>Education:</strong> {formData.education_level}
                      </div>
                      <div>
                        <strong>Occupation:</strong> {formData.occupation}
                      </div>
                      <div>
                        <strong>Email:</strong> {formData.email || "-"}
                      </div>
                    </div>
                  </div>

                  <div className="form-actions space-between">
                    <button type="button" className="btn-secondary" onClick={handlePrev} disabled={isSubmitting}>
                      ← Back
                    </button>
                    <button type="submit" className="btn-submit" disabled={isSubmitting}>
                      {isSubmitting ? "Submitting to Database..." : "💾 Register Profile (Stage 1 Complete)"}
                    </button>
                  </div>
                </div>
              )}
            </form>
          </div>
        ) : (
          /* STEP 4: Success Confirmation */
          <div className="success-card">
            <div className="success-icon">✓</div>
            <h2 className="success-title">Profile Successfully Created & Stored!</h2>
            <p className="success-desc">
              Citizen record has been validated and persisted to SQLite (<code>profiles.db</code>).
            </p>

            <div className="profile-id-badge">
              <span className="badge-label">Generated Profile ID</span>
              <span className="badge-value">#{createdProfile?.id}</span>
            </div>

            <div className="details-table-wrapper">
              <table className="details-table">
                <tbody>
                  <tr>
                    <th>Full Name</th>
                    <td>{createdProfile?.full_name}</td>
                    <th>Age / Gender</th>
                    <td>
                      {createdProfile?.age} yrs ({createdProfile?.gender})
                    </td>
                  </tr>
                  <tr>
                    <th>State</th>
                    <td>{createdProfile?.state}</td>
                    <th>Annual Income</th>
                    <td>₹{Number(createdProfile?.annual_income).toLocaleString("en-IN")}</td>
                  </tr>
                  <tr>
                    <th>Caste Category</th>
                    <td>
                      <span className="tag-caste">{createdProfile?.caste_category?.toUpperCase()}</span>
                    </td>
                    <th>Education</th>
                    <td>{createdProfile?.education_level}</td>
                  </tr>
                  <tr>
                    <th>Occupation</th>
                    <td>{createdProfile?.occupation}</td>
                    <th>Contact</th>
                    <td>
                      {createdProfile?.email}
                      {createdProfile?.phone ? ` | +91 ${createdProfile?.phone}` : ""}
                    </td>
                  </tr>
                  <tr>
                    <th>Database Record</th>
                    <td colSpan="3">
                      Registered at {new Date(createdProfile?.created_at).toLocaleString()} | Indexed on Email
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Stage 2 Hand-off Information */}
            <div className="stage-handoff-alert">
              <div className="handoff-title">🚀 Ready for Stage 2 Integration</div>
              <p>
                This profile data is now primed for the <strong>TinyFish Web Agent</strong>. In Stage 2, TinyFish
                will use Profile ID <code>#{createdProfile?.id}</code> to automatically navigate government portals,
                bypass CAPTCHA/OTP verification checkpoints, and complete scheme application workflows.
              </p>
            </div>

            <div className="success-actions">
              <button
                type="button"
                className="btn-primary"
                onClick={() => setActiveTab("schemes")}
              >
                🎯 View Matching Schemes & Auto-Apply →
              </button>
              <button className="btn-secondary" onClick={handleReset}>
                + Register Another Citizen Profile
              </button>
              <button className="btn-secondary" onClick={fetchProfiles}>
                📋 Inspect All Database Profiles
              </button>
            </div>
          </div>
        )}
          </>
        )}

        {/* Admin Drawer Modal */}
        {showAdminDrawer && (
          <div className="modal-backdrop" onClick={() => setShowAdminDrawer(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>Registered Citizen Profiles (SQLite: <code>profiles.db</code>)</h3>
                <button className="btn-close" onClick={() => setShowAdminDrawer(false)}>
                  ✕
                </button>
              </div>
              <div className="modal-body">
                {isLoadingProfiles ? (
                  <p>Loading database records...</p>
                ) : adminProfiles.length === 0 ? (
                  <p>No profiles found in database yet.</p>
                ) : (
                  <div className="table-responsive">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Name</th>
                          <th>Age/Gender</th>
                          <th>State</th>
                          <th>Income (₹)</th>
                          <th>Caste</th>
                          <th>Occupation</th>
                          <th>Email</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adminProfiles.map((p) => (
                          <tr key={p.id}>
                            <td>
                              <strong>#{p.id}</strong>
                            </td>
                            <td>{p.full_name}</td>
                            <td>
                              {p.age} / {p.gender}
                            </td>
                            <td>{p.state}</td>
                            <td>₹{Number(p.annual_income).toLocaleString("en-IN")}</td>
                            <td>
                              <span className="badge-sm">{p.caste_category.toUpperCase()}</span>
                            </td>
                            <td>{p.occupation}</td>
                            <td>{p.email}</td>
                            <td>
                              <button
                                type="button"
                                className="btn-select-profile"
                                onClick={() => {
                                  setSavedProfileId(p.id);
                                  setActiveTab("schemes");
                                  setShowAdminDrawer(false);
                                }}
                              >
                                🎯 Match Schemes
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button className="btn-secondary" onClick={() => setShowAdminDrawer(false)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="gov-footer">
        <p>Government Scheme Auto-Apply Agent | Hackathon Project Stage 1</p>
      </footer>
    </div>
  );
}
