import React, { useState } from 'react';
import { getApiBase, setApiBase } from '../config';

export default function Header() {
  const [currentBase, setCurrentBase] = useState(getApiBase());
  const [showConfig, setShowConfig] = useState(false);
  const [inputVal, setInputVal] = useState(currentBase);

  const handleSave = () => {
    const clean = inputVal.trim();
    if (clean) {
      setApiBase(clean);
      setCurrentBase(clean);
      setShowConfig(false);
      window.location.reload();
    }
  };

  return (
    <header className="header">
      {/* Search Input with ⌘ K */}
      <div className="header-search">
        <svg className="search-icon-left" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          className="search-input"
          placeholder="Search candidates, roles or documents..."
        />
        <span className="search-badge-right">⌘ K</span>
      </div>

      {/* Header Right (Notifications & Recruiter Profile) */}
      <div className="header-right">
        <button
          type="button"
          className="bell-btn"
          title="Notifications"
          aria-label="Notifications"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          <span className="bell-dot"></span>
        </button>

        {/* Recruiter Profile / Backend Config Toggle */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            className="user-profile-btn"
            onClick={() => setShowConfig(!showConfig)}
          >
            <div className="user-avatar">R</div>
            <span className="user-name">Recruiter</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {showConfig && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: '46px',
              background: '#FFFFFF',
              border: '1px solid #E2E8F0',
              borderRadius: '10px',
              padding: '14px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.08)',
              width: '260px',
              zIndex: 100,
            }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '8px' }}>
                BACKEND API CONFIG
              </div>
              <input
                type="text"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  fontSize: '0.82rem',
                  marginBottom: '10px'
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setShowConfig(false)}
                  style={{ background: 'none', border: 'none', fontSize: '0.8rem', color: '#64748B', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  style={{
                    background: '#4F46E5',
                    color: '#FFFFFF',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '4px 12px',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Save
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
