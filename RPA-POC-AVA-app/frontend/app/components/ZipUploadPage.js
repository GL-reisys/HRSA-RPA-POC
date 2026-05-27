'use client';
import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';

export default function ZipUploadPage({ onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const handleUpload = async (file) => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setProgress(10);

    try {
      const formData = new FormData();
      formData.append('file', file);

      setProgress(30);

      const response = await fetch('/api/zip/upload', {
        method: 'POST',
        body: formData,
      });

      setProgress(70);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Upload failed');
      }

      const result = await response.json();
      setProgress(100);

      setTimeout(() => {
        onUploadComplete(result);
      }, 300);

    } catch (err) {
      console.error('Upload error:', err);
      setError(err.message);
      setProgress(0);
    } finally {
      setTimeout(() => setUploading(false), 500);
    }
  };

  const onDrop = (acceptedFiles) => {
    if (acceptedFiles && acceptedFiles.length > 0) {
      handleUpload(acceptedFiles[0]);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/zip': ['.zip'],
      'application/x-zip-compressed': ['.zip']
    },
    multiple: false,
    disabled: uploading
  });

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f8fafc',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '16px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        maxWidth: '850px',
        width: '100%',
        padding: '48px'
      }}>
        
        {/* Header - HRSA and AVA */}
        <div style={{ marginBottom: '32px' }}>
          {/* HRSA Badge */}
          <div style={{
            display: 'inline-block',
            background: '#f1f5f9',
            padding: '6px 16px',
            borderRadius: '20px',
            marginBottom: '20px'
          }}>
            <span style={{
              fontSize: '12px',
              fontWeight: '600',
              color: '#475569',
              letterSpacing: '0.5px'
            }}>
              HRSA · Health Resources & Services Administration
            </span>
          </div>
          
          {/* AVA Logo and Title */}
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: '#2563eb',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginRight: '14px'
            }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h1 style={{ 
                fontSize: '28px', 
                fontWeight: '700', 
                color: '#1e293b',
                marginBottom: '2px',
                marginTop: '0'
              }}>
                AVA
              </h1>
              <p style={{ 
                fontSize: '14px', 
                color: '#64748b',
                margin: '0'
              }}>
                Application Validation Assistant
              </p>
            </div>
          </div>
        </div>

        {/* Info Box - What to Include */}
        <div style={{
          background: '#f0f9ff',
          border: '2px solid #0ea5e9',
          borderRadius: '12px',
          padding: '20px 24px',
          marginBottom: '24px'
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: '12px' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" strokeWidth="2" style={{ marginRight: '12px', flexShrink: 0 }}>
              <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <div>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '16px', fontWeight: '700', color: '#0c4a6e' }}>
                Upload Your Application Package
              </h3>
              <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#0c4a6e' }}>
                Your ZIP package should include one or both of the following forms and all supporting documents.
              </p>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3" style={{ marginRight: '6px' }}>
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#0c4a6e' }}>SF-424 form</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3" style={{ marginRight: '6px' }}>
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#0c4a6e' }}>PPOP form</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3" style={{ marginRight: '6px' }}>
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#0c4a6e' }}>Supporting documents</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Progress Steps */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-around',
          marginBottom: '32px',
          paddingTop: '12px'
        }}>
          {[
            { num: 1, label: 'Upload\nZIP file', icon: '📁', active: true },
            { num: 2, label: 'AVA\nValidates', icon: '✅', active: uploading },
            { num: 3, label: 'Review\nResults', icon: '📊', active: progress === 100 }
          ].map((step, idx) => (
            <div key={idx} style={{ 
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center'
            }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '12px',
                background: step.active ? '#e0f2fe' : '#f1f5f9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '32px',
                marginBottom: '12px',
                transition: 'all 0.3s ease'
              }}>
                {step.icon}
              </div>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: step.active ? '#2563eb' : '#e2e8f0',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                fontSize: '16px',
                marginBottom: '8px'
              }}>
                {step.num}
              </div>
              <span style={{
                fontSize: '13px',
                fontWeight: '600',
                color: step.active ? '#1e293b' : '#94a3b8',
                whiteSpace: 'pre-line'
              }}>
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {/* Upload Zone */}
        <div
          {...getRootProps()}
          style={{
            border: isDragActive ? '2px dashed #2563eb' : '2px dashed #cbd5e0',
            borderRadius: '12px',
            padding: '56px 32px',
            textAlign: 'center',
            cursor: uploading ? 'not-allowed' : 'pointer',
            background: '#fafbfc',
            transition: 'all 0.3s ease',
            marginBottom: '24px'
          }}
        >
          <input {...getInputProps()} />
          
          {uploading ? (
            <div>
              <div style={{
                width: '64px',
                height: '64px',
                border: '4px solid #e2e8f0',
                borderTop: '4px solid #2563eb',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
                margin: '0 auto 16px'
              }} />
              <p style={{ 
                fontSize: '18px', 
                color: '#1e293b',
                fontWeight: '600',
                marginBottom: '8px'
              }}>
                Processing your ZIP file...
              </p>
              <div style={{
                width: '200px',
                height: '6px',
                background: '#e2e8f0',
                borderRadius: '3px',
                overflow: 'hidden',
                margin: '16px auto'
              }}>
                <div style={{
                  height: '100%',
                  background: '#2563eb',
                  width: `${progress}%`,
                  transition: 'width 0.3s ease'
                }} />
              </div>
              <p style={{ fontSize: '14px', color: '#64748b' }}>
                {progress}% complete
              </p>
            </div>
          ) : (
            <div>
              {/* ZIP icon */}
              <div style={{
                width: '72px',
                height: '72px',
                margin: '0 auto 20px',
                position: 'relative'
              }}>
                <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
                  <rect x="16" y="8" width="40" height="52" rx="3" fill="white" stroke="#cbd5e0" strokeWidth="2"/>
                  <rect x="30" y="24" width="18" height="12" rx="2" fill="#2563eb"/>
                  <text x="36" y="34" fill="white" fontSize="10" fontWeight="bold">ZIP</text>
                  <circle cx="52" cy="52" r="14" fill="#2563eb"/>
                  <path d="M52 46v12m-6-6h12" stroke="white" strokeWidth="3" strokeLinecap="round"/>
                </svg>
              </div>
              <h3 style={{ 
                fontSize: '20px', 
                color: '#1e293b',
                fontWeight: '600',
                marginBottom: '8px',
                marginTop: '0'
              }}>
                {isDragActive ? 'Drop your ZIP file here' : 'Drag and drop your ZIP file here'}
              </h3>
              <p style={{ fontSize: '14px', color: '#94a3b8', marginBottom: '20px' }}>
                or
              </p>
              <button
                type="button"
                style={{
                  background: '#2563eb',
                  color: 'white',
                  padding: '12px 32px',
                  borderRadius: '8px',
                  border: 'none',
                  fontSize: '15px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease'
                }}
                onMouseOver={(e) => e.currentTarget.style.background = '#1d4ed8'}
                onMouseOut={(e) => e.currentTarget.style.background = '#2563eb'}
              >
                Browse files
              </button>
              <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '20px' }}>
                Accepted format: .zip  |  Maximum size: 200 MB
              </p>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div style={{
            background: '#fff5f5',
            border: '1px solid #fc8181',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '24px'
          }}>
            <p style={{ color: '#c53030', fontSize: '14px', margin: 0 }}>
              <strong>Error:</strong> {error}
            </p>
          </div>
        )}

        {/* File Requirements */}
        <div style={{
          background: '#f8fafc',
          borderRadius: '8px',
          padding: '24px',
          border: '1px solid #e2e8f0'
        }}>
          <h3 style={{ 
            fontSize: '15px', 
            fontWeight: '700', 
            color: '#1e293b',
            marginTop: '0',
            marginBottom: '20px'
          }}>
            Your ZIP file should include:
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
            <div style={{ flex: '1 1 200px' }}>
              <div style={{ display: 'flex', alignItems: 'start' }}>
                <div style={{ fontSize: '24px', marginRight: '12px' }}>📄</div>
                <div>
                  <div style={{ fontWeight: '600', color: '#1e293b', fontSize: '14px', marginBottom: '4px' }}>SF-424 form</div>
                  <div style={{ color: '#64748b', fontSize: '13px' }}>Required if applicable</div>
                </div>
              </div>
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <div style={{ display: 'flex', alignItems: 'start' }}>
                <div style={{ fontSize: '24px', marginRight: '12px' }}>📍</div>
                <div>
                  <div style={{ fontWeight: '600', color: '#1e293b', fontSize: '14px', marginBottom: '4px' }}>PPOP form</div>
                  <div style={{ color: '#64748b', fontSize: '13px' }}>Required if applicable</div>
                </div>
              </div>
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <div style={{ display: 'flex', alignItems: 'start' }}>
                <div style={{ fontSize: '24px', marginRight: '12px' }}>📎</div>
                <div>
                  <div style={{ fontWeight: '600', color: '#1e293b', fontSize: '14px', marginBottom: '4px' }}>Attachments</div>
                  <div style={{ color: '#64748b', fontSize: '13px' }}>As needed</div>
                </div>
              </div>
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <div style={{ display: 'flex', alignItems: 'start' }}>
                <div style={{ fontSize: '24px', marginRight: '12px' }}>📊</div>
                <div>
                  <div style={{ fontWeight: '600', color: '#1e293b', fontSize: '14px', marginBottom: '4px' }}>File size</div>
                  <div style={{ color: '#64748b', fontSize: '13px' }}>Under 200 MB</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Help Section */}
        <div style={{
          marginTop: '32px',
          padding: '16px 20px',
          background: '#f8fafc',
          borderRadius: '8px',
          border: '1px solid #e2e8f0',
          textAlign: 'center'
        }}>
          <a 
            href="https://help.hrsa.gov/x/MoAfFg" 
            target="_blank" 
            rel="noopener noreferrer"
            style={{ 
              color: '#2563eb', 
              fontSize: '14px',
              textDecoration: 'none',
              fontWeight: '600'
            }}
          >
            Need Help?
          </a>
        </div>
      </div>

      {/* Animations */}
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
