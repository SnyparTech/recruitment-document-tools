import React, { useState } from 'react';
import { getApiBase } from '../config';
import FileUploadCard from './FileUploadCard';
import DossierResultCard from './DossierResultCard';
import { IconPhoto, IconIdCard, IconDocument, IconUpload, IconBolt, IconAlert } from '../components/Icons';

export default function DossierCompiler() {
  const [photo, setPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [idProof, setIdProof] = useState(null);
  const [resume, setResume] = useState(null);

  const [candidateName, setCandidateName] = useState('');
  const [recruiterNotes, setRecruiterNotes] = useState('');

  const [isCompiling, setIsCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const API_BASE = getApiBase();

  const handlePhotoSelect = (file) => {
    setPhoto(file);
    const reader = new FileReader();
    reader.onload = (e) => setPhotoPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleCompile = async (e) => {
    e.preventDefault();
    if (!photo || !idProof || !resume) {
      setErrorMessage('Please upload all 3 required files: Photo, Identity Proof, and Resume.');
      return;
    }

    setIsCompiling(true);
    setErrorMessage(null);
    setCompileResult(null);

    const formData = new FormData();
    formData.append('photo', photo);
    formData.append('id_proof', idProof);
    formData.append('resume', resume);
    if (candidateName.trim()) formData.append('candidate_name', candidateName.trim());
    if (recruiterNotes.trim()) formData.append('recruiter_notes', recruiterNotes.trim());

    try {
      const response = await fetch(`${API_BASE}/dossier/compile`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.message || errData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setCompileResult(data);
    } catch (err) {
      console.error('Compilation failed:', err);
      setErrorMessage(err.message || 'Failed to compile candidate dossier. Check backend connection.');
    } finally {
      setIsCompiling(false);
    }
  };

  const isFormReady = photo && idProof && resume;

  return (
    <div className="dossier-compiler-module">
      <div className="hero-section">
        <h1 className="hero-title">Candidate Profile Dossier Compiler</h1>
        <p className="hero-desc">
          Upload a candidate photo, government identity proof, and resume. The bot compiles them into a single 
          Word (<strong>.DOCX</strong>) document in the exact order: <strong>Photo ➔ Identity Proof ➔ Exact Resume</strong> (rendered verbatim with zero changes).
        </p>
      </div>

      <div className="card">
        <h2 className="card-title">
          <IconUpload size={22} color="var(--primary)" />
          <span>Upload Candidate Credentials</span>
        </h2>
        <p className="card-subtitle">All three documents are required for automated dossier verification.</p>

        <form onSubmit={handleCompile}>
          {/* 3-in-1 Upload Grid */}
          <div className="upload-grid">
            {/* 1. Photo */}
            <FileUploadCard
              title="1. Candidate Photo"
              icon={<IconPhoto size={36} color="var(--primary)" />}
              accept=".jpg,.jpeg,.png,.webp"
              formatsText="JPG, PNG, WEBP (Square portrait)"
              file={photo}
              preview={photoPreview}
              onFileSelect={handlePhotoSelect}
            />

            {/* 2. ID Proof */}
            <FileUploadCard
              title="2. Identity Proof"
              icon={<IconIdCard size={36} color="var(--primary)" />}
              accept=".pdf,.jpg,.jpeg,.png"
              formatsText="Passport, Aadhaar, PAN, DL (PDF/IMG)"
              file={idProof}
              preview={null}
              onFileSelect={setIdProof}
            />

            {/* 3. Resume */}
            <FileUploadCard
              title="3. Candidate Resume"
              icon={<IconDocument size={36} color="var(--primary)" />}
              accept=".pdf,.docx,.doc,.txt"
              formatsText="PDF, DOCX, DOC, or TXT"
              file={resume}
              preview={null}
              onFileSelect={setResume}
            />
          </div>

          {/* Optional Form Metadata */}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Candidate Name (Optional Override)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Aditi Sharma (auto-detected if left empty)"
                value={candidateName}
                onChange={(e) => setCandidateName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Recruiter Notes / Evaluation (Optional)</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Strong system design, 15 days notice period, verified references"
                value={recruiterNotes}
                onChange={(e) => setRecruiterNotes(e.target.value)}
              />
            </div>
          </div>

          {/* Error display */}
          {errorMessage && (
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
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Compile Action Button */}
          <button
            type="submit"
            className="btn-primary-action"
            disabled={!isFormReady || isCompiling}
          >
            {isCompiling ? (
              <>
                <div className="spinner"></div>
                <span>Compiling Exact Dossier (.DOCX)...</span>
              </>
            ) : (
              <>
                <IconBolt size={18} color="#FFFFFF" />
                <span>Compile Candidate Dossier (.DOCX)</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Result Card with Download Button */}
      <DossierResultCard
        result={compileResult}
        photoPreview={photoPreview}
        apiBase={API_BASE}
      />
    </div>
  );
}
