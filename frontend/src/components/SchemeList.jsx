import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

// Auto-detect backend host from current page (works for localhost AND remote IPs)
const API_BASE = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

export default function SchemeList({ profileId, onNavigateToProfile, onNavigateToTracker }) {
  const [matches, setMatches] = useState([]);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [applyingSchemeId, setApplyingSchemeId] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);

  // Live SSE stream state
  const [liveStream, setLiveStream] = useState(null);
  const eventSourceRef = useRef(null);

  const fetchMatchedSchemes = useCallback(async () => {
    if (!profileId) {
      setMatches([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Fetch eligible matched schemes
      const matchRes = await axios.get(`${API_BASE}/api/match/${profileId}`);
      setMatches(matchRes.data);

      // Fetch any past applications for this profile
      try {
        const appRes = await axios.get(`${API_BASE}/api/applications/${profileId}`);
        setApplications(appRes.data);
      } catch (appErr) {
        console.warn("Could not load application history:", appErr);
      }
    } catch (err) {
      console.error("Failed to fetch matching schemes:", err);
      const detail = err.response?.data?.detail || err.message || "Network error fetching schemes.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    fetchMatchedSchemes();
  }, [fetchMatchedSchemes]);

  // Clean up SSE connection on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleApply = async (scheme) => {
    if (!profileId) {
      alert("No active profile ID. Please create a citizen profile first.");
      return;
    }

    // Close any previous stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setApplyingSchemeId(scheme.id);
    setStatusMessage(null);
    setLiveStream({
      schemeId: scheme.id,
      schemeName: scheme.name,
      status: "initiating",
      stepText: "Connecting to agent scheduler...",
      mode: "evaluating",
    });

    try {
      const response = await axios.post(`${API_BASE}/api/apply`, {
        profile_id: profileId,
        scheme_id: scheme.id,
      });

      const appId = response.data.application_id;
      const initialMode = response.data.mode || "live";

      setLiveStream((prev) => ({
        ...prev,
        applicationId: appId,
        status: response.data.status || "pending",
        mode: initialMode,
        stepText: response.data.message || `Application initiated for ${scheme.name}...`,
      }));

      // Start SSE stream for real-time live events
      const es = new EventSource(`${API_BASE}/api/apply/stream/${appId}`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.error) {
            setLiveStream((prev) => ({
              ...prev,
              status: "failed",
              stepText: payload.error,
            }));
            es.close();
            setApplyingSchemeId(null);
            return;
          }

          setLiveStream((prev) => ({
            ...prev,
            status: payload.status,
            mode: payload.mode || prev.mode,
            tinyfishRunId: payload.tinyfish_run_id,
            screenshotUrl: payload.screenshot_url,
            errorMessage: payload.error_message,
            stepText:
              payload.status === "running"
                ? `Agent active: Navigating portal & auto-filling form fields (${payload.mode === "dry_run" ? "Dry-Run" : "Live"})...`
                : payload.status === "submitted"
                ? `✓ Submission completed successfully!`
                : payload.status === "dry_run"
                ? `🧪 Form filled & screenshot captured! (Stopped before submit as per dry-run policy)`
                : payload.status === "failed"
                ? `Application halted: ${payload.error_message || "Agent error"}`
                : `Status: ${payload.status}`,
          }));

          // Terminal status reached: close event source and refresh
          if (["submitted", "dry_run", "failed"].includes(payload.status)) {
            es.close();
            setApplyingSchemeId(null);
            // Refresh applications list
            axios
              .get(`${API_BASE}/api/applications/${profileId}`)
              .then((res) => setApplications(res.data))
              .catch(() => {});
          }
        } catch (e) {
          console.error("SSE parse error:", e);
        }
      };

      es.onerror = () => {
        console.warn("SSE connection closed or timed out.");
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }
        setApplyingSchemeId(null);
      };
    } catch (err) {
      console.error("Apply error:", err);
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        "Failed to auto-apply to scheme.";
      setStatusMessage({ type: "error", text: errorMsg });
      setLiveStream(null);
      setApplyingSchemeId(null);
      alert(`Auto-Apply Error: ${errorMsg}`);
    }
  };

  // Helper to check if scheme is already applied
  const getExistingApp = (schemeId) => {
    return applications.find((a) => a.scheme_id === schemeId);
  };

  return (
    <div className="scheme-list-container">
      {/* Header Bar */}
      <div className="schemes-header-bar">
        <div>
          <h2 className="schemes-title">🎯 Eligible Government Schemes</h2>
          <p className="schemes-subtitle">
            {profileId ? (
              <>
                Showing personalized matches for <strong>Citizen Profile #{profileId}</strong> based on age, income, caste, domicile, and occupation.
              </>
            ) : (
              "Create or select a citizen profile to discover eligible welfare schemes."
            )}
          </p>
        </div>

        {profileId && (
          <button
            type="button"
            className="btn-refresh"
            onClick={fetchMatchedSchemes}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "🔄 Re-evaluate Matches"}
          </button>
        )}
      </div>

      {/* SSE Live Streaming Toast Banner (Task C4) */}
      {liveStream && (
        <div className={`sse-live-banner status-${liveStream.status}`}>
          <div className="sse-header">
            <div className="sse-title">
              {liveStream.status === "running" || liveStream.status === "initiating" || liveStream.status === "pending" ? (
                <span className="sse-spinner" />
              ) : liveStream.status === "submitted" ? (
                <span className="sse-icon success">✓</span>
              ) : liveStream.status === "dry_run" ? (
                <span className="sse-icon dry">🧪</span>
              ) : (
                <span className="sse-icon fail">⚠️</span>
              )}
              <strong>TinyFish Agent Live Stream: {liveStream.schemeName}</strong>
              <span className={`mode-pill ${liveStream.mode === "dry_run" ? "mode-dry-run" : "mode-live"}`}>
                {liveStream.mode === "dry_run" ? "DRY-RUN MODE" : "LIVE MODE"}
              </span>
            </div>

            <button
              type="button"
              className="btn-dismiss"
              onClick={() => {
                if (eventSourceRef.current) eventSourceRef.current.close();
                setLiveStream(null);
              }}
            >
              ✕
            </button>
          </div>

          <div className="sse-body">
            <p className="sse-text">{liveStream.stepText}</p>
            {liveStream.tinyfishRunId && (
              <div className="sse-run-id">
                TinyFish Run ID: <code>{liveStream.tinyfishRunId}</code>
              </div>
            )}
            {liveStream.screenshotUrl && (
              <div className="sse-screenshot-preview">
                <a
                  href={liveStream.screenshotUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-screenshot-link"
                >
                  📸 View Full Captured Form Screenshot ↗
                </a>
              </div>
            )}
          </div>

          {onNavigateToTracker && ["submitted", "dry_run", "failed"].includes(liveStream.status) && (
            <div className="sse-footer">
              <button
                type="button"
                className="btn-link-action"
                onClick={onNavigateToTracker}
              >
                View in Application Tracker Dashboard →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Global Status Message */}
      {statusMessage && (
        <div className={`alert ${statusMessage.type === "error" ? "alert-danger" : "alert-success"}`}>
          {statusMessage.text}
        </div>
      )}

      {/* NO PROFILE SELECTED STATE */}
      {!profileId && (
        <div className="empty-state-card">
          <div className="empty-state-icon">📋</div>
          <h3>No Citizen Profile Selected</h3>
          <p>
            Please complete and submit the 3-step citizen registration form first.
            Once saved, our matching engine will automatically evaluate your eligibility against all central and state schemes.
          </p>
          {onNavigateToProfile && (
            <button
              type="button"
              className="btn-primary"
              onClick={onNavigateToProfile}
            >
              Go to Citizen Profile Form →
            </button>
          )}
        </div>
      )}

      {/* LOADING STATE */}
      {loading && profileId && (
        <div className="loading-card">
          <div className="spinner" />
          <p>Evaluating eligibility criteria against official scheme database...</p>
        </div>
      )}

      {/* ERROR STATE */}
      {error && !loading && (
        <div className="alert alert-danger">
          <strong>Error Loading Schemes:</strong> {error}
          <div style={{ marginTop: "10px" }}>
            <button type="button" className="btn-secondary-sm" onClick={fetchMatchedSchemes}>
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* EMPTY RESULTS STATE */}
      {!loading && !error && profileId && matches.length === 0 && (
        <div className="empty-state-card">
          <div className="empty-state-icon">🔍</div>
          <h3>No Qualifying Schemes Found</h3>
          <p>
            Based on the current profile parameters (income, age, occupation, caste), no scheme criteria were fully satisfied.
            You can edit your profile details in the <strong>Profile tab</strong> to re-evaluate.
          </p>
        </div>
      )}

      {/* SCHEME CARDS GRID */}
      {!loading && !error && matches.length > 0 && (
        <div className="schemes-grid">
          {matches.map(({ scheme, match_score, matched_criteria }) => {
            const existingApp = getExistingApp(scheme.id);
            const scorePercent = Math.round(match_score * 100);

            return (
              <div key={scheme.id} className="scheme-card">
                {/* Scheme Header */}
                <div className="scheme-card-header">
                  <div className="scheme-title-group">
                    <span className="category-pill">{scheme.category}</span>
                    <h3 className="scheme-name">{scheme.name}</h3>
                    {scheme.ministry && (
                      <span className="ministry-text">🏛️ {scheme.ministry}</span>
                    )}
                  </div>

                  <div className="score-badge" title="Eligibility Match Score">
                    <span className="score-num">{scorePercent}%</span>
                    <span className="score-lbl">Match</span>
                  </div>
                </div>

                {/* Description */}
                <p className="scheme-desc">{scheme.description}</p>

                {/* Eligibility Summary */}
                <div className="eligibility-box">
                  <strong>Eligibility Summary:</strong> {scheme.eligibility_text}
                </div>

                {/* Matched Criteria List */}
                <div className="matched-criteria-section">
                  <h4 className="criteria-heading">Matched Criteria:</h4>
                  <ul className="criteria-list">
                    {matched_criteria.map((crit, idx) => (
                      <li key={idx} className="criteria-item">
                        <span className="check-icon">✓</span> {crit}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Existing Application Status if available */}
                {existingApp && (
                  <div className={`app-status-badge status-${existingApp.status}`}>
                    <span>
                      Application Status: <strong>{existingApp.status.toUpperCase()}</strong>
                      {existingApp.mode ? ` [${existingApp.mode.toUpperCase()}]` : ""}
                      {existingApp.tinyfish_run_id ? ` (Run ID: ${existingApp.tinyfish_run_id})` : ""}
                    </span>
                    {existingApp.error_message && (
                      <div className="app-error-note">Note: {existingApp.error_message}</div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="scheme-card-actions">
                  <a
                    href={scheme.official_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-learn-more"
                  >
                    Learn More ↗
                  </a>

                  <button
                    type="button"
                    className="btn-auto-apply"
                    onClick={() => handleApply(scheme)}
                    disabled={applyingSchemeId === scheme.id || (existingApp && (existingApp.status === "submitted" || existingApp.status === "running"))}
                  >
                    {applyingSchemeId === scheme.id
                      ? "⏳ Launching TinyFish..."
                      : existingApp && existingApp.status === "submitted"
                      ? "✓ Auto-Applied"
                      : existingApp && existingApp.status === "running"
                      ? "⏳ Agent Running..."
                      : "🚀 Auto-Apply via TinyFish"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
