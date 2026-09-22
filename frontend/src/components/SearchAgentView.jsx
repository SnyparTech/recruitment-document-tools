import React, { useState, useRef, useEffect, useCallback } from 'react';
import { getApiBase } from '../config';
import {
  IconSearch,
  IconBolt,
  IconEye,
  IconRocket,
  IconClipboard,
  IconCheck,
  IconAlert,
  IconDocument,
} from './Icons';

const RESULTS_POLL_INTERVAL_MS = 4000;

const PRESET_REQUIREMENTS = [
  "Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. Python, FastAPI, Machine Learning and NLP are mandatory. Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days.",
  "Senior Full Stack React and Node.js developer in Bengaluru with 4 to 8 years experience. AWS and Docker required. Budget 18 to 30 LPA.",
  "DevOps Cloud Engineer in Pune or Mumbai with Kubernetes, Terraform, and CI/CD pipelines. 3 to 6 years experience.",
];

export default function SearchAgentView({ onCompileCandidate }) {
  const API_BASE = getApiBase();
  const [prompt, setPrompt] = useState(PRESET_REQUIREMENTS[0]);
  const [executeMode, setExecuteMode] = useState('dry_run'); // 'dry_run', 'inspection', 'submit'
  const [isLoading, setIsLoading] = useState(false);
  const [searchResponse, setSearchResponse] = useState(null);
  const [error, setError] = useState(null);

  // Candidate results extracted from Resdex by the extension, polled after an
  // inspection/submit request. Ranking (match_score/data_completeness) is
  // computed server-side against the active SearchPlan — see
  // candidate_ranking_service.py. `null` while we haven't polled yet.
  const [candidateResults, setCandidateResults] = useState(null);
  // NOTE: search_response.execution.executed is ALWAYS false from this API —
  // actual execution happens asynchronously via the extension polling
  // /search/active-plan, not synchronously in this request. So "did we ask
  // the extension to act" is derived from the execution mode the recruiter
  // chose (inspection/submit both hand off to the extension), not from
  // `executed`. Derived, not separate state — avoids a redundant
  // setState-in-effect render just to mirror a value we already have.
  const isPollingResults = Boolean(searchResponse) && executeMode !== 'dry_run';

  // Which keywords HR currently wants marked mandatory (starred) in Resdex —
  // a subset, not the old all-or-nothing checkbox. Seeded from the plan's
  // keywords.required whenever a new plan arrives (new execute, or restored
  // on mount).
  const [mandatoryKeywords, setMandatoryKeywords] = useState(new Set());
  const [isApplyingKeywords, setIsApplyingKeywords] = useState(false);
  const [keywordApplyMsg, setKeywordApplyMsg] = useState(null);

  // Document Upload & Format Preservation State
  const [uploadedDoc, setUploadedDoc] = useState(null);
  const [isExtractingDoc, setIsExtractingDoc] = useState(false);
  const [docError, setDocError] = useState(null);
  const [isDraggingDoc, setIsDraggingDoc] = useState(false);
  const docInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  /**
   * Intelligently parses rich clipboard HTML (from Google AI Overview, Word, web pages, Notion, Docs)
   * into clean, faithfully formatted text preserving:
   * - Line breaks before/after headings and paragraphs
   * - Bullet points (•) for all list items
   * - Proper whitespace and indentations
   */
  const htmlToFormattedText = (htmlString) => {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(htmlString, 'text/html');

      // Drop non-content tags
      const dropSelectors = ['script', 'style', 'noscript', 'svg', 'button', 'nav'];
      doc.querySelectorAll(dropSelectors.join(',')).forEach((el) => el.remove());

      const walk = (node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          return node.nodeValue;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) {
          return '';
        }

        const tagName = node.tagName.toUpperCase();
        const role = node.getAttribute('role') || '';
        const className = typeof node.className === 'string' ? node.className : '';

        // Recursively build children text
        let childrenText = '';
        for (const child of node.childNodes) {
          childrenText += walk(child);
        }

        // 1. Headings (H1-H6 or role="heading")
        if (/^H[1-6]$/.test(tagName) || role === 'heading') {
          const text = childrenText.trim();
          return text ? `\n\n${text}\n\n` : '';
        }

        // 2. Paragraphs & Blockquotes
        if (tagName === 'P' || tagName === 'BLOCKQUOTE') {
          const text = childrenText.trim();
          return text ? `\n\n${text}\n` : '';
        }

        // 3. List Items (<li> or role="listitem" or .list-item)
        const isListItem =
          tagName === 'LI' ||
          role === 'listitem' ||
          className.includes('listitem') ||
          className.includes('list-item');

        if (isListItem) {
          const text = childrenText.trim();
          if (!text) return '';
          // Ensure every bullet point starts on its own line with a bullet symbol
          const alreadyHasBullet = /^[•\-\*\u2022\u25aa\u25b6]/.test(text);
          return `\n${alreadyHasBullet ? '' : '• '}${text}\n`;
        }

        // 4. Line Breaks
        if (tagName === 'BR') {
          return '\n';
        }

        // 5. Table Rows & Cells
        if (tagName === 'TR') {
          const text = childrenText.trim();
          return text ? `\n${text}` : '';
        }
        if (tagName === 'TD' || tagName === 'TH') {
          return ` ${childrenText.trim()} `;
        }

        // 6. Generic block containers (DIV, SECTION, ARTICLE)
        if (['DIV', 'SECTION', 'ARTICLE', 'MAIN'].includes(tagName)) {
          return `\n${childrenText}`;
        }

        return childrenText;
      };

      let result = walk(doc.body);

      // Clean up excessive blank lines (max 2 consecutive newlines)
      result = result
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .replace(/[ \t]+\n/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();

      return result;
    } catch (err) {
      console.warn('HTML format conversion error:', err);
      return '';
    }
  };

  /**
   * Lossless Paste Handler:
   * - Inspects both text/html and text/plain
   * - If HTML contains structural elements (headings, list items, paragraphs, divs)
   *   it converts them into structured text with explicit bullets and line breaks,
   *   preventing browser line-collapsing.
   * - If plain text has explicit lines/code formatting, preserves it exactly.
   */
  const handlePaste = (e) => {
    const clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData) return;

    const html = clipboardData.getData('text/html');
    const plain = clipboardData.getData('text/plain');

    let textToInsert = '';

    if (
      html &&
      (html.includes('<li') ||
        html.includes('<p') ||
        html.includes('<div') ||
        html.includes('<h') ||
        html.includes('<br') ||
        html.includes('role="listitem"') ||
        html.includes('role="heading"'))
    ) {
      const formattedFromHtml = htmlToFormattedText(html);
      const htmlLines = (formattedFromHtml.match(/\n/g) || []).length;
      const plainLines = (plain.match(/\n/g) || []).length;

      // If HTML conversion restored lost line breaks or bullet points, prefer it!
      if (htmlLines > plainLines || (formattedFromHtml.includes('•') && !plain.includes('•'))) {
        textToInsert = formattedFromHtml;
      } else {
        textToInsert = plain || formattedFromHtml;
      }
    } else {
      textToInsert = plain || '';
    }

    if (textToInsert) {
      e.preventDefault();
      const textarea = e.target;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const currentVal = textarea.value;
      const nextVal = currentVal.substring(0, start) + textToInsert + currentVal.substring(end);
      setPrompt(nextVal);
      requestAnimationFrame(() => {
        textarea.selectionStart = textarea.selectionEnd = start + textToInsert.length;
      });
    }
  };

  /**
   * Handles uploaded requirement document (PDF, DOCX, DOC, TXT):
   * Extracts text on backend preserving all line breaks, bullets, and sections.
   */
  const handleDocFile = async (file) => {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'doc', 'txt'].includes(ext)) {
      setDocError(`Unsupported format '.${ext}'. Please upload a PDF, DOCX, DOC, or TXT file.`);
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setDocError('File is too large. Maximum size allowed is 10 MB.');
      return;
    }

    setIsExtractingDoc(true);
    setDocError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch(`${API_BASE}/search/upload-requirement`, {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.message || `Upload failed with status ${resp.status}`);
      }

      const data = await resp.json();
      setUploadedDoc({
        filename: data.filename,
        size: data.size,
        lineCount: data.line_count,
        charCount: data.char_count,
      });

      // Populate prompt with the extracted requirement text (preserving exact formatting)
      setPrompt(data.extracted_text);
    } catch (err) {
      console.error('Failed to extract document:', err);
      setDocError(err.message || 'Failed to extract requirement text from document.');
    } finally {
      setIsExtractingDoc(false);
      if (docInputRef.current) docInputRef.current.value = '';
    }
  };

  const handleRemoveDoc = () => {
    setUploadedDoc(null);
    setDocError(null);
  };

  const executeSearch = async () => {
    if (!prompt.trim()) return;

    setIsLoading(true);
    setError(null);
    setSearchResponse(null);

    const payload = {
      requirement: prompt.trim(),
      execute: executeMode !== 'dry_run',
      submit_search: executeMode === 'submit',
    };

    try {
      const resp = await fetch(`${API_BASE}/search/candidates`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.message || errJson.detail || `HTTP Error ${resp.status}`);
      }

      const data = await resp.json();
      setSearchResponse(data);
    } catch (err) {
      console.error('Search request failed:', err);
      setError(err.message || 'Failed to execute search. Check backend connection.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e) => {
    if (e) e.preventDefault();
    executeSearch();
  };

  const pollCandidateResults = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/search/results`);
      if (!resp.ok) return;
      const data = await resp.json();
      setCandidateResults(data);
    } catch (err) {
      console.warn('Failed to poll candidate results:', err);
    }
  }, [API_BASE]);

  // Only poll once the recruiter has actually asked the extension to act on
  // Resdex (inspection/submit) — a dry-run plan has no candidates to fetch,
  // and polling unconditionally would be wasted network traffic.
  useEffect(() => {
    if (!isPollingResults) return;

    pollCandidateResults();
    const intervalId = setInterval(pollCandidateResults, RESULTS_POLL_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [isPollingResults, pollCandidateResults]);

  // Restore state on mount/refresh. The backend keeps the latest SearchPlan
  // and extracted candidates (now persisted to disk too — survives a backend
  // restart, not just a page refresh), but React state doesn't: a plain
  // refresh used to lose the whole results view even though the data was
  // still sitting server-side. Re-hydrate from /search/active-plan so the
  // candidate-results poll below picks back up automatically.
  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/search/active-plan`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.has_plan && data.plan) {
          setSearchResponse({
            validation: { valid: true, errors: [], warnings: [] },
            search_plan: data.plan,
            execution: {
              executed: false,
              message: 'Restored from a previous session.',
              fields_interacted: [],
            },
          });
          setExecuteMode((prev) => (prev === 'dry_run' ? 'inspection' : prev));
        }
      } catch (err) {
        console.warn('Failed to restore active plan on load:', err);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-seed the mandatory-keyword selection whenever a (new or restored) plan
  // arrives, from its keywords.required.
  useEffect(() => {
    const kw = searchResponse?.search_plan?.keywords;
    if (!kw) return;
    setMandatoryKeywords(new Set(kw.required || []));
  }, [searchResponse?.search_plan?.keywords]);

  const toggleMandatoryKeyword = (keyword) => {
    setMandatoryKeywords((prev) => {
      const next = new Set(prev);
      if (next.has(keyword)) next.delete(keyword);
      else next.add(keyword);
      return next;
    });
  };

  const applyMandatoryKeywords = async () => {
    const kw = searchResponse?.search_plan?.keywords;
    if (!kw) return;
    const allKeywords = [...new Set([...(kw.required || []), ...(kw.preferred || [])])];
    const required = allKeywords.filter((k) => mandatoryKeywords.has(k));
    const preferred = allKeywords.filter((k) => !mandatoryKeywords.has(k));

    setIsApplyingKeywords(true);
    setKeywordApplyMsg(null);
    try {
      const resp = await fetch(`${API_BASE}/search/plan/keywords`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ required, preferred }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail?.message || data.detail || 'Failed to update keywords.');

      setSearchResponse((prev) => prev && { ...prev, search_plan: data.plan });
      setKeywordApplyMsg({ ok: true, text: 'Applied — extension will click Modify and re-run the search on Resdex.' });
    } catch (err) {
      setKeywordApplyMsg({ ok: false, text: err.message || 'Failed to apply keyword changes.' });
    } finally {
      setIsApplyingKeywords(false);
    }
  };

  const handleCompile = (candidate) => {
    if (!onCompileCandidate) return;
    onCompileCandidate({
      name: candidate.name,
      notes: [
        candidate.title && `Title: ${candidate.title}`,
        candidate.company && `Company: ${candidate.company}`,
        candidate.location && `Location: ${candidate.location}`,
        candidate.experience && `Experience: ${candidate.experience}`,
        candidate.scored && `Match score: ${candidate.match_score}% (data completeness: ${candidate.data_completeness}%)`,
      ].filter(Boolean).join('\n'),
    });
  };

  return (
    <div>
      <div className="hero-section">
        <h1 className="hero-title">Candidate Search Agent</h1>
        <p className="hero-desc">
          Schema-driven autonomous recruitment intelligence. Type your natural-language candidate criteria
          below. The agent validates against the live portal schema and deterministically fills the search form.
        </p>
      </div>

      <div className="card">
        <h2 className="card-title">
          <IconSearch size={22} color="var(--primary)" />
          <span>Recruiter Requirement Criteria</span>
        </h2>
        <p className="card-subtitle">Select a preset or enter custom hiring requirements.</p>

        {/* Preset Chips */}
        <div className="preset-chips">
          {PRESET_REQUIREMENTS.map((req, i) => (
            <button
              key={i}
              type="button"
              className="preset-chip"
              onClick={() => setPrompt(req)}
            >
              Preset {i + 1}: {req.slice(0, 48)}...
            </button>
          ))}
        </div>

        <form onSubmit={handleSearch}>
          <div className="form-group" style={{ marginBottom: '20px' }}>
            {/* Hidden Document Input */}
            <input
              ref={docInputRef}
              id="doc-upload-input"
              name="docUpload"
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files?.[0]) handleDocFile(e.target.files[0]);
              }}
            />

            {/* Prompt Header with Upload Button */}
            <div className="prompt-header-row">
              <label htmlFor="jd-prompt-textarea" className="form-label">Requirement Prompt &amp; Job Criteria</label>
              <div className="prompt-actions">
                <button
                  type="button"
                  className="btn-upload-req-doc"
                  onClick={() => docInputRef.current?.click()}
                  disabled={isExtractingDoc}
                  title="Upload a Job Description or Requirement document (PDF, DOCX, DOC, TXT)"
                >
                  {isExtractingDoc ? (
                    <>
                      <span className="spinner-light-sm" style={{ borderColor: '#4F46E5', borderTopColor: 'transparent' }}></span>
                      <span>Extracting Document...</span>
                    </>
                  ) : (
                    <>
                      <IconDocument size={14} />
                      <span>Upload Requirement Doc / PDF</span>
                    </>
                  )}
                </button>

                {prompt && (
                  <button
                    type="button"
                    className="btn-clear-prompt"
                    onClick={() => {
                      setPrompt('');
                      setUploadedDoc(null);
                    }}
                    title="Clear prompt text"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            {/* Attached Document Banner */}
            {uploadedDoc && (
              <div className="doc-requirement-banner">
                <div className="doc-info-left">
                  <IconDocument size={18} color="#166534" />
                  <div className="doc-meta-text">
                    <span className="doc-name">{uploadedDoc.filename}</span>
                    <span className="doc-sub">
                      ({formatFileSize(uploadedDoc.size)} • {uploadedDoc.lineCount} lines extracted &amp; populated below)
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-remove-doc"
                  onClick={handleRemoveDoc}
                >
                  ✕ Remove
                </button>
              </div>
            )}

            {/* Error banner if doc extraction failed */}
            {docError && (
              <div className="inline-error" style={{ marginBottom: '10px' }}>
                <IconAlert size={16} color="#DC2626" />
                <span>{docError}</span>
              </div>
            )}

            {/* Exact-Format-Preserving Textarea */}
            <textarea
              id="jd-prompt-textarea"
              name="jdPrompt"
              className={`form-textarea ${isDraggingDoc ? 'prompt-drag-active' : ''}`}
              rows={8}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onPaste={handlePaste}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDraggingDoc(true);
              }}
              onDragLeave={() => setIsDraggingDoc(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDraggingDoc(false);
                if (e.dataTransfer.files?.[0]) handleDocFile(e.dataTransfer.files[0]);
              }}
              placeholder="Type your recruitment criteria, paste formatted text without changes, or drop/upload a Job Description (PDF, DOCX, DOC, TXT) to automate search in Naukri Resdex..."
            />

            {/* Prompt Helper / Format preservation indicator & counters */}
            <div className="prompt-meta-row">
              <span className="prompt-meta-hint">
                <IconCheck size={13} color="#10B981" />
                <span>100% exact format preserved on paste &amp; upload (newlines, tabs, indentations, bullets).</span>
              </span>
              <span className="prompt-meta-counts">
                {prompt ? prompt.split(/\r\n|\r|\n/).length : 0} lines • {prompt.length.toLocaleString()} chars
              </span>
            </div>
          </div>

          {/* Execution Mode Selector */}
          <div className="form-row" style={{ marginBottom: '24px' }}>
            <div className="form-group">
              <label htmlFor="execution-mode-dry-run" className="form-label">Execution Mode</label>
              <div className="execution-mode-selector">
                <label className={`mode-option-card ${executeMode === 'dry_run' ? 'active-dry' : ''}`}>
                  <input
                    id="execution-mode-dry-run"
                    type="radio"
                    name="mode"
                    value="dry_run"
                    checked={executeMode === 'dry_run'}
                    onChange={() => setExecuteMode('dry_run')}
                  />
                  <span className="mode-option-content">
                    <IconBolt size={15} color="var(--primary)" />
                    <span>Dry-Run Plan Only</span>
                  </span>
                </label>

                <label className={`mode-option-card ${executeMode === 'inspection' ? 'active-inspection' : ''}`}>
                  <input
                    type="radio"
                    name="mode"
                    value="inspection"
                    checked={executeMode === 'inspection'}
                    onChange={() => setExecuteMode('inspection')}
                  />
                  <span className="mode-option-content">
                    <IconEye size={15} color="var(--accent-emerald)" />
                    <span>Visual Form Fill (Inspection)</span>
                  </span>
                </label>

                <label className={`mode-option-card ${executeMode === 'submit' ? 'active-submit' : ''}`}>
                  <input
                    type="radio"
                    name="mode"
                    value="submit"
                    checked={executeMode === 'submit'}
                    onChange={() => setExecuteMode('submit')}
                  />
                  <span className="mode-option-content">
                    <IconRocket size={15} color="var(--accent-amber)" />
                    <span>Live Submit Search</span>
                  </span>
                </label>
              </div>
            </div>
          </div>

          {error && (
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
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="btn-primary-action"
            disabled={isLoading || !prompt.trim()}
          >
            {isLoading ? (
              <>
                <div className="spinner"></div>
                <span>Executing Agent Strategy...</span>
              </>
            ) : (
              <>
                <IconBolt size={18} color="#FFFFFF" />
                <span>
                  {executeMode === 'dry_run' && 'Generate & Validate SearchPlan'}
                  {executeMode === 'inspection' && 'Auto-Fill Open Resdex Tab (Inspection)'}
                  {executeMode === 'submit' && 'Execute Live Resdex Candidate Search'}
                </span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Results View */}
      {searchResponse && (
        <div className="card">
          <h3 className="card-title">
            <IconClipboard size={20} color="var(--primary)" />
            <span>Generated SearchPlan & Execution Status</span>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '3px 10px',
              borderRadius: '999px',
              background: searchResponse.validation.valid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
              color: searchResponse.validation.valid ? '#10B981' : '#F43F5E',
              border: `1px solid ${searchResponse.validation.valid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`
            }}>
              {searchResponse.validation.valid ? 'VALIDATED SCHEMA' : 'SCHEMA ERRORS'}
            </span>
          </h3>

          {isPollingResults && (
            <div style={{
              background: 'rgba(56, 189, 248, 0.08)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              padding: '16px',
              borderRadius: '8px',
              marginBottom: '16px'
            }}>
              <div style={{ fontWeight: 700, color: 'var(--primary)', marginBottom: '4px' }}>
                Execution Report
              </div>
              <div style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                {searchResponse.execution.message}
              </div>
              {searchResponse.execution.fields_interacted?.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {searchResponse.execution.fields_interacted.map((f, i) => (
                    <span key={i} className="skill-pill" style={{ fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <IconCheck size={11} color="var(--accent-emerald)" />
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}


          {searchResponse.search_plan.keywords &&
            (searchResponse.search_plan.keywords.required?.length > 0 ||
              searchResponse.search_plan.keywords.preferred?.length > 0) && (
            <div style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              padding: '14px',
              borderRadius: '8px',
              marginBottom: '16px',
            }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Mandatory keywords</div>
              <p className="card-subtitle" style={{ marginTop: 0, marginBottom: 10 }}>
                Star the keywords Resdex must require. Unstarred ones stay in the search as optional. Changing this
                re-runs the search live on the open Resdex tab (clicks Modify, updates stars, searches again).
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {[...new Set([
                  ...(searchResponse.search_plan.keywords.required || []),
                  ...(searchResponse.search_plan.keywords.preferred || []),
                ])].map((kw) => {
                  const isMandatory = mandatoryKeywords.has(kw);
                  return (
                    <button
                      key={kw}
                      type="button"
                      onClick={() => toggleMandatoryKeyword(kw)}
                      className="skill-pill"
                      style={{
                        cursor: 'pointer',
                        border: isMandatory ? '1px solid #F59E0B' : '1px solid rgba(255,255,255,0.15)',
                        background: isMandatory ? 'rgba(245, 158, 11, 0.12)' : 'transparent',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                      }}
                      title={isMandatory ? 'Mandatory — click to make optional' : 'Optional — click to make mandatory'}
                    >
                      <span>{isMandatory ? '★' : '☆'}</span>
                      {kw}
                    </button>
                  );
                })}
              </div>
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={applyMandatoryKeywords}
                  disabled={isApplyingKeywords}
                >
                  {isApplyingKeywords ? 'Applying...' : 'Apply to Resdex'}
                </button>
                {keywordApplyMsg && (
                  <span style={{ fontSize: '0.8rem', color: keywordApplyMsg.ok ? '#10B981' : '#F43F5E' }}>
                    {keywordApplyMsg.text}
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="code-box">
            {JSON.stringify(searchResponse.search_plan, null, 2)}
          </div>
        </div>
      )}

      {/* Extracted & Ranked Candidates (from the browser extension, polled from the backend) */}
      {isPollingResults && (
        <div className="card">
          <h3 className="card-title">
            <IconSearch size={20} color="var(--primary)" />
            <span>Candidates Found on Resdex</span>
            {isPollingResults && <span className="spinner-light-sm" style={{ marginLeft: 4 }}></span>}
          </h3>

          {!candidateResults || candidateResults.count === 0 ? (
            <p className="card-subtitle">
              Waiting for the browser extension to submit candidates extracted from the Resdex results page...
            </p>
          ) : (
            <>
              <p className="card-subtitle">
                {candidateResults.count} candidate(s) found
                {candidateResults.ranked_against_active_plan
                  ? ' — ranked against the active SearchPlan below.'
                  : ' — no active SearchPlan to rank against yet.'}
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {candidateResults.candidates.map((c, i) => (
                  <div key={i} style={{
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 8,
                    padding: 14,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div>
                        <div style={{ fontWeight: 700 }}>{c.name}</div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                          {[c.title, c.company, c.location].filter(Boolean).join(' • ') || 'No additional details extracted'}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        {c.scored ? (
                          <>
                            <div style={{ fontWeight: 800, fontSize: '1.1rem', color: c.match_score >= 70 ? '#10B981' : c.match_score >= 40 ? '#F59E0B' : '#F43F5E' }}>
                              {c.match_score}%
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                              {c.data_completeness}% data completeness
                            </div>
                          </>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Not yet scored</span>
                        )}
                      </div>
                    </div>

                    {(c.experience || c.education || c.notice_period || c.profile_url) && (
                      <div style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', flexWrap: 'wrap', gap: '4px 14px' }}>
                        {c.experience && <span><strong>Experience:</strong> {c.experience}</span>}
                        {c.education && <span><strong>Education:</strong> {c.education}</span>}
                        {c.notice_period && <span><strong>Notice:</strong> {c.notice_period}</span>}
                        {c.profile_url && <a href={c.profile_url} target="_blank" rel="noreferrer">View profile</a>}
                      </div>
                    )}

                    {c.skills?.length > 0 && (
                      <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                        <strong style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Skills on profile:</strong>
                        {c.skills.map((sk, si) => (
                          <span key={`s-${si}`} className="skill-pill" style={{ fontSize: '0.72rem' }}>{sk}</span>
                        ))}
                      </div>
                    )}

                    {(c.matched_requirements?.length > 0 || c.missing_requirements?.length > 0 || c.unavailable_info?.length > 0) && (
                      <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {c.matched_requirements?.map((m, mi) => (
                          <span key={`m-${mi}`} className="skill-pill" style={{ fontSize: '0.72rem', color: '#10B981' }}>✓ {m}</span>
                        ))}
                        {c.missing_requirements?.map((m, mi) => (
                          <span key={`x-${mi}`} className="skill-pill" style={{ fontSize: '0.72rem', color: '#F43F5E' }}>✗ {m}</span>
                        ))}
                        {c.unavailable_info?.map((u, ui) => (
                          <span key={`u-${ui}`} className="skill-pill" style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }} title="Requested in SearchPlan but no data was extracted for this candidate">? {u}</span>
                        ))}
                      </div>
                    )}

                    {onCompileCandidate && (
                      <button
                        type="button"
                        className="btn-clear-prompt"
                        style={{ marginTop: 10 }}
                        onClick={() => handleCompile(c)}
                      >
                        Compile Dossier
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
