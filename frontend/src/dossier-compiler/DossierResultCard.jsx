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
    <div style={{
      background: '#FFFFFF',
      border: '1.5px solid #E0E7FF',
      borderRadius: '16px',
      padding: '24px 28px',
      boxShadow: '0 8px 30px rgba(79, 70, 229, 0.06)',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        paddingBottom: '20px',
        borderBottom: '1px solid #EEF2FF',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '60px',
            height: '60px',
            borderRadius: '12px',
            overflow: 'hidden',
            backgroundColor: '#EEF2FF',
            border: '2px solid #C7D2FE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            {photoPreview ? (
              <img src={photoPreview} alt="Candidate" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              <IconUser size={30} color="#4F46E5" />
            )}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A' }}>
                {result.candidate_name || 'Candidate Dossier'}
              </h3>
              <span style={{
                background: '#ECFDF5',
                color: '#059669',
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '999px',
                border: '1px solid #A7F3D0',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}>
                <IconCheck size={11} color="#059669" /> Verified Dossier
              </span>
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#4F46E5', marginTop: '2px' }}>
              {result.title || 'Candidate Profile'}
            </div>
            <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', marginTop: '4px', fontSize: '0.78rem', color: '#64748B' }}>
              {result.email && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <IconMail size={12} color="#6366F1" /> {result.email}
                </span>
              )}
              {result.phone && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <IconPhone size={12} color="#6366F1" /> {result.phone}
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {onReset && (
            <button
              type="button"
              onClick={onReset}
              style={{
                background: '#FFFFFF',
                border: '1px solid #CBD5E1',
                color: '#475569',
                borderRadius: '8px',
                padding: '10px 18px',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Upload Another
            </button>
          )}

          <a
            href={`${apiBase}${result.download_url}`}
            target="_blank"
            rel="noreferrer"
            download
            style={{
              background: '#4F46E5',
              color: '#FFFFFF',
              textDecoration: 'none',
              padding: '10px 22px',
              borderRadius: '8px',
              fontSize: '0.9rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              boxShadow: '0 4px 14px rgba(79, 70, 229, 0.3)',
            }}
          >
            <IconDownload size={16} color="#FFFFFF" />
            <span>Download Verified Dossier (.docx)</span>
          </a>
        </div>
      </div>

      <div style={{ marginTop: '18px', background: '#F8FAFC', padding: '14px 18px', borderRadius: '10px', border: '1px solid #E2E8F0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <IconDocument size={16} color="#4F46E5" />
          <strong style={{ fontSize: '0.86rem', color: '#1E293B' }}>
            Compiled Document Structure (Strict Sequence Verified):
          </strong>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ background: '#FFF7F5', color: '#EF4444', border: '1px solid #FED7AA', padding: '3px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <IconPhoto size={13} color="#EF4444" />
            1. Candidate Photo & Header
          </span>
          <span style={{ background: '#F0FDF4', color: '#10B981', border: '1px solid #BBF7D0', padding: '3px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <IconIdCard size={13} color="#10B981" />
            2. ID Proof ({result.id_type || 'Verified'})
          </span>
          <span style={{ background: '#F5F6FF', color: '#6366F1', border: '1px solid #C7D2FE', padding: '3px 10px', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <IconDocument size={13} color="#6366F1" />
            3. Candidate Resume (Verbatim Multi-Page Document)
          </span>
        </div>
      </div>
    </div>
  );
}
