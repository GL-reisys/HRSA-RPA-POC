'use client';

import { useState, useCallback } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  CircularProgress,
  Alert
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ChatInterface from './ChatInterface';

export default function AVAChatAssistant() {
  const [file, setFile] = useState(null);
  const [fileId, setFileId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const [aiResponse, setAiResponse] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);

  const onDrop = useCallback(async (acceptedFiles) => {
    const uploadedFile = acceptedFiles[0];
    
    if (!uploadedFile) return;
    
    if (uploadedFile.type !== 'application/pdf') {
      setError('Please upload a PDF file');
      return;
    }

    if (uploadedFile.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      return;
    }

    setFile(uploadedFile);
    setError(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);

      const uploadResponse = await fetch('/api/pdf/upload', {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json();
        throw new Error(errorData.error || 'Upload failed');
      }

      const uploadResult = await uploadResponse.json();
      setFileId(uploadResult.file_id);
      
      setAnalyzing(true);
      
      const analyzeResponse = await fetch('/api/pdf/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_id: uploadResult.file_id,
          file_name: uploadedFile.name,
          message: 'Please analyze this SF-424 form.'
        }),
      });

      if (!analyzeResponse.ok) {
        const errorData = await analyzeResponse.json();
        throw new Error(errorData.error || 'Analysis failed');
      }

      const analyzeResult = await analyzeResponse.json();
      
      setFormData(analyzeResult.form_data);
      setValidationErrors(analyzeResult.validation_errors || []);
      setAiResponse(analyzeResult.ai_response);
      
      setChatHistory([
        {
          role: 'user',
          content: 'Please analyze this SF-424 form.',
          timestamp: new Date().toISOString()
        },
        {
          role: 'assistant',
          content: analyzeResult.ai_response,
          timestamp: new Date().toISOString()
        }
      ]);

    } catch (err) {
      console.error('Error:', err);
      setError(err.message);
      setFile(null);
      setFileId(null);
    } finally {
      setUploading(false);
      setAnalyzing(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    maxFiles: 1,
    multiple: false
  });

  const handleReset = async () => {
    if (fileId) {
      try {
        await fetch('/api/session/clear', {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ file_id: fileId }),
        });
      } catch (err) {
        console.error('Error clearing session:', err);
      }
    }
    
    setFile(null);
    setFileId(null);
    setFormData(null);
    setValidationErrors([]);
    setAiResponse(null);
    setChatHistory([]);
    setError(null);
  };

  if (fileId && aiResponse) {
    return (
      <ChatInterface
        fileId={fileId}
        fileName={file?.name}
        formData={formData}
        validationErrors={validationErrors}
        initialResponse={aiResponse}
        chatHistory={chatHistory}
        onReset={handleReset}
      />
    );
  }

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', mt: 4 }}>
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>
          AVA Chat Assistant
        </Typography>
      </Paper>

      <Paper 
        elevation={1} 
        sx={{ 
          p: 6, 
          textAlign: 'center',
          border: '2px dashed #ccc',
          backgroundColor: isDragActive ? '#f0f8ff' : '#fafafa',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          '&:hover': {
            backgroundColor: '#f5f5f5',
            borderColor: '#999'
          }
        }}
      >
        {uploading || analyzing ? (
          <Box>
            <CircularProgress size={60} sx={{ mb: 2 }} />
            <Typography variant="h6" color="text.secondary">
              {uploading ? 'Uploading PDF...' : 'Analyzing form...'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {analyzing && 'Extracting form fields and validating data...'}
            </Typography>
          </Box>
        ) : (
          <div {...getRootProps()}>
            <input {...getInputProps()} />
            <UploadFileIcon sx={{ fontSize: 80, color: 'primary.main', mb: 2 }} />
            <Typography variant="h5" gutterBottom sx={{ color: '#003366', fontWeight: 600 }}>
              Upload SF-424 Form for Validation
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
              Drag and drop your PDF file here
            </Typography>
            <Typography variant="body2" color="text.secondary">
              or click to browse
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 3, display: 'block' }}>
              Supported: PDF files only (Max 10MB)
            </Typography>
          </div>
        )}
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
    </Box>
  );
}
