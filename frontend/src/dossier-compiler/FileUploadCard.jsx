import React, { useRef } from 'react';
import { IconCheck } from '../components/Icons';

export default function FileUploadCard({
  title,
  icon,
  accept,
  formatsText,
  file,
  preview,
  onFileSelect,
}) {
  const inputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0]);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileSelect(e.dataTransfer.files[0]);
    }
  };

  return (
    <div
      className={`upload-box ${file ? 'has-file' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {file ? (
        <div className="file-preview">
          {preview ? (
            <img src={preview} alt="Preview" className="photo-thumb" />
          ) : (
            <div style={{ fontSize: '42px', marginBottom: '8px' }}>{icon}</div>
          )}
          <div className="file-name-pill">{file.name}</div>
          <div className="file-size-text">{(file.size / 1024).toFixed(1)} KB</div>
          <span style={{ fontSize: '0.72rem', color: 'var(--accent-emerald)', marginTop: '4px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <IconCheck size={12} color="var(--accent-emerald)" /> Ready to compile
          </span>
        </div>
      ) : (
        <>
          <div className="upload-icon">{icon}</div>
          <div className="upload-heading">{title}</div>
          <div className="upload-formats">{formatsText}</div>
          <div className="upload-btn-ghost">Browse File</div>
        </>
      )}
    </div>
  );
}
