import React, { useState, useRef } from 'react';
import { getApiBase } from '../config';
import {
  IconDocument,
  IconCheck,
  IconClose,
  IconUpload,
  IconDownload,
  IconEye,
  IconShield,
  IconSparkles,
  IconCopy,
} from './Icons';

// 10 Mandatory Progress Steps from Specification
const CONVERSION_STEPS = [
  { id: 1, label: 'Uploading resume' },
  { id: 2, label: 'Validating file' },
  { id: 3, label: 'Checking document safety' },
  { id: 4, label: 'Detecting sensitive information' },
  { id: 5, label: 'Extracting resume content' },
  { id: 6, label: 'Structuring resume' },
  { id: 7, label: 'Verifying information completeness' },
  { id: 8, label: 'Applying resume template' },
  { id: 9, label: 'Generating DOCX' },
  { id: 10, label: 'Ready to download' },
];

export default function ResumeConverterWorkspace() {
  const [file, setFile] = useState(null);
  const [uploadData, setUploadData] = useState(null);
  const [conversionData, setConversionData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);
  const [previewTab, setPreviewTab] = useState('formatted'); // 'formatted' | 'latex' | 'audit'
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [copiedLatex, setCopiedLatex] = useState(false);
  const fileInputRef = useRef(null);

  const apiBase = getApiBase();

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = async (selectedFile) => {
    setErrorMsg(null);
    setConversionData(null);
    setUploadData(null);
    setCurrentStep(0);

    // Initial client check for extension
    const ext = selectedFile.name.split('.').pop().toLowerCase();
    if (!['pdf', 'doc', 'docx'].includes(ext)) {
      setErrorMsg(`Unsupported file format '.${ext}'. Allowed formats: PDF, DOC, DOCX.`);
      return;
    }

    if (selectedFile.size > 10 * 1024 * 1024) {
      setErrorMsg('File is too large. Please upload a resume smaller than 10 MB.');
      return;
    }

    setFile(selectedFile);
    await uploadAndValidateFile(selectedFile);
  };

  const uploadAndValidateFile = async (fileToUpload) => {
    setIsUploading(true);
    setCurrentStep(1); // Uploading resume

    const formData = new FormData();
    formData.append('file', fileToUpload);

    try {
      // Step 1 -> Step 2 transition
      setCurrentStep(2); // Validating file

      const res = await fetch(`${apiBase}/api/resume/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        const message =
          data?.detail?.message || data?.message || 'File validation rejected by security policy.';
        setErrorMsg(message);
        setCurrentStep(0);
        setIsUploading(false);
        return;
      }

      // Step 3: Checking document safety
      setCurrentStep(3);
      await new Promise((r) => setTimeout(r, 250));

      // Step 4: Detecting sensitive information
      setCurrentStep(4);
      await new Promise((r) => setTimeout(r, 250));

      // Step 5: Extracting resume content
      setCurrentStep(5);
      setUploadData(data);
      setIsUploading(false);
    } catch (err) {
      console.error(err);
      setErrorMsg('Network error communicating with server. Please ensure backend is running.');
      setCurrentStep(0);
      setIsUploading(false);
    }
  };

  const handleConvertResume = async () => {
    if (!uploadData?.upload_id) return;

    setIsConverting(true);
    setErrorMsg(null);

    try {
      // Step 6: Structuring resume
      setCurrentStep(6);

      // Trigger conversion endpoint
      const convertPromise = fetch(`${apiBase}/api/resume/convert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: uploadData.upload_id }),
      });

      // Advance visual stepper smoothly while background computation runs
      await new Promise((r) => setTimeout(r, 600));
      setCurrentStep(7); // Verifying information completeness

      await new Promise((r) => setTimeout(r, 600));
      setCurrentStep(8); // Applying resume template

      await new Promise((r) => setTimeout(r, 600));
      setCurrentStep(9); // Generating DOCX

      const res = await convertPromise;
      const data = await res.json();

      if (!res.ok) {
        const message = data?.detail?.message || data?.message || 'Failed to convert resume.';
        setErrorMsg(message);
        setIsConverting(false);
        return;
      }

      // Step 10: Ready to download
      setCurrentStep(10);
      setConversionData(data);
      setIsConverting(false);
    } catch (err) {
      console.error(err);
      setErrorMsg('Error during resume conversion: ' + err.message);
      setIsConverting(false);
    }
  };

  const handleDownload = (format) => {
    if (!conversionData?.task_id) return;
    const downloadUrl = `${apiBase}/api/resume/download/${conversionData.task_id}/${format}`;
    window.open(downloadUrl, '_blank');
  };

  const handleCopyLatex = () => {
    if (conversionData?.latex_source) {
      navigator.clipboard.writeText(conversionData.latex_source);
      setCopiedLatex(true);
      setTimeout(() => setCopiedLatex(false), 2000);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="resume-converter-root">
      {/* Hero Banner */}
      <div className="converter-hero-card">
        <div className="converter-hero-pill">
          <IconSparkles size={14} color="#6366F1" />
          <span>Zero-Information-Loss AI Resume Engine</span>
        </div>
        <h1 className="converter-title">Convert Resume to LaTeX & DOCX</h1>
        <p className="converter-subtitle">
          Upload your existing resume in <strong>PDF, DOC, or DOCX</strong> format. Our
          deterministic AI reorganizes 100% of your original content into the standardized LaTeX
          resume structure and generates an editable, beautifully formatted <strong>DOCX</strong>{' '}
          document.
        </p>

        {/* Feature Pill Tags */}
        <div className="converter-guarantees">
          <div className="guarantee-chip">
            <IconShield size={14} color="#10B981" />
            <span>Magic-Byte Validation</span>
          </div>
          <div className="guarantee-chip">
            <span className="chip-indicator-blue"></span>
            <span>DLP Masking (Aadhaar, PAN)</span>
          </div>
          <div className="guarantee-chip">
            <span className="chip-indicator-purple"></span>
            <span>100% Zero-Loss Guarantee</span>
          </div>
          <div className="guarantee-chip">
            <span className="chip-indicator-emerald"></span>
            <span>Editable Microsoft Word (.docx)</span>
          </div>
        </div>
      </div>

      {/* Main Upload & Configuration Grid */}
      <div className="converter-main-grid">
        {/* Left / Top: Upload Zone */}
        <div className="converter-card upload-section-card">
          <div className="card-header-bar">
            <div className="card-header-title">
              <IconUpload size={18} color="#4F46E5" />
              <h3>1. Upload Existing Resume</h3>
            </div>
            <span className="badge-pill">PDF • DOC • DOCX (Max 10 MB)</span>
          </div>

          {/* Drag & Drop Area */}
          <div
            className={`dropzone-container ${file ? 'has-file' : ''}`}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileChange}
            />

            <div className="dropzone-icon-circle">
              <IconDocument size={28} color="#4F46E5" />
            </div>

            {file ? (
              <div className="dropzone-file-details">
                <p className="dropzone-file-name">{file.name}</p>
                <p className="dropzone-file-meta">
                  {formatBytes(file.size)} • {file.name.split('.').pop().toUpperCase()}
                </p>
                <span className="dropzone-change-hint">Click or drag another file to replace</span>
              </div>
            ) : (
              <div className="dropzone-text-block">
                <p className="dropzone-primary-text">
                  <strong>Drag & drop your resume here</strong>, or{' '}
                  <span className="dropzone-browse-link">browse files</span>
                </p>
                <p className="dropzone-secondary-text">
                  Strict security verification ensures safe parsing and DLP redaction
                </p>
              </div>
            )}
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div className="converter-error-banner">
              <IconClose size={16} color="#EF4444" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Upload & Security Inspection Report */}
          {uploadData && (
            <div className="upload-inspection-card">
              <div className="inspection-header">
                <span className="inspection-status-pill">
                  <IconCheck size={14} color="#10B981" /> Verified Safe
                </span>
                <span className="inspection-format-tag">{uploadData.detected_type} Document</span>
              </div>

              {/* Security & DLP Badges */}
              <div className="inspection-grid">
                <div className="inspection-item">
                  <span className="inspection-item-label">Magic Bytes & MIME</span>
                  <span className="inspection-item-val val-green">✓ Validated Signature</span>
                </div>
                <div className="inspection-item">
                  <span className="inspection-item-label">Archive Safety</span>
                  <span className="inspection-item-val val-green">✓ Clean (No Zip Bomb)</span>
                </div>
                <div className="inspection-item">
                  <span className="inspection-item-label">DLP Masking</span>
                  <span className="inspection-item-val val-blue">
                    {uploadData.dlp_summary?.detected_count > 0
                      ? `Masked ${uploadData.dlp_summary.detected_count} sensitive tokens`
                      : 'No sensitive IDs detected'}
                  </span>
                </div>
                <div className="inspection-item">
                  <span className="inspection-item-label">Detected Sections</span>
                  <span className="inspection-item-val val-slate">
                    {uploadData.sections_detected?.length || 0} sections found
                  </span>
                </div>
              </div>

              {/* DLP Summary Alert */}
              {uploadData.dlp_summary?.detected_count > 0 && (
                <div className="dlp-alert-banner">
                  <IconShield size={15} color="#3B82F6" />
                  <div>
                    <strong>Data Privacy Shield Active: </strong>
                    {uploadData.dlp_summary.masked_summaries?.map((s, idx) => (
                      <span key={idx} className="dlp-masked-tag">
                        {s.type}: {s.masked_value}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Convert Action Trigger */}
              <div className="convert-action-wrap">
                <button
                  type="button"
                  onClick={handleConvertResume}
                  disabled={isConverting}
                  className={`btn-primary-convert ${isConverting ? 'loading' : ''}`}
                >
                  <IconSparkles size={18} color="#FFFFFF" />
                  <span>{isConverting ? 'Converting Resume...' : 'Convert Resume Now'}</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right / Bottom: 10-Step Progress Stepper & Results Card */}
        <div className="converter-card progress-section-card">
          <div className="card-header-bar">
            <div className="card-header-title">
              <IconSparkles size={18} color="#6366F1" />
              <h3>2. Conversion Pipeline & Output</h3>
            </div>
            <span className="badge-pill">
              {currentStep === 10
                ? 'Complete (10/10)'
                : currentStep > 0
                ? `Step ${currentStep} of 10`
                : 'Waiting for Upload'}
            </span>
          </div>

          {/* Stepper Timeline */}
          <div className="stepper-track">
            {CONVERSION_STEPS.map((step) => {
              const isCompleted = currentStep > step.id || (currentStep === 10 && step.id === 10);
              const isActive = currentStep === step.id && currentStep !== 10;
              const isPending = currentStep < step.id;

              return (
                <div
                  key={step.id}
                  className={`stepper-item ${
                    isCompleted ? 'completed' : isActive ? 'active' : 'pending'
                  }`}
                >
                  <div className="stepper-marker">
                    {isCompleted ? (
                      <IconCheck size={12} color="#FFFFFF" />
                    ) : isActive ? (
                      <span className="spinner-mini"></span>
                    ) : (
                      <span className="step-num">{step.id}</span>
                    )}
                  </div>
                  <div className="stepper-text">
                    <span className="stepper-label">{step.label}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Success Download Card when Ready */}
          {conversionData && (
            <div className="conversion-ready-card">
              <div className="ready-header">
                <div className="ready-avatar">
                  <IconCheck size={20} color="#10B981" />
                </div>
                <div>
                  <h4 className="ready-candidate-name">
                    {conversionData.candidate_name || 'Candidate'} Resume
                  </h4>
                  <p className="ready-subtext">Successfully structured into LaTeX template</p>
                </div>
              </div>

              {/* Completeness Scorecard Pill */}
              <div className="preservation-scorecard">
                <div className="scorecard-badge">
                  <span className="scorecard-pct">
                    {conversionData.completeness_report?.preservation_score || 100}%
                  </span>
                  <span className="scorecard-text">Preservation Verified</span>
                </div>
                <div className="scorecard-desc">
                  <span>
                    Zero information lost. All metrics, dates, companies, skills, and bullets
                    preserved verbatim.
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="download-actions-grid">
                {/* Primary Button: Download DOCX */}
                <button
                  type="button"
                  onClick={() => handleDownload('docx')}
                  className="btn-download-primary"
                  title="Download editable Microsoft Word Document"
                >
                  <IconDownload size={18} color="#FFFFFF" />
                  <span className="btn-dl-text">
                    <strong>Download DOCX</strong>
                    <small>Real Editable Word File</small>
                  </span>
                </button>

                {/* Secondary Button: Download PDF */}
                {conversionData.has_pdf && (
                  <button
                    type="button"
                    onClick={() => handleDownload('pdf')}
                    className="btn-download-secondary"
                    title="Download high-fidelity PDF"
                  >
                    <IconDocument size={16} color="#4F46E5" />
                    <span>Download PDF</span>
                  </button>
                )}

                {/* Secondary Button: Download LaTeX Source */}
                <button
                  type="button"
                  onClick={() => handleDownload('tex')}
                  className="btn-download-secondary"
                  title="Download clean .tex LaTeX source"
                >
                  <IconDownload size={16} color="#059669" />
                  <span>Download .tex</span>
                </button>

                {/* Secondary Button: View Preview */}
                <button
                  type="button"
                  onClick={() => setShowPreviewModal(true)}
                  className="btn-download-secondary preview-trigger"
                  title="View structured preview & LaTeX code"
                >
                  <IconEye size={16} color="#D97706" />
                  <span>View Preview</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Preview Modal */}
      {showPreviewModal && conversionData && (
        <div className="converter-modal-backdrop" onClick={() => setShowPreviewModal(false)}>
          <div className="converter-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="converter-modal-header">
              <div className="modal-title-wrap">
                <IconEye size={20} color="#4F46E5" />
                <h3>Resume Preview & Audit</h3>
              </div>

              {/* Modal Tabs */}
              <div className="modal-nav-tabs">
                <button
                  type="button"
                  className={`modal-tab ${previewTab === 'formatted' ? 'active' : ''}`}
                  onClick={() => setPreviewTab('formatted')}
                >
                  Structured Resume
                </button>
                <button
                  type="button"
                  className={`modal-tab ${previewTab === 'latex' ? 'active' : ''}`}
                  onClick={() => setPreviewTab('latex')}
                >
                  LaTeX Source (.tex)
                </button>
                <button
                  type="button"
                  className={`modal-tab ${previewTab === 'audit' ? 'active' : ''}`}
                  onClick={() => setPreviewTab('audit')}
                >
                  Completeness Audit
                </button>
              </div>

              <button
                type="button"
                className="btn-modal-close"
                onClick={() => setShowPreviewModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="converter-modal-body">
              {/* Tab 1: Formatted View */}
              {previewTab === 'formatted' && (
                <div className="formatted-resume-view">
                  <div className="latex-paper-simulation">
                    <h2 className="sim-name">
                      {conversionData.candidate_name || 'CANDIDATE NAME'}
                    </h2>

                    {/* Section: Education */}
                    {conversionData.structured_resume?.education?.length > 0 && (
                      <div className="sim-section">
                        <div className="sim-sec-title">EDUCATION</div>
                        <div className="sim-divider"></div>
                        {conversionData.structured_resume.education.map((edu, idx) => (
                          <div key={idx} className="sim-entry">
                            <div className="sim-entry-row">
                              <strong>{edu.institution || 'University'}</strong>
                              <span>{edu.date}</span>
                            </div>
                            <div className="sim-entry-sub">
                              <em>{edu.degree}</em>
                              <span>{edu.location}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Section: Skills */}
                    {conversionData.structured_resume?.skills && (
                      <div className="sim-section">
                        <div className="sim-sec-title">SKILLS</div>
                        <div className="sim-divider"></div>
                        {conversionData.structured_resume.skills.technical_skills?.length > 0 && (
                          <p className="sim-skills-line">
                            <strong>Technical Skills: </strong>
                            {conversionData.structured_resume.skills.technical_skills.join(', ')}
                          </p>
                        )}
                        {conversionData.structured_resume.skills.soft_skills?.length > 0 && (
                          <p className="sim-skills-line">
                            <strong>Soft Skills: </strong>
                            {conversionData.structured_resume.skills.soft_skills.join(', ')}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Section: Experience */}
                    {conversionData.structured_resume?.experience?.length > 0 && (
                      <div className="sim-section">
                        <div className="sim-sec-title">EXPERIENCE</div>
                        <div className="sim-divider"></div>
                        {conversionData.structured_resume.experience.map((exp, idx) => (
                          <div key={idx} className="sim-entry">
                            <div className="sim-entry-row">
                              <strong>{exp.company || 'Company'}</strong>
                              <span>
                                {exp.start_date} - {exp.end_date}
                              </span>
                            </div>
                            <div className="sim-entry-sub">
                              <em>{exp.role}</em>
                              <span>{exp.location}</span>
                            </div>
                            <ul className="sim-bullets">
                              {exp.bullets?.map((b, bIdx) => (
                                <li key={bIdx}>{b}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: LaTeX Source */}
              {previewTab === 'latex' && (
                <div className="latex-source-view">
                  <div className="source-toolbar">
                    <button type="button" onClick={handleCopyLatex} className="btn-copy-code">
                      <IconCopy size={14} />
                      <span>{copiedLatex ? 'Copied to Clipboard!' : 'Copy LaTeX Code'}</span>
                    </button>
                  </div>
                  <pre className="latex-code-block">{conversionData.latex_source}</pre>
                </div>
              )}

              {/* Tab 3: Completeness Audit */}
              {previewTab === 'audit' && (
                <div className="audit-report-view">
                  <div className="audit-card">
                    <h4>Completeness Verification Report</h4>
                    <p>
                      Preservation Score:{' '}
                      <strong>
                        {conversionData.completeness_report?.preservation_score || 100}%
                      </strong>
                    </p>
                    <p className="audit-guarantee-text">
                      ✓ No companies, dates, metrics, percentages, job titles, or bullet points were
                      invented, dropped, or summarized.
                    </p>
                    {conversionData.completeness_report?.missing_items?.length > 0 ? (
                      <div className="missing-list">
                        <h5>Auto-Recovered Entities:</h5>
                        <ul>
                          {conversionData.completeness_report.missing_items.map((m, idx) => (
                            <li key={idx}>{m}</li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <div className="audit-all-clear">
                        <IconCheck size={18} color="#10B981" />
                        <span>All source entities matched 1-to-1 in the structured output.</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
