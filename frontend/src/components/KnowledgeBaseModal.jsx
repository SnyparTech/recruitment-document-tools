import React, { useEffect, useState } from 'react';
import { getApiBase, apiFetch } from '../config';
import { IconClose, IconAlert } from './Icons';

export default function KnowledgeBaseModal({ onClose }) {
  const API_BASE = getApiBase();
  const [facts, setFacts] = useState(null);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState(null);

  const loadFacts = async () => {
    setError('');
    try {
      const resp = await apiFetch(`${API_BASE}/search/knowledge`);
      if (!resp.ok) {
        setError('Could not load remembered facts.');
        return;
      }
      const data = await resp.json();
      setFacts(data.facts || []);
    } catch {
      setError('Could not reach the server.');
    }
  };

  useEffect(() => { loadFacts(); }, []);

  const handleDelete = async (id) => {
    setDeletingId(id);
    try {
      const resp = await apiFetch(`${API_BASE}/search/knowledge/${id}`, { method: 'DELETE' });
      if (resp.ok) {
        setFacts((prev) => prev.filter((f) => f.id !== id));
      }
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="converter-modal-backdrop" onClick={onClose}>
      <div className="converter-modal-content knowledge-base-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="converter-modal-header">
          <div className="modal-title-wrap">
            <h3>Knowledge Base</h3>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose}>
            <IconClose size={16} />
          </button>
        </div>

        <div className="converter-modal-body">
          <p className="modal-subheading">
            Rules and facts you've stated mid-chat (formulas, standing exclusions, policies) — applied to every
            future chat automatically. Remove anything that's wrong or no longer relevant.
          </p>

          {error && (
            <div className="login-error" style={{ marginTop: 12 }}>
              <IconAlert size={14} color="#EF4444" />
              <span>{error}</span>
            </div>
          )}

          {facts === null ? (
            <p className="card-subtitle">Loading...</p>
          ) : facts.length === 0 ? (
            <p className="card-subtitle">Nothing remembered yet — say something like "remember: monthly salary x12 = annual CTC" in a chat.</p>
          ) : (
            <div className="knowledge-fact-list">
              {facts.map((f) => (
                <div key={f.id} className="knowledge-fact-row">
                  <span className="knowledge-fact-text">{f.text}</span>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => handleDelete(f.id)}
                    disabled={deletingId === f.id}
                  >
                    {deletingId === f.id ? 'Removing...' : 'Forget'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
