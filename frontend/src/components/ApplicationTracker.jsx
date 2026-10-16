import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

export default function ApplicationTracker({ profileId, onNavigateToSchemes }) {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedScreenshot, setSelectedScreenshot] = useState(null);
  const pollTimerRef = useRef(null);

  const fetchApplications = useCallback(async (isPolling = false) => {
    if (!profileId) {
      setApplications([]);
      setLoading(false);
      return;
    }

    if (!isPolling) setLoading(true);
    setError(null);

    try {
      const res = await axios.get(`${API_BASE}/api/applications/${profileId}/detailed`);
      setApplications(res.data);
    } catch (err) {
      console.error("Failed to load applications:", err);
      if (!isPolling) {
        setError(err.response?.data?.detail || err.message || "Failed to fetch applications.");
      }
    } finally {
      if (!isPolling) setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  // Auto-refresh every 5s if any application is in 'running' or 'pending' state
  useEffect(() => {
    const hasActiveTask = applications.some(
      (app) => app.status === "running" || app.status === "pending"
    );

    if (hasActiveTask) {
      pollTimerRef.current = setTimeout(() => {
        fetchApplications(true);
      }, 5000);
    }

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, [applications, fetchApplications]);

  const getStatusBadge = (status) => {
    const s = (status || "").toLowerCase();
    switch (s) {
      case "submitted":
        return <span className="app-badge badge-submitted">✓ Submitted</span>;
      case "dry_run":
        return <span className="app-badge badge-dry-run">🧪 Dry-Run (Verified)</span>;
      case "running":
        return (
          <span className="app-badge badge-running">
            <span className="badge-pulse" /> ⏳ Running
          </span>
        );
      case "failed":
        return <span className="app-badge badge-failed">✕ Failed</span>;
      case "pending":
      default:
        return <span className="app-badge badge-pending">⋯ Pending</span>;
    }
  };

  const getModeBadge = (mode) => {
    const m = (mode || "live").toLowerCase();
    if (m === "dry_run") {
      return <span className="mode-pill mode-dry-run">DRY RUN</span>;
    }
    return <span className="mode-pill mode-live">LIVE</span>;
  };

  return (
    <div className="tracker-container">
      {/* Tracker Header */}
      <div className="schemes-header-bar">
        <div>
          <h2 className="schemes-title">📄 Application Tracking Dashboard</h2>
          <p className="schemes-subtitle">
            {profileId ? (
              <>
                Monitoring scheme application runs and agent execution logs for{" "}
                <strong>Citizen Profile #{profileId}</strong>.
              </>
            ) : (
              "Select or register a citizen profile to view past and active scheme applications."
            )}
          </p>
        </div>

        {profileId && (
          <button
            type="button"
            className="btn-refresh"
            onClick={() => fetchApplications(false)}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "🔄 Refresh Status"}
          </button>
        )}
      </div>

      {/* ERROR BANNER */}
      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* NO PROFILE STATE */}
      {!profileId && (
        <div className="empty-state-card">
          <div className="empty-state-icon">📋</div>
          <h3>No Citizen Profile Selected</h3>
          <p>
            Please create a profile or select an existing citizen profile from the DB drawer to view their
            application submissions.
          </p>
        </div>
      )}

      {/* LOADING STATE */}
      {loading && profileId && (
        <div className="loading-card">
          <div className="spinner" />
          <p>Loading application logs and TinyFish statuses...</p>
        </div>
      )}

      {/* EMPTY APPLICATIONS STATE */}
      {!loading && profileId && applications.length === 0 && (
        <div className="empty-state-card">
          <div className="empty-state-icon">🚀</div>
          <h3>No Scheme Applications Yet</h3>
          <p>
            You haven't initiated any scheme applications for Profile #{profileId}. Browse eligible
            welfare programs and launch automated form filling.
          </p>
          {onNavigateToSchemes && (
            <button type="button" className="btn-primary" onClick={onNavigateToSchemes}>
              🎯 Go to My Schemes →
            </button>
          )}
        </div>
      )}

      {/* APPLICATIONS TABLE */}
      {!loading && applications.length > 0 && (
        <div className="tracker-table-card">
          <div className="table-responsive">
            <table className="tracker-table">
              <thead>
                <tr>
                  <th>App #</th>
                  <th>Scheme</th>
                  <th>Status</th>
                  <th>Mode</th>
                  <th>Created At</th>
                  <th>Run ID</th>
                  <th>Screenshot / Evidence</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id}>
                    <td>
                      <strong className="app-id">#{app.id}</strong>
                    </td>
                    <td>
                      <div className="scheme-cell">
                        <span className="category-pill-sm">{app.scheme_category}</span>
                        <a
                          href={app.official_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="scheme-link"
                        >
                          {app.scheme_name} ↗
                        </a>
                      </div>
                      {app.error_message && (
                        <div className="cell-error-note">⚠️ {app.error_message}</div>
                      )}
                    </td>
                    <td>{getStatusBadge(app.status)}</td>
                    <td>{getModeBadge(app.mode)}</td>
                    <td className="timestamp-cell">
                      {new Date(app.created_at).toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td>
                      {app.tinyfish_run_id ? (
                        <code className="run-id-pill" title={app.tinyfish_run_id}>
                          {app.tinyfish_run_id.length > 16
                            ? `${app.tinyfish_run_id.slice(0, 14)}…`
                            : app.tinyfish_run_id}
                        </code>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      {app.screenshot_url ? (
                        <button
                          type="button"
                          className="btn-screenshot"
                          onClick={() => setSelectedScreenshot(app.screenshot_url)}
                        >
                          📸 View Screenshot
                        </button>
                      ) : app.result_url ? (
                        <a
                          href={app.result_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="link-result"
                        >
                          🔗 Portal Result
                        </a>
                      ) : (
                        <span className="text-muted">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Screenshot Modal */}
      {selectedScreenshot && (
        <div className="modal-backdrop" onClick={() => setSelectedScreenshot(null)}>
          <div className="modal-content screenshot-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>TinyFish Agent - Pre-Submission Screenshot</h3>
              <button className="btn-close" onClick={() => setSelectedScreenshot(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body text-center">
              <img
                src={selectedScreenshot}
                alt="Form Filling Screenshot"
                className="screenshot-img"
              />
            </div>
            <div className="modal-footer">
              <a
                href={selectedScreenshot}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
              >
                Open in New Tab ↗
              </a>
              <button className="btn-secondary" onClick={() => setSelectedScreenshot(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
