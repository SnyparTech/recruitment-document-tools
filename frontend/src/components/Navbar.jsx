import React, { useState } from 'react';
import { getApiBase, setApiBase } from '../config';
import { IconTarget, IconUser, IconDocument, IconEdit } from './Icons';

export default function Navbar({ activeTab, setActiveTab }) {
  const [currentBase, setCurrentBase] = useState(getApiBase());
  const [isEditing, setIsEditing] = useState(false);
  const [inputVal, setInputVal] = useState(currentBase);

  const handleSave = () => {
    const clean = inputVal.trim();
    if (clean) {
      setApiBase(clean);
      setCurrentBase(clean);
      setIsEditing(false);
      window.location.reload();
    }
  };

  return (
    <header className="navbar-top">
      {/* Brand */}
      <div className="nav-brand-top">
        <div className="brand-ring-icon" style={{ width: '32px', height: '32px' }}>
          <div className="brand-ring-inner" style={{ width: '18px', height: '18px' }}></div>
        </div>
        <div>
          <span className="brand-name" style={{ fontSize: '1.15rem' }}>Profile Bot AI</span>
        </div>
      </div>

      {/* Two Tab Navigation Options: Candidates & Dossier Compiler */}
      <div className="top-nav-tabs">
        <button
          type="button"
          className={`top-nav-tab ${activeTab === 'candidates' ? 'active' : ''}`}
          onClick={() => setActiveTab('candidates')}
          id="tab-candidates"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <span>Candidates</span>
        </button>

        <button
          type="button"
          className={`top-nav-tab ${activeTab === 'dossier' ? 'active' : ''}`}
          onClick={() => setActiveTab('dossier')}
          id="tab-dossier"
        >
          <IconDocument size={17} />
          <span>Dossier Compiler</span>
        </button>
      </div>

      {/* Right Side: Backend Connection & Edit */}
      <div className="nav-status-top">
        <span className="status-dot-green"></span>
        {isEditing ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              style={{
                background: '#FFFFFF',
                border: '1px solid #818CF8',
                color: '#1E293B',
                borderRadius: '6px',
                padding: '2px 8px',
                fontSize: '0.8rem',
                width: '170px',
              }}
            />
            <button
              onClick={handleSave}
              style={{
                background: '#4F46E5',
                border: 'none',
                color: '#FFFFFF',
                borderRadius: '6px',
                padding: '3px 10px',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Save
            </button>
          </div>
        ) : (
          <div
            onClick={() => setIsEditing(true)}
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            title="Click to change backend port"
          >
            <span>Backend: <strong style={{ color: '#1E293B' }}>{currentBase ? currentBase.replace(/^https?:\/\//, '') : 'local'}</strong></span>
            <IconEdit size={13} color="#4F46E5" />
          </div>
        )}
      </div>
    </header>
  );
}
