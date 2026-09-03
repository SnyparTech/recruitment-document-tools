import React, { useState } from 'react';
import { getApiBase, setApiBase } from '../config';
import { IconTarget, IconEdit } from './Icons';

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
    <header className="navbar">
      <div className="nav-brand">
        <div className="brand-icon">
          <IconTarget size={22} color="var(--primary)" />
        </div>
        <div>
          <div className="brand-title">Profile Bot AI</div>
        </div>
        <span className="brand-badge">Enterprise</span>
      </div>

      <div className="nav-status">
        <span className="status-dot"></span>
        {isEditing ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--primary)',
                color: '#FFFFFF',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '0.8rem',
                width: '180px',
              }}
            />
            <button
              onClick={handleSave}
              style={{
                background: 'var(--primary)',
                border: 'none',
                color: '#FFFFFF',
                borderRadius: '4px',
                padding: '2px 8px',
                fontSize: '0.75rem',
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
            title="Click to edit backend port"
          >
            <span>Backend: <strong>{currentBase.replace('http://', '')}</strong></span>
            <IconEdit size={13} color="var(--primary)" />
          </div>
        )}
      </div>
    </header>
  );
}
