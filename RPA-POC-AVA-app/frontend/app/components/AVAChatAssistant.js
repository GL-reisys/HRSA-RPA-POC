'use client';

import { useState, useCallback } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  CircularProgress,
  Alert,
  Button
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ChatInterface from './ChatInterface';

async function readJsonOrText(response) {
  const body = await response.text();

  if (!body) {
    return null;
  }

  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

export default function AVAChatAssistant() {
  const [file, setFile] = useState(null);
  const [fileId, setFileId] = useState(null);
  const [formType, setFormType] = useState(null);
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

      const uploadPayload = await readJsonOrText(uploadResponse);

      if (!uploadResponse.ok) {
        const message =
          (uploadPayload && typeof uploadPayload === 'object' && uploadPayload.error) ||
          (typeof uploadPayload === 'string' && uploadPayload) ||
          'Upload failed';
        throw new Error(message);
      }

      if (!uploadPayload || typeof uploadPayload !== 'object') {
        throw new Error('Upload returned an unexpected response.');
      }

      const uploadResult = uploadPayload;
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

      const analyzePayload = await readJsonOrText(analyzeResponse);

      if (!analyzeResponse.ok) {
        const message =
          (analyzePayload && typeof analyzePayload === 'object' && analyzePayload.error) ||
          (typeof analyzePayload === 'string' && analyzePayload) ||
          'Analysis failed';
        throw new Error(message);
      }

      if (!analyzePayload || typeof analyzePayload !== 'object') {
        throw new Error('Analysis returned an unexpected response.');
      }

      const analyzeResult = analyzePayload;
      
      setFormType(analyzeResult.form_type || 'SF-424');
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
    setFormType(null);
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
        formType={formType}
        formData={formData}
        validationErrors={validationErrors}
        initialResponse={aiResponse}
        chatHistory={chatHistory}
        onReset={handleReset}
      />
    );
  }

  return (
    <Box sx={{ 
      minHeight: '100vh',
      backgroundColor: '#f5f7f9',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      p: 3
    }}>
      <Paper 
        elevation={8} 
        sx={{ 
          maxWidth: 550,
          width: '100%',
          p: 5,
          borderRadius: 3,
          textAlign: 'center'
        }}
      >
        <Box sx={{ mb: 4 }}>
          <Typography 
            variant="h4" 
            sx={{ 
              fontWeight: 700,
              color: '#1e4d5a',
              mb: 1
            }}
          >
            AVA
          </Typography>
          <Typography variant="h6" sx={{ color: '#424242', fontWeight: 500 }}>
            Application Validation Assistant
          </Typography>
        </Box>

        {uploading || analyzing ? (
          <Box sx={{ py: 4 }}>
            <CircularProgress size={60} sx={{ mb: 3, color: '#1e4d5a' }} />
            <Typography variant="h6" sx={{ color: '#424242', fontWeight: 500, mb: 1 }}>
              {uploading ? 'Uploading PDF...' : 'Analyzing form...'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {analyzing && 'Extracting form fields and validating data...'}
            </Typography>
          </Box>
        ) : (
          <Box>
            <Typography variant="h6" sx={{ color: '#1e4d5a', fontWeight: 600, mb: 2 }}>
              Upload SF-424 Form
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
              Get instant validation and AI-powered assistance
            </Typography>
            
            <Box
              {...getRootProps()}
              sx={{
                p: 4,
                border: '2px dashed #e0e0e0',
                borderRadius: 2,
                backgroundColor: isDragActive ? '#f0f8ff' : '#fafafa',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                mb: 3,
                '&:hover': {
                  backgroundColor: '#f5f5f5',
                  borderColor: '#1e4d5a'
                }
              }}
            >
              <input {...getInputProps()} />
              <UploadFileIcon sx={{ fontSize: 60, color: '#1e4d5a', mb: 2 }} />
              <Typography variant="body1" sx={{ color: '#424242', mb: 1 }}>
                Drag and drop your PDF here
              </Typography>
              <Typography variant="body2" color="text.secondary">
                or click to browse
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
                PDF files only (Max 10MB)
              </Typography>
            </Box>

            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            <Button
              variant="text"
              sx={{ 
                color: '#1e4d5a',
                textTransform: 'none',
                fontWeight: 500,
                '&:hover': {
                  backgroundColor: 'transparent',
                  textDecoration: 'underline'
                }
              }}
            >
              Need help?
            </Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
