import React, { useState } from 'react';
import { getApiBase } from '../config';
import { IconSearch, IconBolt, IconEye, IconRocket, IconClipboard, IconCheck, IconAlert } from './Icons';

const PRESET_REQUIREMENTS = [
  "Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. Python, FastAPI, Machine Learning and NLP are mandatory. Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days.",
  "Senior Full Stack React and Node.js developer in Bengaluru with 4 to 8 years experience. AWS and Docker required. Budget 18 to 30 LPA.",
  "DevOps Cloud Engineer in Pune or Mumbai with Kubernetes, Terraform, and CI/CD pipelines. 3 to 6 years experience.",
];

export default function SearchAgentView() {
  const API_BASE = getApiBase();
  const [prompt, setPrompt] = useState(PRESET_REQUIREMENTS[0]);
  const [executeMode, setExecuteMode] = useState('dry_run'); // 'dry_run', 'inspection', 'submit'
  const [isLoading, setIsLoading] = useState(false);
  const [searchResponse, setSearchResponse] = useState(null);
  const [error, setError] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setIsLoading(true);
    setError(null);
    setSearchResponse(null);

    const payload = {
      requirement: prompt.trim(),
      execute: executeMode !== 'dry_run',
      submit_search: executeMode === 'submit',
    };

    try {
      const resp = await fetch(`${API_BASE}/search/candidates`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.message || errJson.detail || `HTTP Error ${resp.status}`);
      }

      const data = await resp.json();
      setSearchResponse(data);
    } catch (err) {
      console.error('Search request failed:', err);
      setError(err.message || 'Failed to execute search. Check backend connection.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <div className="hero-section">
        <h1 className="hero-title">Naukri Resdex Candidate Search Agent</h1>
        <p className="hero-desc">
          Schema-driven autonomous recruitment intelligence. Type your natural-language candidate criteria
          below. The agent validates against the live Resdex schema and deterministically fills the search form.
        </p>
      </div>

      <div className="card">
        <h2 className="card-title">
          <IconSearch size={22} color="var(--primary)" />
          <span>Recruiter Requirement Criteria</span>
        </h2>
        <p className="card-subtitle">Select a preset or enter custom hiring requirements.</p>

        {/* Preset Chips */}
        <div className="preset-chips">
          {PRESET_REQUIREMENTS.map((req, i) => (
            <button
              key={i}
              type="button"
              className="preset-chip"
              onClick={() => setPrompt(req)}
            >
              Preset {i + 1}: {req.slice(0, 48)}...
            </button>
          ))}
        </div>

        <form onSubmit={handleSearch}>
          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label className="form-label">Requirement Prompt</label>
            <textarea
              className="form-textarea"
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Find Python developers in Hyderabad with 3 to 6 years experience..."
            />
          </div>

          {/* Execution Mode Selector */}
          <div className="form-row" style={{ marginBottom: '24px' }}>
            <div className="form-group">
              <label className="form-label">Execution Mode</label>
              <div className="execution-mode-selector">
                <label className={`mode-option-card ${executeMode === 'dry_run' ? 'active-dry' : ''}`}>
                  <input
                    type="radio"
                    name="mode"
                    value="dry_run"
                    checked={executeMode === 'dry_run'}
                    onChange={() => setExecuteMode('dry_run')}
                  />
                  <span className="mode-option-content">
                    <IconBolt size={15} color="var(--primary)" />
                    <span>Dry-Run Plan Only</span>
                  </span>
                </label>

                <label className={`mode-option-card ${executeMode === 'inspection' ? 'active-inspection' : ''}`}>
                  <input
                    type="radio"
                    name="mode"
                    value="inspection"
                    checked={executeMode === 'inspection'}
                    onChange={() => setExecuteMode('inspection')}
                  />
                  <span className="mode-option-content">
                    <IconEye size={15} color="var(--accent-emerald)" />
                    <span>Visual Form Fill (Inspection)</span>
                  </span>
                </label>

                <label className={`mode-option-card ${executeMode === 'submit' ? 'active-submit' : ''}`}>
                  <input
                    type="radio"
                    name="mode"
                    value="submit"
                    checked={executeMode === 'submit'}
                    onChange={() => setExecuteMode('submit')}
                  />
                  <span className="mode-option-content">
                    <IconRocket size={15} color="var(--accent-amber)" />
                    <span>Live Submit Search</span>
                  </span>
                </label>
              </div>
            </div>
          </div>

          {error && (
            <div style={{
              background: 'rgba(244, 63, 94, 0.12)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              color: '#FDA4AF',
              padding: '12px 16px',
              borderRadius: '8px',
              marginBottom: '20px',
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <IconAlert size={18} color="#FDA4AF" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="btn-primary-action"
            disabled={isLoading || !prompt.trim()}
          >
            {isLoading ? (
              <>
                <div className="spinner"></div>
                <span>Executing Agent Strategy...</span>
              </>
            ) : (
              <>
                <IconBolt size={18} color="#FFFFFF" />
                <span>
                  {executeMode === 'dry_run' && 'Generate & Validate SearchPlan'}
                  {executeMode === 'inspection' && 'Launch Chrome & Fill Resdex Form (Inspection)'}
                  {executeMode === 'submit' && 'Execute Live Resdex Candidate Search'}
                </span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Results View */}
      {searchResponse && (
        <div className="card">
          <h3 className="card-title">
            <IconClipboard size={20} color="var(--primary)" />
            <span>Generated SearchPlan & Execution Status</span>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '3px 10px',
              borderRadius: '999px',
              background: searchResponse.validation.valid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
              color: searchResponse.validation.valid ? '#10B981' : '#F43F5E',
              border: `1px solid ${searchResponse.validation.valid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`
            }}>
              {searchResponse.validation.valid ? 'VALIDATED SCHEMA' : 'SCHEMA ERRORS'}
            </span>
          </h3>

          {searchResponse.execution.executed && (
            <div style={{
              background: 'rgba(56, 189, 248, 0.08)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              padding: '16px',
              borderRadius: '8px',
              marginBottom: '16px'
            }}>
              <div style={{ fontWeight: 700, color: 'var(--primary)', marginBottom: '4px' }}>
                Selenium Execution Report
              </div>
              <div style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                {searchResponse.execution.message}
              </div>
              {searchResponse.execution.fields_interacted?.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {searchResponse.execution.fields_interacted.map((f, i) => (
                    <span key={i} className="skill-pill" style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <IconCheck size={11} color="var(--accent-emerald)" />
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="code-box">
            {JSON.stringify(searchResponse.search_plan, null, 2)}
          </div>
        </div>
      )}
    </div>
  );
}
