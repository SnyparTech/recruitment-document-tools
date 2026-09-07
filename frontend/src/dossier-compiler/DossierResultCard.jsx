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

export default function DossierResultCard({ result, photoPreview, apiBase, onReset }) {
  if (!result) return null;

  return (
    <div className="dossier-result-card">
      <div className="dossier-result-header">
        <div className="dossier-candidate-profile">
          <div className="dossier-candidate-avatar">
            {photoPreview ? (
              <img src={photoPreview} alt="Candidate" />
            ) : (
              <IconUser size={30} color="#4F46E5" />
            )}
          </div>
          <div className="dossier-candidate-info">
            <div className="dossier-name-row">
              <h3 className="dossier-candidate-name">
                {result.candidate_name || 'Candidate Dossier'}
              </h3>
              <span className="dossier-verified-badge">
                <IconCheck size={11} color="#059669" /> Verified Dossier
              </span>
            </div>
            <div className="dossier-candidate-title">
              {result.title || 'Candidate Profile'}
            </div>
            <div className="dossier-candidate-contacts">
              {result.email && (
                <span className="contact-item">
                  <IconMail size={12} color="#6366F1" /> {result.email}
                </span>
              )}
              {result.phone && (
                <span className="contact-item">
                  <IconPhone size={12} color="#6366F1" /> {result.phone}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="dossier-result-actions">
          {onReset && (
            <button
              type="button"
              className="btn-result-reset"
              onClick={onReset}
            >
              Upload Another
            </button>
          )}

          {result.converted_resume_url && (
            <a
              href={`${apiBase}${result.converted_resume_url}`}
              target="_blank"
              rel="noreferrer"
              download
              className="btn-result-download-docx"
              title="Download standalone converted Word .docx resume"
            >
              <IconDocument size={16} color="#4338CA" />
              <span>Converted Resume (.docx)</span>
            </a>
          )}

          <a
            href={`${apiBase}${result.download_url}`}
            target="_blank"
            rel="noreferrer"
            download
            className="btn-result-download-dossier"
          >
            <IconDownload size={17} color="#FFFFFF" />
            <span>Download Verified Dossier (.docx)</span>
          </a>
        </div>
      </div>

      <div className="dossier-structure-box">
        <div className="dossier-structure-title">
          <IconDocument size={16} color="#4F46E5" />
          <strong>Compiled Document Structure (Strict Sequence Verified):</strong>
        </div>
        <div className="dossier-structure-pills">
          <span className="structure-pill pill-photo">
            <IconPhoto size={13} color="#EF4444" />
            1. Candidate Photo & Header
          </span>
          <span className="structure-pill pill-id">
            <IconIdCard size={13} color="#10B981" />
            2. ID Proof ({result.id_type || 'Verified'})
          </span>
          <span className="structure-pill pill-resume">
            <IconDocument size={13} color="#6366F1" />
            3. Candidate Resume {result.converted_resume_url ? '(PDF Auto-Converted to Native DOCX)' : '(Native Word Document)'}
          </span>
        </div>
      </div>
    </div>
  );
}
