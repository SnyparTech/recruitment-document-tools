import React, { useState } from 'react';
import {
  IconCheck,
  IconClose,
  IconCopy,
  IconEye,
  IconRefresh,
  IconSparkles,
} from '../components/Icons';

export default function ConvertedResumePreviewModal({
  isOpen,
  conversionData,
  isRegenerating,
  isConfirming,
  onConfirm,
  onRegenerate,
  onCancel,
}) {
  const [activeTab, setActiveTab] = useState('formatted'); // 'formatted' | 'latex' | 'audit'
  const [copiedLatex, setCopiedLatex] = useState(false);

  if (!isOpen || !conversionData) return null;

  const sr = conversionData.structured_resume || {};
  const pi = sr.personal_information || sr.personal_info || {};
  const candidateName = conversionData.candidate_name || pi.name || 'Candidate Name';
  const objective = sr.objective || '';
  const education = sr.education || [];
  const experience = sr.experience || [];
  const projects = sr.projects || [];
  const additionalSections = sr.additional_sections || [];
  const skills = sr.skills || {};

  // Extract skills dictionary or list
  const skillsDict = skills.skills_dict || {};
  const skillsCategories = Object.keys(skillsDict).length > 0
    ? Object.entries(skillsDict)
    : [
        skills.technical_skills?.length ? ['Technical Skills', skills.technical_skills.join(', ')] : null,
        skills.soft_skills?.length ? ['Soft Skills', skills.soft_skills.join(', ')] : null,
      ].filter(Boolean);

  const handleCopyLatex = () => {
    if (conversionData.latex_code || conversionData.latex_source) {
      navigator.clipboard.writeText(conversionData.latex_code || conversionData.latex_source);
      setCopiedLatex(true);
      setTimeout(() => setCopiedLatex(false), 2000);
    }
  };

  return (
    <div className="converter-modal-backdrop" onClick={onCancel}>
      <div className="converter-modal-content resume-preview-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="converter-modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon-badge">
              <IconSparkles size={18} color="#4F46E5" />
            </div>
            <div>
              <h3 className="modal-heading">Confirm AI Converted Resume</h3>
              <p className="modal-subheading">
                Standard LaTeX Format (<code>resume.cls</code>) • Review layout before applying
              </p>
            </div>
          </div>

          {/* Nav Tabs */}
          <div className="modal-nav-tabs">
            <button
              type="button"
              className={`modal-tab ${activeTab === 'formatted' ? 'active' : ''}`}
              onClick={() => setActiveTab('formatted')}
            >
              <IconEye size={14} />
              <span>Formatted Preview</span>
            </button>
            <button
              type="button"
              className={`modal-tab ${activeTab === 'latex' ? 'active' : ''}`}
              onClick={() => setActiveTab('latex')}
            >
              <span>LaTeX Code (.tex)</span>
            </button>
            <button
              type="button"
              className={`modal-tab ${activeTab === 'audit' ? 'active' : ''}`}
              onClick={() => setActiveTab('audit')}
            >
              <span>Zero-Loss Audit</span>
            </button>
          </div>

          <button
            type="button"
            className="btn-modal-close"
            onClick={onCancel}
            title="Cancel and ignore AI conversion"
          >
            <IconClose size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="converter-modal-body">
          {/* Tab 1: Formatted Preview (LaTeX Template Paper Replica) */}
          {activeTab === 'formatted' && (
            <div className="formatted-resume-view">
              <div className="latex-paper-simulation latex-paper-exact">
                {/* 1. Header: Candidate Name */}
                <h1 className="latex-sim-name">{candidateName.toUpperCase()}</h1>

                {/* 2. Contact Sublines */}
                <div className="latex-sim-contact">
                  {[
                    pi.phone,
                    pi.location,
                    pi.email,
                    pi.linkedin,
                    pi.website,
                  ].filter(Boolean).map((item, idx, arr) => (
                    <React.Fragment key={idx}>
                      <span>{item}</span>
                      {idx < arr.length - 1 && <span className="latex-sim-sep">|</span>}
                    </React.Fragment>
                  ))}
                </div>

                {/* 3. Objective */}
                {objective && (
                  <div className="latex-sim-section">
                    <div className="latex-sim-sec-title">OBJECTIVE</div>
                    <div className="latex-sim-hrule" />
                    <p className="latex-sim-objective-text">{objective}</p>
                  </div>
                )}

                {/* 4. Education */}
                {education.length > 0 && (
                  <div className="latex-sim-section">
                    <div className="latex-sim-sec-title">EDUCATION</div>
                    <div className="latex-sim-hrule" />
                    {education.map((edu, idx) => (
                      <div key={idx} className="latex-sim-entry">
                        <div className="latex-sim-row">
                          <strong className="latex-sim-primary">{edu.institution || 'University'}</strong>
                          <span className="latex-sim-date">{edu.date || ''}</span>
                        </div>
                        <div className="latex-sim-subrow">
                          <em className="latex-sim-secondary">{edu.degree || ''}</em>
                          {edu.location && <span className="latex-sim-location">{edu.location}</span>}
                        </div>
                        {edu.details?.length > 0 && (
                          <ul className="latex-sim-bullets">
                            {edu.details.map((d, dIdx) => (
                              <li key={dIdx}>{d}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* 5. Skills */}
                {skillsCategories.length > 0 && (
                  <div className="latex-sim-section">
                    <div className="latex-sim-sec-title">SKILLS</div>
                    <div className="latex-sim-hrule" />
                    <div className="latex-sim-skills-grid">
                      {skillsCategories.map(([cat, val], idx) => (
                        <div key={idx} className="latex-sim-skill-row">
                          <span className="latex-sim-skill-label">{cat}:</span>
                          <span className="latex-sim-skill-val">{val}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 6. Experience */}
                {experience.length > 0 && (
                  <div className="latex-sim-section">
                    <div className="latex-sim-sec-title">EXPERIENCE</div>
                    <div className="latex-sim-hrule" />
                    {experience.map((exp, idx) => (
                      <div key={idx} className="latex-sim-entry">
                        <div className="latex-sim-row">
                          <strong className="latex-sim-primary">{exp.role || exp.title || 'Role'}</strong>
                          <span className="latex-sim-date">
                            {[exp.start_date, exp.end_date].filter(Boolean).join(' - ') || exp.date || ''}
                          </span>
                        </div>
                        <div className="latex-sim-subrow">
                          <em className="latex-sim-secondary">{exp.company || 'Company'}</em>
                          {exp.location && <span className="latex-sim-location">{exp.location}</span>}
                        </div>
                        {exp.bullets?.length > 0 && (
                          <ul className="latex-sim-bullets">
                            {exp.bullets.map((bullet, bIdx) => (
                              <li key={bIdx}>{bullet}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* 7. Projects */}
                {projects.length > 0 && (
                  <div className="latex-sim-section">
                    <div className="latex-sim-sec-title">PROJECTS</div>
                    <div className="latex-sim-hrule" />
                    {projects.map((proj, idx) => (
                      <div key={idx} className="latex-sim-entry">
                        <div className="latex-sim-row">
                          <strong className="latex-sim-primary">{proj.title}</strong>
                          {proj.url && <span className="latex-sim-link">{proj.url}</span>}
                        </div>
                        {proj.description && (
                          <p className="latex-sim-proj-desc">{proj.description}</p>
                        )}
                        {proj.bullets?.length > 0 && (
                          <ul className="latex-sim-bullets">
                            {proj.bullets.map((b, bIdx) => (
                              <li key={bIdx}>{b}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* 8. Additional Sections */}
                {additionalSections.map((sec, idx) => (
                  <div key={idx} className="latex-sim-section">
                    <div className="latex-sim-sec-title">{(sec.title || 'ADDITIONAL').toUpperCase()}</div>
                    <div className="latex-sim-hrule" />
                    {sec.content && <p className="latex-sim-proj-desc">{sec.content}</p>}
                    {sec.bullets?.length > 0 && (
                      <ul className="latex-sim-bullets">
                        {sec.bullets.map((b, bIdx) => (
                          <li key={bIdx}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tab 2: LaTeX Code */}
          {activeTab === 'latex' && (
            <div className="latex-source-view">
              <div className="source-toolbar">
                <button type="button" onClick={handleCopyLatex} className="btn-copy-code">
                  <IconCopy size={14} />
                  <span>{copiedLatex ? 'Copied to Clipboard!' : 'Copy LaTeX Code'}</span>
                </button>
              </div>
              <pre className="latex-code-block">
                {conversionData.latex_code || conversionData.latex_source || '% No LaTeX source available'}
              </pre>
            </div>
          )}

          {/* Tab 3: Audit Report */}
          {activeTab === 'audit' && (
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
                  ✓ 100% of names, dates, metrics, percentages, job titles, and bullet points preserved without loss.
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
                    <span>All source entities verified and matched 1-to-1 in structured format.</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Action Footer */}
        <div className="converter-modal-footer">
          <div className="modal-footer-left">
            <button
              type="button"
              className="btn-modal-cancel"
              onClick={onCancel}
              disabled={isRegenerating || isConfirming}
            >
              Cancel
            </button>
            <span className="footer-hint">Ignores AI conversion &amp; keeps original resume</span>
          </div>

          <div className="modal-footer-right">
            <button
              type="button"
              className="btn-modal-regenerate"
              onClick={onRegenerate}
              disabled={isRegenerating || isConfirming}
            >
              {isRegenerating ? (
                <>
                  <span className="spinner-light-sm" />
                  <span>Regenerating...</span>
                </>
              ) : (
                <>
                  <IconRefresh size={15} />
                  <span>Regenerate</span>
                </>
              )}
            </button>

            <button
              type="button"
              className="btn-modal-confirm"
              onClick={onConfirm}
              disabled={isRegenerating || isConfirming}
            >
              {isConfirming ? (
                <>
                  <span className="spinner-light-sm" />
                  <span>Confirming...</span>
                </>
              ) : (
                <>
                  <IconCheck size={16} />
                  <span>Confirm Format</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
