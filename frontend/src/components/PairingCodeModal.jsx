import React, { useEffect, useState } from 'react';
import { getApiBase, apiFetch } from '../config';
import { IconClose, IconCopy, IconCheck } from './Icons';

export default function PairingCodeModal({ onClose }) {
  const API_BASE = getApiBase();
  const [code, setCode] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const requestCode = async () => {
    setError('');
    setCode(null);
    try {
      const resp = await apiFetch(`${API_BASE}/auth/pairing-code`, { method: 'POST' });
      if (!resp.ok) {
        setError('Could not generate a pairing code. Try again.');
        return;
      }
      const data = await resp.json();
      setCode(data.code);
      setSecondsLeft(data.expires_in_seconds);
    } catch {
      setError('Could not reach the server.');
    }
  };

  useEffect(() => { requestCode(); }, []);

  useEffect(() => {
    if (!code || secondsLeft <= 0) return;
    const t = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [code, secondsLeft]);

  const handleCopy = () => {
    if (!code) return;
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const mins = Math.floor(secondsLeft / 60);
  const secs = String(secondsLeft % 60).padStart(2, '0');
  const expired = code && secondsLeft <= 0;

  return (
    <div className="converter-modal-backdrop" onClick={onClose}>
      <div className="converter-modal-content pairing-code-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="converter-modal-header">
          <div className="modal-title-wrap">
            <h3>Pair the Chrome extension</h3>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose}>
            <IconClose size={16} />
          </button>
        </div>

        <div className="converter-modal-body">
          <p className="modal-subheading">
            Open the extension popup and paste this code. It expires in a few minutes.
          </p>

          {error ? (
            <div className="login-error" style={{ marginTop: 12 }}>{error}</div>
          ) : code && !expired ? (
            <>
              <div className="pairing-code-display">
                <span className="pairing-code-text">{code}</span>
                <button type="button" className="btn-secondary" onClick={handleCopy}>
                  {copied ? <IconCheck size={14} color="#10B981" /> : <IconCopy size={14} />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <div className="pairing-code-timer">Expires in {mins}:{secs}</div>
            </>
          ) : expired ? (
            <div className="pairing-code-timer" style={{ color: '#EF4444' }}>
              This code expired.
            </div>
          ) : (
            <div className="pairing-code-timer">Generating code…</div>
          )}

          <button type="button" className="btn-secondary" style={{ marginTop: 16, width: '100%' }} onClick={requestCode}>
            Generate a new code
          </button>
        </div>
      </div>
    </div>
  );
}
