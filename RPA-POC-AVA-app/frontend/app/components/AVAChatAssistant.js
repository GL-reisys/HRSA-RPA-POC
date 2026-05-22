'use client';

import { useState, useCallback, useEffect } from 'react';
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
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState(null);
  const [validationErrors, setValidationErrors] = useState([]);
  const [aiResponse, setAiResponse] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);

  // Prevent browser from opening/downloading files on drag
  useEffect(() => {
    const preventDefault = (e) => {
      e.preventDefault();
      e.stopPropagation();
    };

    window.addEventListener('dragover', preventDefault);
    window.addEventListener('drop', preventDefault);

    return () => {
      window.removeEventListener('dragover', preventDefault);
      window.removeEventListener('drop', preventDefault);
    };
  }, []);

  const onDrop = useCallback(async (acceptedFiles) => {
    const uploadedFile = acceptedFiles[0];
    
    if (!uploadedFile) return;
    
    // ONLY accept ZIP files
    const isZip = uploadedFile.name.toLowerCase().endsWith('.zip');
    
    if (!isZip) {
      setError('Please upload a ZIP file containing SF-424, PPOP, and attachments');
      return;
    }

    const maxSize = 200 * 1024 * 1024; // 200MB for ZIP
    if (uploadedFile.size > maxSize) {
      setError('File size must be less than 200MB');
      return;
    }

    setFile(uploadedFile);
    setError(null);
    setUploading(true);
    setFormData(null);
    setChatHistory([]);

    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);

      const uploadResponse = await fetch('/api/zip/upload', {
        method: 'POST',
        body: formData,
      });

      const uploadPayload = await readJsonOrText(uploadResponse);

      if (!uploadResponse.ok) {
        const message =
          (uploadPayload && typeof uploadPayload === 'object' && uploadPayload.error) ||
          (typeof uploadPayload === 'string' && uploadPayload) ||
          'ZIP upload failed';
        throw new Error(message);
      }

      // Convert ZIP results to chat format like prod
      const zipResult = uploadPayload;
      setFileId(zipResult.file_id);
      setFormType('ZIP');
      
      // Build AI response matching prod format EXACTLY
      let aiMessage = '';
      
      // SF-424 Section
      aiMessage += '**📄 SF-424 Form Validation:**\n';
      
      // Check if SF-424 file exists in files list
      const sf424FileFound = zipResult.attachments?.files?.some(f => 
        f.file_type === 'form' && f.form_name === 'SF-424'
      );
      
      if (zipResult.sf424_validation) {
        const sf424 = zipResult.sf424_validation;
        const fields = sf424.fields || {};
        const hasErrors = sf424.validation_results && !sf424.validation_results.valid;
        
        if (sf424.extracted) {
          const errors = sf424.validation_results?.errors || [];
          const errorFieldNames = new Set(errors.map(e => e.field_name).filter(Boolean));
          
          if (hasErrors) {
            aiMessage += 'Here is a quick summary:\n\n';
            aiMessage += '**Need to fix the following error(s):**\n';
            errors.forEach(err => {
              // Extract field name from user_message if field_name is null
              const fieldName = err.field_name || err.user_message.split(' is ')[0] || 'Unknown Field';
              aiMessage += `   ❌ ${fieldName}\n`;
            });
            aiMessage += '\n';
          }
          
          // Show validated fields (fields that have values and no errors)
          aiMessage += '**Fields validated successfully:**\n';
          let hasValidFields = false;
          if (fields.application_type && !errorFieldNames.has('Type of Application')) {
            aiMessage += `   ✅ Application Type\n`;
            hasValidFields = true;
          }
          if (fields.funding_opportunity_number && !errorFieldNames.has('Funding Opportunity Number')) {
            aiMessage += `   ✅ Funding Opportunity Number\n`;
            hasValidFields = true;
          }
          if (fields.samuei && !errorFieldNames.has('UEI') && !errorFieldNames.has('UEI (Unique Entity Identifier)')) {
            aiMessage += `   ✅ UEI\n`;
            hasValidFields = true;
          }
          if (fields.organization_name && !errorFieldNames.has('Organization Name')) {
            aiMessage += `   ✅ Organization Name\n`;
            hasValidFields = true;
          }
          if (!hasValidFields) {
            aiMessage += '   (No fields validated yet)\n';
          }
          aiMessage += '\n';
          
          // Detailed error explanations with formatting
          if (hasErrors && errors.length > 0) {
            errors.forEach((err, index) => {
              aiMessage += `**${index + 1}. ${err.user_message}**\n`;
              
              // How to Fix section (blue color using HTML)
              if (err.guidance) {
                aiMessage += '   <span style="color: #0066cc; font-weight: 600;">How to Fix:</span>\n';
                // Convert HTML to plain text for display
                const guidanceText = err.guidance.replace(/<br>/g, '\n   ');
                const cleanGuidance = guidanceText.replace(/<[^>]+>/g, '');
                cleanGuidance.split('\n').forEach(line => {
                  if (line.trim()) {
                    aiMessage += `   ${line.trim()}\n`;
                  }
                });
              }
              aiMessage += '\n';
            });
          }
        } else if (sf424FileFound) {
          aiMessage += '⚠️ SF-424 form found but could not be extracted\n';
          aiMessage += '   File may be corrupted or encrypted\n\n';
        } else {
          aiMessage += '⚠️ SF-424 form not found in ZIP\n';
          aiMessage += '   Expected filename pattern: SF424_4_0 or SF-424\n\n';
        }
      } else if (sf424FileFound) {
        aiMessage += '⚠️ SF-424 form found but could not be extracted\n';
        aiMessage += '   File may be corrupted or encrypted\n\n';
      } else {
        aiMessage += '⚠️ SF-424 form not found in ZIP\n';
        aiMessage += '   Expected filename pattern: SF424_4_0 or SF-424\n\n';
      }
      
      // PPOP Section
      aiMessage += '**📍 PPOP Form Validation:**\n';
      
      // Check if PPOP file exists in files list
      const ppopFileFound = zipResult.attachments?.files?.some(f => 
        f.file_type === 'form' && f.form_name === 'PPOP'
      );
      
      if (zipResult.ppop_validation) {
        const ppop = zipResult.ppop_validation;
        
        if (ppop.extracted) {
          if (ppop.validation_results && ppop.validation_results.valid) {
            aiMessage += '✅ All PPOP validations passed\n\n';
          } else if (ppop.validation_results && ppop.validation_results.errors) {
            const ppopErrors = ppop.validation_results.errors;
            aiMessage += `❌ ${ppop.validation_results.error_count} validation error(s) found:\n\n`;
            ppopErrors.forEach((err, index) => {
              aiMessage += `${index + 1}. ${err.user_message}\n`;
              
              // Field details if available
              if (err.field_location || err.current_value) {
                aiMessage += '   📋 **Field Details:**\n';
                if (err.field_location) {
                  aiMessage += `   • ${err.field_location}\n`;
                  if (err.field_name) {
                    aiMessage += `      ${err.field_name} field\n`;
                  }
                }
                if (err.current_value) {
                  aiMessage += `   • Current Value: ${err.current_value}\n`;
                }
                aiMessage += '\n';
              }
              
              // How to Fix section
              if (err.guidance) {
                aiMessage += '   **How to Fix:**\n';
                const guidanceText = err.guidance.replace(/<br>/g, '\n   ');
                const cleanGuidance = guidanceText.replace(/<[^>]+>/g, '');
                cleanGuidance.split('\n').forEach(line => {
                  if (line.trim()) {
                    aiMessage += `   ${line.trim()}\n`;
                  }
                });
              }
              aiMessage += '\n';
            });
          }
        } else if (ppopFileFound) {
          aiMessage += '⚠️ PPOP form found but could not be extracted\n';
          aiMessage += '   File may be corrupted or encrypted\n\n';
        } else {
          aiMessage += '⚠️ PPOP form not found in ZIP\n';
          aiMessage += '   Expected filename pattern: PerformanceSite_4_0 or PPOP\n\n';
        }
      } else if (ppopFileFound) {
        aiMessage += '⚠️ PPOP form found but could not be extracted\n';
        aiMessage += '   File may be corrupted or encrypted\n\n';
      } else {
        aiMessage += '⚠️ PPOP form not found in ZIP\n';
        aiMessage += '   Expected filename pattern: PerformanceSite_4_0 or PPOP\n\n';
      }
      
      // Page Count Section
      if (zipResult.attachments) {
        const att = zipResult.attachments;
        aiMessage += '**📎 Page Count Validation:**\n';
        
        const maxAttPages = att.max_attachment_page_count;
        const attPages = att.attachment_pages || 0;
        const formPages = att.form_pages || 0;
        
        if (maxAttPages !== null && maxAttPages !== undefined) {
          if (att.page_count_ok) {
            aiMessage += `✅ Total: ${attPages} pages attached (max attachment page limit: ${maxAttPages})\n`;
          } else {
            aiMessage += `⚠️ Page count EXCEEDED: ${attPages} pages (max attachment page limit: ${maxAttPages})\n`;
          }
        } else {
          aiMessage += `Total: ${attPages} pages attached\n`;
        }
        
        aiMessage += `\nFiles processed: ${att.total_files}\n`;
        
        // Count and list attachments
        const attachments = att.files ? att.files.filter(f => f.file_type === 'attachment') : [];
        const convertedFiles = attachments.filter(f => f.converted);
        
        aiMessage += `Attachments found: ${attachments.length}\n`;
        if (convertedFiles.length > 0) {
          aiMessage += `Attachments converted to PDF: ${convertedFiles.length}\n\n`;
          aiMessage += 'Converted files:\n';
          convertedFiles.forEach(f => {
            aiMessage += `   • ${f.name}\n`;
          });
        }
      }
      
      setFormData(zipResult);
      setAiResponse(aiMessage);
      setValidationErrors([]);
      
      // Initialize chat with validation results
      setChatHistory([
        {
          role: 'user',
          content: `Uploaded: ${uploadedFile.name}`,
          timestamp: new Date().toISOString()
        },
        {
          role: 'assistant',
          content: aiMessage,
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
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/zip': ['.zip'],
      'application/x-zip-compressed': ['.zip']
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
    setZipResults(null);
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

        {uploading ? (
          <Box sx={{ py: 4 }}>
            <CircularProgress size={60} sx={{ mb: 3, color: '#1e4d5a' }} />
            <Typography variant="h6" sx={{ color: '#424242', fontWeight: 500, mb: 1 }}>
              Processing ZIP file...
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Validating SF-424, PPOP, and attachments...
            </Typography>
          </Box>
        ) : (
          <Box>
            <Typography variant="h6" sx={{ color: '#1e4d5a', fontWeight: 600, mb: 2 }}>
              Upload Zip file containing forms & attachments
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
              ZIP files must contain either an SF-424 form, PPOP form or both, and supporting documents
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
                Drag and drop your ZIP file here
              </Typography>
              <Typography variant="body2" color="text.secondary">
                or click to browse
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
                ZIP files only (Max 200MB)
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
