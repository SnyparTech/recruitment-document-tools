import React, { useState } from 'react';
import { getApiBase, setApiBase } from '../config';
import { IconTarget, IconUser, IconDocument, IconEdit, IconSparkles } from './Icons';

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
          title="Naukri Candidate Search"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <span className="tab-label-full">Candidates</span>
          <span className="tab-label-short">Search</span>
        </button>

        <button
          type="button"
          className={`top-nav-tab ${activeTab === 'dossier' ? 'active' : ''}`}
          onClick={() => setActiveTab('dossier')}
          id="tab-dossier"
          title="Compile Candidate Dossier"
        >
          <IconDocument size={17} />
          <span className="tab-label-full">Dossier Compiler</span>
          <span className="tab-label-short">Dossier</span>
        </button>

        <button
          type="button"
          className={`top-nav-tab ${activeTab === 'resume-converter' ? 'active' : ''}`}
          onClick={() => setActiveTab('resume-converter')}
          id="tab-resume-converter"
          title="Convert Resume to LaTeX & DOCX"
        >
          <IconSparkles size={17} color={activeTab === 'resume-converter' ? '#6366F1' : 'currentColor'} />
          <span className="tab-label-full">AI Resume Converter</span>
          <span className="tab-label-short">Converter</span>
        </button>
      </div>

      {/* Right Side: Backend Connection & Edit */}
      <div className="nav-status-top">
        <span className="status-dot-green"></span>
        {isEditing ? (
          <div className="nav-status-edit-box">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Backend URL"
              className="nav-status-input"
            />
            <button
              onClick={handleSave}
              className="btn-nav-save"
            >
              Save
            </button>
            <button
              onClick={() => setIsEditing(false)}
              className="btn-nav-cancel"
            >
              ✕
            </button>
          </div>
        ) : (
          <div
            onClick={() => setIsEditing(true)}
            className="nav-status-label-wrap"
            title="Click to configure API backend endpoint"
          >
            <span className="nav-status-text">
              <span className="nav-status-prefix">Backend: </span>
              <strong className="nav-status-host">{currentBase ? currentBase.replace(/^https?:\/\//, '') : 'local'}</strong>
            </span>
            <IconEdit size={13} color="#4F46E5" />
          </div>
        )}
      </div>
    </header>
  );
}
