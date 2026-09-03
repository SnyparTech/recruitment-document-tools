import React from 'react';
import {
  IconUser,
  IconMail,
  IconPhone,
  IconCheck,
  IconDownload,
  IconDocument,
  IconPhoto,
  IconIdCard,
} from '../components/Icons';

export default function DossierResultCard({ result, photoPreview, apiBase }) {
  if (!result) return null;

  return (
    <div className="result-card">
      <div className="result-header">
        <div className="candidate-meta">
          <div className="candidate-avatar-frame">
            {photoPreview ? (
              <img src={photoPreview} alt="Candidate Portrait" />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <IconUser size={36} color="var(--text-muted)" />
              </div>
            )}
          </div>
          <div>
            <div className="candidate-name">{result.candidate_name}</div>
            <div className="candidate-title">{result.title}</div>
            <div className="candidate-contact-bar">
              {result.email && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  <IconMail size={13} color="var(--primary)" />
                  {result.email}
                </span>
              )}
              {result.phone && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  <IconPhone size={13} color="var(--primary)" />
                  {result.phone}
                </span>
              )}
              <span className="id-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <IconCheck size={12} color="var(--accent-emerald)" />
                {result.id_type} Verified
              </span>
            </div>
          </div>
        </div>

        <a
          href={`${apiBase}${result.download_url}`}
          target="_blank"
          rel="noreferrer"
          className="btn-download-docx"
          download
        >
          <IconDownload size={16} color="#FFFFFF" />
          <span>Download Dossier (.docx)</span>
        </a>
      </div>

      <div style={{ marginTop: '16px', background: 'rgba(0,0,0,0.2)', padding: '14px 18px', borderRadius: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <IconDocument size={16} color="var(--primary)" />
          <strong style={{ fontSize: '0.92rem', color: 'var(--text-primary)' }}>
            Compiled Document Structure (Strict Sequence):
          </strong>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
          <span className="skill-pill" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <IconPhoto size={13} color="#38BDF8" />
            1. Candidate Photo & Header
          </span>
          <span className="skill-pill" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <IconIdCard size={13} color="#10B981" />
            2. ID Proof ({result.id_type})
          </span>
          <span className="skill-pill" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818CF8', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <IconDocument size={13} color="#818CF8" />
            3. Candidate Resume (Verbatim Document)
          </span>
        </div>
      </div>
    </div>
  );
}
