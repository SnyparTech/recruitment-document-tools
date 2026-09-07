import React, { useState, useRef, useEffect } from 'react';
import { getApiBase } from '../config';
import DossierResultCard from './DossierResultCard';

export default function DossierUploadWorkspace({ initialCandidate, onBack }) {
  const [photo, setPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [idProof, setIdProof] = useState(null);
  const [resume, setResume] = useState(null);

  const [candidateName, setCandidateName] = useState(initialCandidate?.name || '');
  const [recruiterNotes, setRecruiterNotes] = useState(initialCandidate?.notes || '');

  const [dragSlot, setDragSlot] = useState(null);
  const [currentStep, setCurrentStep] = useState(1); // 1: Upload, 2: Review, 3: Generate
  const [isCompiling, setIsCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const photoInputRef = useRef(null);
  const idInputRef = useRef(null);
  const resumeInputRef = useRef(null);

  const API_BASE = getApiBase();

  useEffect(() => {
    if (initialCandidate?.name) setCandidateName(initialCandidate.name);
    if (initialCandidate?.notes) setRecruiterNotes(initialCandidate.notes);
  }, [initialCandidate]);

  const handlePhotoFile = (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('Photo exceeds maximum allowed size of 10 MB.');
      return;
    }
    setPhoto(file);
    setErrorMessage(null);
    const reader = new FileReader();
    reader.onload = (e) => setPhotoPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const handleIdFile = (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('Identity proof exceeds maximum allowed size of 10 MB.');
      return;
    }
    setIdProof(file);
    setErrorMessage(null);
  };

  const handleResumeFile = (file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('Resume exceeds maximum allowed size of 10 MB.');
      return;
    }
    setResume(file);
    setErrorMessage(null);
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const uploadedCount = [photo, idProof, resume].filter(Boolean).length;
  const isComplete = uploadedCount === 3;

  const handleCompile = async () => {
    if (!isComplete) return;

    setIsCompiling(true);
    setErrorMessage(null);
    setCurrentStep(2);

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
      setCurrentStep(3);
    } catch (err) {
      console.error('Compilation failed:', err);
      setErrorMessage(err.message || 'Failed to compile candidate dossier. Please verify backend is running.');
      setCurrentStep(1);
    } finally {
      setIsCompiling(false);
    }
  };

  const handleReset = () => {
    setPhoto(null);
    setPhotoPreview(null);
    setIdProof(null);
    setResume(null);
    setCompileResult(null);
    setErrorMessage(null);
    setCurrentStep(1);
  };

  return (
    <div className="workspace-container">
      <div className="workspace-card">
        {/* Top Bar: Back link + 3-step wizard */}
        <div className="workspace-top-bar">
          <button type="button" className="back-link" onClick={onBack}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            <span>Back to Candidates</span>
          </button>

          {/* Stepper */}
          <div className="stepper-nav">
            {/* Step 1 */}
            <div className={`step-item ${currentStep === 1 ? 'active' : ''} ${currentStep > 1 ? 'completed' : ''}`}>
              <div className="step-circle">
                {currentStep > 1 ? '✓' : '1'}
              </div>
              <span className="step-label">
                <span className="step-label-full">Upload Documents</span>
                <span className="step-label-short">Upload</span>
              </span>
            </div>

            <div className={`step-connector ${currentStep > 1 ? 'completed' : ''}`}></div>

            {/* Step 2 */}
            <div className={`step-item ${currentStep === 2 ? 'active' : ''} ${currentStep > 2 ? 'completed' : ''}`}>
              <div className="step-circle">
                {currentStep > 2 ? '✓' : '2'}
              </div>
              <span className="step-label">Review</span>
            </div>

            <div className={`step-connector ${currentStep > 2 ? 'completed' : ''}`}></div>

            {/* Step 3 */}
            <div className={`step-item ${currentStep === 3 ? 'active' : ''}`}>
              <div className="step-circle">3</div>
              <span className="step-label">
                <span className="step-label-full">Generate Dossier</span>
                <span className="step-label-short">Generate</span>
              </span>
            </div>
          </div>
        </div>

        {/* Heading */}
        <div className="workspace-heading-block">
          <h1 className="workspace-main-title">Upload Candidate Documents</h1>
          <p className="workspace-sub-title">
            All three documents are <strong>mandatory</strong> to compile the candidate's profile.
          </p>
        </div>

        {/* Error message if any */}
        {errorMessage && (
          <div className="inline-error">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{errorMessage}</span>
          </div>
        )}

        {/* If dossier compiled successfully, show the Result View */}
        {compileResult ? (
          <div style={{ marginTop: '20px' }}>
            <DossierResultCard
              result={compileResult}
              apiBase={API_BASE}
              onReset={handleReset}
            />
          </div>
        ) : (
          <>
            {/* 3 Document Slots Row + Right Showcase */}
            <div className="slots-showcase-grid">
              {/* ---------------------------------------------------- */}
              {/* SLOT 1: Candidate Photo */}
              {/* ---------------------------------------------------- */}
              <div className="document-slot slot-photo">
                <span className="slot-badge-required">Required</span>

                <div className="slot-icon-wrapper">
                  <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="8" r="4" fill="currentColor" fillOpacity="0.25" />
                    <path d="M6 20v-1a6 6 0 0 1 12 0v1" fill="currentColor" fillOpacity="0.25" />
                  </svg>
                </div>

                <h3 className="slot-title">Candidate Photo</h3>
                <p className="slot-desc">Clear passport size photo</p>
                <div className="slot-specs">
                  JPG / PNG / WEBP<br />(Max 10 MB)
                </div>

                <input
                  ref={photoInputRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp"
                  style={{ display: 'none' }}
                  onChange={(e) => handlePhotoFile(e.target.files[0])}
                />

                {photo ? (
                  <div className="slot-uploaded-box">
                    <div className="uploaded-file-row">
                      {photoPreview ? (
                        <img src={photoPreview} alt="Thumbnail" className="uploaded-thumb" />
                      ) : (
                        <div className="uploaded-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#FFE8E2' }}>
                          📸
                        </div>
                      )}
                      <div className="uploaded-file-details">
                        <div className="uploaded-file-name" title={photo.name}>{photo.name}</div>
                        <div className="uploaded-file-size">{formatFileSize(photo.size)}</div>
                      </div>
                    </div>
                    <div className="uploaded-actions-row">
                      <button
                        type="button"
                        className="btn-slot-action btn-slot-replace"
                        onClick={() => photoInputRef.current?.click()}
                      >
                        Replace
                      </button>
                      <button
                        type="button"
                        className="btn-slot-action btn-slot-remove"
                        onClick={() => { setPhoto(null); setPhotoPreview(null); }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`slot-dropzone ${dragSlot === 'photo' ? 'drag-active' : ''}`}
                    onClick={() => photoInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragSlot('photo'); }}
                    onDragLeave={() => setDragSlot(null)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragSlot(null);
                      if (e.dataTransfer.files?.[0]) handlePhotoFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <div className="dropzone-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                    </div>
                    <span className="dropzone-text">
                      {dragSlot === 'photo' ? 'Drop photo here' : 'Drag & drop or click to upload'}
                    </span>
                  </div>
                )}
              </div>

              {/* ---------------------------------------------------- */}
              {/* SLOT 2: Identity Proof */}
              {/* ---------------------------------------------------- */}
              <div className="document-slot slot-id">
                <span className="slot-badge-required">Required</span>

                <div className="slot-icon-wrapper">
                  <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="5" width="20" height="14" rx="2" fill="currentColor" fillOpacity="0.2" />
                    <line x1="2" y1="10" x2="22" y2="10" />
                    <circle cx="7" cy="15" r="1.5" />
                    <line x1="12" y1="15" x2="18" y2="15" />
                  </svg>
                </div>

                <h3 className="slot-title">Identity Proof</h3>
                <p className="slot-desc">Government issued document (Aadhaar, PAN, DL etc.)</p>
                <div className="slot-specs">
                  PDF / JPG / PNG<br />(Max 10 MB)
                </div>

                <input
                  ref={idInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  style={{ display: 'none' }}
                  onChange={(e) => handleIdFile(e.target.files[0])}
                />

                {idProof ? (
                  <div className="slot-uploaded-box">
                    <div className="uploaded-file-row">
                      <div className="uploaded-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#DCFCE7', color: '#10B981', fontWeight: 700, fontSize: '0.65rem' }}>
                        IDENTITY
                      </div>
                      <div className="uploaded-file-details">
                        <div className="uploaded-file-name" title={idProof.name}>{idProof.name}</div>
                        <div className="uploaded-file-size">{formatFileSize(idProof.size)}</div>
                      </div>
                    </div>
                    <div className="uploaded-actions-row">
                      <button
                        type="button"
                        className="btn-slot-action btn-slot-replace"
                        onClick={() => idInputRef.current?.click()}
                      >
                        Replace
                      </button>
                      <button
                        type="button"
                        className="btn-slot-action btn-slot-remove"
                        onClick={() => setIdProof(null)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`slot-dropzone ${dragSlot === 'id' ? 'drag-active' : ''}`}
                    onClick={() => idInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragSlot('id'); }}
                    onDragLeave={() => setDragSlot(null)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragSlot(null);
                      if (e.dataTransfer.files?.[0]) handleIdFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <div className="dropzone-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                    </div>
                    <span className="dropzone-text">
                      {dragSlot === 'id' ? 'Drop ID proof here' : 'Drag & drop or click to upload'}
                    </span>
                  </div>
                )}
              </div>

              {/* ---------------------------------------------------- */}
              {/* SLOT 3: Resume */}
              {/* ---------------------------------------------------- */}
              <div className="document-slot slot-resume">
                <span className="slot-badge-required">Required</span>

                <div className="slot-icon-wrapper">
                  <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="currentColor" fillOpacity="0.2" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                </div>

                <h3 className="slot-title">Resume</h3>
                <p className="slot-desc">Latest resume</p>
                <div className="slot-specs">
                  PDF (Auto-converts to DOCX)<br />DOCX / DOC (Max 10 MB)
                </div>

                <input
                  ref={resumeInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.txt"
                  style={{ display: 'none' }}
                  onChange={(e) => handleResumeFile(e.target.files[0])}
                />

                {resume ? (
                  <div className="slot-uploaded-box">
                    <div className="uploaded-file-row">
                      <div className="uploaded-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#E0E7FF', color: '#6366F1', fontWeight: 700, fontSize: '0.65rem' }}>
                        RESUME
                      </div>
                      <div className="uploaded-file-details">
                        <div className="uploaded-file-name" title={resume.name}>{resume.name}</div>
                        <div className="uploaded-file-size" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>{formatFileSize(resume.size)}</span>
                          {resume.name.toLowerCase().endsWith('.pdf') && (
                            <span style={{
                              background: '#EEF2FF',
                              color: '#4338CA',
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              padding: '1px 6px',
                              borderRadius: '4px',
                            }}>
                              Auto-converting to DOCX
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="uploaded-actions-row">
                      <button
                        type="button"
                        className="btn-slot-action btn-slot-replace"
                        onClick={() => resumeInputRef.current?.click()}
                      >
                        Replace
                      </button>
                      <button
                        type="button"
                        className="btn-slot-action btn-slot-remove"
                        onClick={() => setResume(null)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`slot-dropzone ${dragSlot === 'resume' ? 'drag-active' : ''}`}
                    onClick={() => resumeInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragSlot('resume'); }}
                    onDragLeave={() => setDragSlot(null)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragSlot(null);
                      if (e.dataTransfer.files?.[0]) handleResumeFile(e.dataTransfer.files[0]);
                    }}
                  >
                    <div className="dropzone-icon">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                    </div>
                    <span className="dropzone-text">
                      {dragSlot === 'resume' ? 'Drop resume here' : 'Drag & drop or click to upload'}
                    </span>
                  </div>
                )}
              </div>

              {/* ---------------------------------------------------- */}
              {/* RIGHT SHOWCASE COLUMN (FOLDER ART + VALUE PROPS) */}
              {/* ---------------------------------------------------- */}
              <div className="showcase-column">
                <div className="showcase-annotation">
                  <span className="annotation-text">
                    Three documents<br />
                    One complete profile
                  </span>
                  <svg className="annotation-arrow" width="36" height="34" viewBox="0 0 36 34" fill="none">
                    <path d="M12 2C24 6 32 16 28 28M28 28L22 24M28 28L34 22" stroke="#4338CA" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>

                {/* 3D-styled Folder Graphic */}
                <div className="folder-visual-box">
                  <svg className="folder-svg" viewBox="0 0 200 160" fill="none" xmlns="http://www.w3.org/2000/svg">
                    {/* Back folder flap */}
                    <path d="M25 45C25 39.4772 29.4772 35 35 35H75L90 48H165C170.523 48 175 52.4772 175 58V125C175 130.523 170.523 135 165 135H35C29.4772 135 25 130.523 25 125V45Z" fill="#C7D2FE" />
                    
                    {/* Candidate document sticking out */}
                    <rect x="52" y="18" width="96" height="110" rx="8" fill="#FFFFFF" filter="drop-shadow(0 4px 12px rgba(0,0,0,0.08))" />
                    <circle cx="100" cy="46" r="16" fill="#818CF8" />
                    <circle cx="100" cy="42" r="6" fill="#FFFFFF" />
                    <path d="M90 56C90 52 94 50 100 50C106 50 110 52 110 56" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
                    <rect x="70" y="72" width="60" height="5" rx="2.5" fill="#E2E8F0" />
                    <rect x="76" y="83" width="48" height="4" rx="2" fill="#E2E8F0" />
                    <rect x="82" y="93" width="36" height="4" rx="2" fill="#EEF2FF" />

                    {/* Front folder flap (angled perspective) */}
                    <path d="M20 62C20 57.5817 23.5817 54 28 54H172C176.418 54 180 57.5817 180 62L172 132C171.5 136 168 139 164 139H36C32 139 28.5 136 28 132L20 62Z" fill="url(#folderGradient)" fillOpacity="0.9" />
                    
                    {/* Front highlight line */}
                    <path d="M28 58H172" stroke="#A5B4FC" strokeWidth="2" strokeLinecap="round" />

                    <defs>
                      <linearGradient id="folderGradient" x1="20" y1="54" x2="180" y2="139" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#6366F1" />
                        <stop offset="1" stopColor="#4F46E5" />
                      </linearGradient>
                    </defs>
                  </svg>
                </div>

                {/* 3 Checkmark Value Props */}
                <div className="showcase-checklist">
                  <div className="checklist-item">
                    <div className="check-badge">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <span>Secure Uploads</span>
                  </div>

                  <div className="checklist-item">
                    <div className="check-badge">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <span>HR Only Access</span>
                  </div>

                  <div className="checklist-item">
                    <div className="check-badge">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <span>Used for Profile Compilation</span>
                  </div>
                </div>
              </div>
            </div>



            {/* Bottom Security Strip */}
            <div className="security-strip">
              <div className="security-left">
                <div className="security-icon-box">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </div>
                <div>
                  <div className="security-title">Your data is secure</div>
                  <div className="security-desc">
                    Documents are encrypted and accessible only to authorized HR members.
                  </div>
                </div>
              </div>

              <div className="security-right">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <polyline points="9 12 11 14 15 10" />
                </svg>
                <span>We follow industry best practices for data security.</span>
              </div>
            </div>

            {/* Bottom Action Bar: Cancel & Continue → */}
            <div className="action-bar">
              <button
                type="button"
                className="btn-cancel"
                onClick={handleReset}
              >
                Cancel
              </button>

              <button
                type="button"
                className="btn-continue"
                disabled={!isComplete || isCompiling}
                onClick={handleCompile}
              >
                {isCompiling ? (
                  <>
                    <span className="spinner-light"></span>
                    <span>Compiling Dossier...</span>
                  </>
                ) : (
                  <>
                    <span>Continue</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12" />
                      <polyline points="12 5 19 12 12 19" />
                    </svg>
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
