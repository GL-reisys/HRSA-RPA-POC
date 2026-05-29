'use client';
import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';

export default function ZipUploadPage({ onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const handleUpload = async (file) => {
    if (!file) return;

    // Validate file extension
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Invalid Application filename extension - Please use a zip file with a Funding Opportunity Number');
      return;
    }

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
    multiple: false,
    disabled: uploading
  });

  return (
    <div style={{
      minHeight: '100vh',
      background: '#e5faff'
    }}>
      {/* HRSA Banner */}
      <div style={{
        background: '#005ea2',
        padding: '16px 32px',
        borderBottom: '4px solid #e87722'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          maxWidth: '1200px',
          margin: '0'
        }}>
           <img src="/logo-black-lg.png" alt="HRSA Logo" style={{ height: '50px', marginRight: '12px' }} /> 
          <div style={{
            fontSize: '40px',
            fontWeight: '700',
            color: 'white',
            letterSpacing: '-1px',
            marginRight: '16px'
          }}>
            HRSA
          </div>
          <div>
            <div style={{
              fontSize: '14px',
              fontWeight: '600',
              color: 'white',
              lineHeight: '1.2'
            }}>
              Health Resources & Services Administration
            </div>
            <div style={{
              fontSize: '12px',
              color: '#cbd5e1',
              lineHeight: '1.2'
            }}>
              U.S. Department of Health and Human Services
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{
        maxWidth: '900px',
        width: '100%',
        margin: '0 auto',
        padding: '40px 20px'
      }}>
          
          {/* Welcome Header */}
          <div style={{ marginBottom: '32px', textAlign: 'center' }}>
            <h1 style={{ 
              fontSize: '32px', 
              fontWeight: '700', 
              color: '#1e293b',
              marginBottom: '8px',
              marginTop: '0'
            }}>
              Welcome to the Application Validation Assistant
            </h1>
            <div style={{ fontSize: '32px', fontWeight: '700', color: '#1e293b', marginBottom: '16px' }}>
              (AVA)
            </div>
            <p style={{
              fontSize: '16px',
              color: '#475569',
              margin: '0',
              lineHeight: '1.5'
            }}>
              Upload your application package and let AVA validate your forms and attachments quickly.
            </p>
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
                Upload Your Application Package (ZIP)
              </h3>
              <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#0c4a6e', fontWeight: '700' }}>
                * Make sure the zip name is in the format HRSA-XX-YYY where XX is the year and YYY is the Funding Opportunity number. Example: HRSA-26-091
              </p>
              <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#0c4a6e', fontWeight: '700' }}>
                * Your application package should include one or both of the following forms and all supporting documents/attachments towards Application page limit
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
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#0c4a6e' }}>Performance Site</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3" style={{ marginRight: '6px' }}>
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                  <span style={{ fontSize: '14px', fontWeight: '600', color: '#0c4a6e' }}>Supporting documents/attachments towards Application page limit</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Progress Steps */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          marginBottom: '32px',
          paddingTop: '12px',
          gap: '24px'
        }}>
          {/* Step 1 */}
          <div style={{ 
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '12px',
              background: '#e5faff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '32px',
              marginBottom: '12px'
            }}>
              📁
            </div>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: '#2563eb',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: '700',
              fontSize: '16px',
              marginBottom: '8px'
            }}>
              1
            </div>
            <span style={{
              fontSize: '13px',
              fontWeight: '600',
              color: '#1e293b',
              whiteSpace: 'pre-line'
            }}>
              Upload ZIP file
            </span>
          </div>
          
          {/* Arrow */}
          <div style={{ textAlign: 'center', marginTop: '20px' }}>
            <div style={{ fontSize: '14px', fontWeight: '600', color: '#005ea2', marginBottom: '8px' }}>AVA Validates</div>
            <div style={{ fontSize: '24px', color: '#64748b' }}>──────▶</div>
          </div>
          
          {/* Step 3 */}
          <div style={{ 
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '12px',
              background: progress === 100 ? '#e5faff' : '#e5faff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '32px',
              marginBottom: '12px'
            }}>
              📊
            </div>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: progress === 100 ? '#2563eb' : '#e2e8f0',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: '700',
              fontSize: '16px',
              marginBottom: '8px'
            }}>
              2
            </div>
            <span style={{
              fontSize: '13px',
              fontWeight: '600',
              color: progress === 100 ? '#1e293b' : '#94a3b8',
              whiteSpace: 'pre-line'
            }}>
              Review & Results
            </span>
          </div>
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
                Validating your application...
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
                Please wait...
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
              <p style={{ fontSize: '13px', color: '#475569', marginTop: '20px', fontWeight: '500' }}>
                Accepted format: .zip | Maximum size: 200 MB
              </p>
              <p style={{ fontSize: '13px', color: '#475569', marginTop: '8px', fontWeight: '500' }}>
                Make sure the zip name is in the format HRSA-XX-YYY where XX is the year and YYY is the funding opportunity number. Example: HRSA-26-091
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

        {/* Help Section */}
        <div style={{
          marginTop: '32px',
          padding: '20px',
          background: '#f0f9ff',
          borderRadius: '8px',
          border: '2px solid #0ea5e9',
          textAlign: 'center'
        }}>
          <a 
            href="https://help.hrsa.gov/pages/releaseview.action?pageId=4816898&IsPopUp=true" 
            target="_blank" 
            rel="noopener noreferrer"
            style={{ 
              textDecoration: 'none'
            }}
          >
            <div style={{ fontSize: '16px', fontWeight: '700', color: '#0ea5e9', marginBottom: '4px' }}>
              Need Help?
            </div>
            <div style={{ fontSize: '14px', color: '#0c4a6e' }}>
              Learn more about forms, file requirements, and AVA
            </div>
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
