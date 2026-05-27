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
import ZipUploadPage from './ZipUploadPage';

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
      
      // Calculate status for each section
      const hasPageCount = zipResult.attachments && zipResult.attachments.total_files > 0;
      const pageCountPassed = hasPageCount && zipResult.attachments.page_count_ok === true;
      
      const hasSF424 = zipResult.sf424_validation && zipResult.sf424_validation.extracted;
      // SF-424 passes if: no NOFO mismatch AND (validation passed OR only database errors exist)
      // Database errors like "funding_cycle_code should be string" are not form field errors
      const hasOnlyDatabaseErrors = zipResult.sf424_validation?.errors?.every(err => 
        err.includes('funding_cycle_code') || err.includes('validation error for FundingOpportunity')
      );
      const sf424Passed = hasSF424 && 
        !zipResult.sf424_validation.nofo_mismatch &&
        (zipResult.sf424_validation.validation_results?.valid === true || 
         (!zipResult.sf424_validation.validation_results && hasOnlyDatabaseErrors));
      
      const hasPPOP = zipResult.ppop_validation && zipResult.ppop_validation.extracted;
      const ppopPassed = hasPPOP && zipResult.ppop_validation.validation_results?.valid === true;
      
      // 1. SUMMARY SECTION (new design matching Designer.png)
      const passedCount = [sf424Passed, ppopPassed, pageCountPassed].filter(Boolean).length;
      const failedCount = [hasSF424 && !sf424Passed, hasPPOP && !ppopPassed, hasPageCount && !pageCountPassed].filter(Boolean).length;
      
      aiMessage += '<div style="background: white; border-radius: 12px; padding: 14px 18px; margin: 0 auto 20px auto; max-width: 380px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">\n';
      
      // Title with clipboard icon
      aiMessage += '<div style="display: flex; align-items: center; margin-bottom: 10px;">\n';
      aiMessage += '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1e293b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="15" y2="16"/></svg>\n';
      aiMessage += '<div style="font-size: 19px; font-weight: 700; color: #1e293b;">Validation Summary</div>\n';
      aiMessage += '</div>\n';
      
      // Passed/Failed counts
      aiMessage += '<div style="display: flex; justify-content: space-around; margin-bottom: 12px;">\n';
      aiMessage += `<div style="display: flex; align-items: center; font-size: 15px; font-weight: 700; color: #10b981;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 5px;"><polyline points="20 6 9 17 4 12"/></svg>${passedCount} Passed</div>\n`;
      aiMessage += `<div style="display: flex; align-items: center; font-size: 15px; font-weight: 700; color: #ef4444;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 5px;"><polyline points="6 18 18 6"/><polyline points="6 6 18 18"/></svg>${failedCount} Failed</div>\n`;
      aiMessage += '</div>\n';
      
      // Horizontal divider
      aiMessage += '<div style="border-top: 1px solid #e5e7eb; margin-bottom: 10px;"></div>\n';
      
      // Form list with badges
      if (hasSF424) {
        aiMessage += '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; border-bottom: 1px solid #f3f4f6;">\n';
        aiMessage += '<div style="font-size: 14px; font-weight: 600; color: #1e293b;">SF-424 Form</div>\n';
        if (sf424Passed) {
          aiMessage += '<div style="background: #10b981; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"/></svg>PASSED</div>\n';
        } else {
          aiMessage += '<div style="background: #ef4444; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>FAILED</div>\n';
        }
        aiMessage += '</div>\n';
      }
      
      if (hasPPOP) {
        aiMessage += '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; border-bottom: 1px solid #f3f4f6;">\n';
        aiMessage += '<div style="font-size: 14px; font-weight: 600; color: #1e293b;">PPOP Form</div>\n';
        if (ppopPassed) {
          aiMessage += '<div style="background: #10b981; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"/></svg>PASSED</div>\n';
        } else {
          aiMessage += '<div style="background: #ef4444; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>FAILED</div>\n';
        }
        aiMessage += '</div>\n';
      }
      
      if (hasPageCount) {
        aiMessage += '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0;">\n';
        aiMessage += '<div style="font-size: 14px; font-weight: 600; color: #1e293b;">Page Count</div>\n';
        if (pageCountPassed) {
          aiMessage += '<div style="background: #10b981; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"/></svg>PASSED</div>\n';
        } else {
          aiMessage += '<div style="background: #ef4444; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>FAILED</div>\n';
        }
        aiMessage += '</div>\n';
      }
      
      if (!hasPageCount && !hasPPOP && !hasSF424) {
        aiMessage += '<div style="text-align: center; padding: 20px; color: #64748b;">⚠️ No forms found for validation</div>\n';
      }
      
      aiMessage += '</div>\n\n';
      
      // 2. SF-424 SECTION
      if (hasSF424) {
        aiMessage += '<div style="font-size: 17px; font-weight: 700; margin-bottom: 4px;">📄 SF-424 Form Validation:</div>\n';
        
        const sf424 = zipResult.sf424_validation;
        
        // Check for NOFO mismatch first
        if (sf424.nofo_mismatch) {
          aiMessage += `❌ ${sf424.nofo_error.user_message}\n\n`;
          aiMessage += 'Please ensure the funding opportunity number in your SF-424 form matches the ZIP filename.\n\n';
        } else {
          // Normal SF-424 validation display
          const fields = sf424.fields || {};
          const hasErrors = sf424.validation_results && !sf424.validation_results.valid;
        
          if (sf424.extracted) {
            const errors = sf424.validation_results?.errors || [];
            const errorFieldNames = new Set(errors.map(e => e.field_name).filter(Boolean));
            
            if (hasErrors) {
              aiMessage += 'Here is a quick summary:\n\n';
              aiMessage += '**Need to fix the following error(s):**\n';
              errors.forEach(err => {
                const fieldName = err.field_name || err.user_message.split(' is ')[0] || 'Unknown Field';
                aiMessage += `   ❌ ${fieldName}\n`;
              });
              aiMessage += '\n';
            }
            
            // Show validated fields
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
            
            // Detailed error explanations
            if (hasErrors && errors.length > 0) {
              errors.forEach((err, index) => {
                aiMessage += `<span style="color: #dc2626; font-weight: 700;">${index + 1}. ${err.user_message}</span>\n`;
                
                if (err.field_location) {
                  aiMessage += `   • ${err.field_location}\n`;
                }
                
                if (err.image_path) {
                  aiMessage += `   <img src="${err.image_path}" alt="${err.field_name} field" style="max-width: 100%; margin: 8px 0; border: 1px solid #e5e7eb; border-radius: 4px;" />\n`;
                }
                
                if (err.current_value) {
                  aiMessage += `   • Current Value: ${err.current_value}\n`;
                }
                
                aiMessage += '\n';
                
                if (err.guidance) {
                  aiMessage += '   <span style="color: #0066cc; font-weight: 600;">How to Fix:</span>\n';
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
          }
        }
      }
      
      // 3. PPOP SECTION
      if (hasPPOP) {
        aiMessage += '<div style="font-size: 17px; font-weight: 700; margin-bottom: 4px;">📍 PPOP Form Validation:</div>\n';
        if (ppopPassed) {
          aiMessage += '✅ All PPOP validations passed\n\n';
        } else if (zipResult.ppop_validation.validation_results?.errors) {
          const ppopErrors = zipResult.ppop_validation.validation_results.errors;
          ppopErrors.forEach((err, index) => {
            aiMessage += `❌ ${err.user_message}\n`;
          });
          aiMessage += '\n';
        }
      }
      
      // 4. PAGE COUNT SECTION
      if (hasPageCount) {
        aiMessage += '<div style="font-size: 17px; font-weight: 700; margin-bottom: 4px;">📎 Page Count Validation:</div>\n';
        const att = zipResult.attachments;
        const countedFiles = att.files || [];
        const excludedFiles = att.excluded_files || [];
        
        // Show counted files
        if (countedFiles.length > 0) {
          aiMessage += '**Files counted towards page limit:**\n';
          countedFiles.forEach(f => {
            const pageText = f.pages === 1 ? 'page' : 'pages';
            aiMessage += `   • ${f.name} (${f.pages} ${pageText})\n`;
          });
          
          const totalPageText = att.total_pages === 1 ? 'page' : 'pages';
          aiMessage += `\n**Total: ${att.total_pages} ${totalPageText}**`;
          if (att.max_attachment_page_count) {
            aiMessage += ` (Maximum Page Limit: ${att.max_attachment_page_count})`;
          }
          if (pageCountPassed) {
            aiMessage += ' ✅\n';
          } else if (att.page_count_ok === false) {
            aiMessage += ' ❌ EXCEEDED\n';
          } else {
            aiMessage += '\n';
          }
          aiMessage += '\n';
        }
        
        // Show excluded files
        if (excludedFiles.length > 0) {
          aiMessage += '**Files excluded from page count:**\n';
          excludedFiles.forEach(f => {
            aiMessage += `   • ${f.name} - ${f.exclusion_reason}\n`;
          });
          aiMessage += '\n';
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
  };

  // Show chat interface after upload completes
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

  // Show new upload page when no file uploaded
  if (!file && !uploading) {
    return <ZipUploadPage onUploadComplete={async (zipResult) => {
      // Process ZIP result same as onDrop
      setFile({ name: zipResult.file_name || 'Unknown.zip' });
      setFileId(zipResult.file_id);
      setFormType('ZIP');
      
      // Build AI response
      let aiMessage = '';
      
      // Calculate status for each section
      const hasPageCount = zipResult.attachments && zipResult.attachments.total_files > 0;
      const pageCountPassed = hasPageCount && zipResult.attachments.page_count_ok === true;
      
      const hasSF424 = zipResult.sf424_validation && zipResult.sf424_validation.extracted;
      // SF-424 passes if: no NOFO mismatch AND (validation passed OR only database errors exist)
      // Database errors like "funding_cycle_code should be string" are not form field errors
      const hasOnlyDatabaseErrors = zipResult.sf424_validation?.errors?.every(err => 
        err.includes('funding_cycle_code') || err.includes('validation error for FundingOpportunity')
      );
      const sf424Passed = hasSF424 && 
        !zipResult.sf424_validation.nofo_mismatch &&
        (zipResult.sf424_validation.validation_results?.valid === true || 
         (!zipResult.sf424_validation.validation_results && hasOnlyDatabaseErrors));
      
      const hasPPOP = zipResult.ppop_validation && zipResult.ppop_validation.extracted;
      const ppopPassed = hasPPOP && zipResult.ppop_validation.validation_results?.valid === true;
      
      // 1. SUMMARY SECTION (new design matching Designer.png)
      const passedCount = [sf424Passed, ppopPassed, pageCountPassed].filter(Boolean).length;
      const failedCount = [hasSF424 && !sf424Passed, hasPPOP && !ppopPassed, hasPageCount && !pageCountPassed].filter(Boolean).length;
      
      aiMessage += '<div style="background: white; border-radius: 12px; padding: 14px 18px; margin: 0 auto 20px auto; max-width: 380px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">\n';
      
      // Title with clipboard icon
      aiMessage += '<div style="display: flex; align-items: center; margin-bottom: 10px;">\n';
      aiMessage += '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1e293b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="15" y2="16"/></svg>\n';
      aiMessage += '<div style="font-size: 19px; font-weight: 700; color: #1e293b;">Validation Summary</div>\n';
      aiMessage += '</div>\n';
      
      // Passed/Failed counts
      aiMessage += '<div style="display: flex; justify-content: space-around; margin-bottom: 12px;">\n';
      aiMessage += `<div style="display: flex; align-items: center; font-size: 15px; font-weight: 700; color: #10b981;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 5px;"><polyline points="20 6 9 17 4 12"/></svg>${passedCount} Passed</div>\n`;
      aiMessage += `<div style="display: flex; align-items: center; font-size: 15px; font-weight: 700; color: #ef4444;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 5px;"><polyline points="6 18 18 6"/><polyline points="6 6 18 18"/></svg>${failedCount} Failed</div>\n`;
      aiMessage += '</div>\n';
      
      // Horizontal divider
      aiMessage += '<div style="border-top: 1px solid #e5e7eb; margin-bottom: 10px;"></div>\n';
      
      // Form list with badges
      if (hasSF424) {
        aiMessage += '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; border-bottom: 1px solid #f3f4f6;">\n';
        aiMessage += '<div style="font-size: 14px; font-weight: 600; color: #1e293b;">SF-424 Form</div>\n';
        if (sf424Passed) {
          aiMessage += '<div style="background: #10b981; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"/></svg>PASSED</div>\n';
        } else {
          aiMessage += '<div style="background: #ef4444; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>FAILED</div>\n';
        }
        aiMessage += '</div>\n';
      }
      
      if (hasPPOP) {
        aiMessage += '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; border-bottom: 1px solid #f3f4f6;">\n';
        aiMessage += '<div style="font-size: 14px; font-weight: 600; color: #1e293b;">PPOP Form</div>\n';
        if (ppopPassed) {
          aiMessage += '<div style="background: #10b981; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"/></svg>PASSED</div>\n';
        } else {
          aiMessage += '<div style="background: #ef4444; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>FAILED</div>\n';
        }
        aiMessage += '</div>\n';
      }
      
      if (hasPageCount) {
        aiMessage += '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0;">\n';
        aiMessage += '<div style="font-size: 14px; font-weight: 600; color: #1e293b;">Page Count</div>\n';
        if (pageCountPassed) {
          aiMessage += '<div style="background: #10b981; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"/></svg>PASSED</div>\n';
        } else {
          aiMessage += '<div style="background: #ef4444; color: white; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 11px; display: flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>FAILED</div>\n';
        }
        aiMessage += '</div>\n';
      }
      
      if (!hasPageCount && !hasPPOP && !hasSF424) {
        aiMessage += '<div style="text-align: center; padding: 20px; color: #64748b;">⚠️ No forms found for validation</div>\n';
      }
      
      aiMessage += '</div>\n\n';
      
      // 2. SF-424 SECTION
      if (hasSF424) {
        aiMessage += '<div style="font-size: 17px; font-weight: 700; margin-bottom: 4px;">📄 SF-424 Form Validation:</div>\n';
        
        const sf424 = zipResult.sf424_validation;
        
        // Check for NOFO mismatch first
        if (sf424.nofo_mismatch) {
          aiMessage += `❌ ${sf424.nofo_error.user_message}\n\n`;
          aiMessage += 'Please ensure the funding opportunity number in your SF-424 form matches the ZIP filename.\n\n';
        } else {
          // Normal SF-424 validation display
          const fields = sf424.fields || {};
          const hasErrors = sf424.validation_results && !sf424.validation_results.valid;
        
          if (sf424.extracted) {
            const errors = sf424.validation_results?.errors || [];
            const errorFieldNames = new Set(errors.map(e => e.field_name).filter(Boolean));
            
            if (hasErrors) {
              aiMessage += 'Here is a quick summary:\n\n';
              aiMessage += '**Need to fix the following error(s):**\n';
              errors.forEach(err => {
                const fieldName = err.field_name || err.user_message.split(' is ')[0] || 'Unknown Field';
                aiMessage += `   ❌ ${fieldName}\n`;
              });
              aiMessage += '\n';
            }
            
            // Show validated fields
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
            
            // Detailed error explanations
            if (hasErrors && errors.length > 0) {
              errors.forEach((err, index) => {
                aiMessage += `<span style="color: #dc2626; font-weight: 700;">${index + 1}. ${err.user_message}</span>\n`;
                
                if (err.field_location) {
                  aiMessage += `   • ${err.field_location}\n`;
                }
                
                if (err.image_path) {
                  aiMessage += `   <img src="${err.image_path}" alt="${err.field_name} field" style="max-width: 100%; margin: 8px 0; border: 1px solid #e5e7eb; border-radius: 4px;" />\n`;
                }
                
                if (err.current_value) {
                  aiMessage += `   • Current Value: ${err.current_value}\n`;
                }
                
                aiMessage += '\n';
                
                if (err.guidance) {
                  aiMessage += '   <span style="color: #0066cc; font-weight: 600;">How to Fix:</span>\n';
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
          }
        }
      }
      
      // 3. PPOP SECTION
      if (hasPPOP) {
        aiMessage += '<div style="font-size: 17px; font-weight: 700; margin-bottom: 4px;">📍 PPOP Form Validation:</div>\n';
        if (ppopPassed) {
          aiMessage += '✅ All PPOP validations passed\n\n';
        } else if (zipResult.ppop_validation.validation_results?.errors) {
          const ppopErrors = zipResult.ppop_validation.validation_results.errors;
          ppopErrors.forEach((err, index) => {
            aiMessage += `❌ ${err.user_message}\n`;
          });
          aiMessage += '\n';
        }
      }
      
      // 4. PAGE COUNT SECTION
      if (hasPageCount) {
        aiMessage += '<div style="font-size: 17px; font-weight: 700; margin-bottom: 4px;">📎 Page Count Validation:</div>\n';
        const att = zipResult.attachments;
        const countedFiles = att.files || [];
        const excludedFiles = att.excluded_files || [];
        
        // Show counted files
        if (countedFiles.length > 0) {
          aiMessage += '**Files counted towards page limit:**\n';
          countedFiles.forEach(f => {
            const pageText = f.pages === 1 ? 'page' : 'pages';
            aiMessage += `   • ${f.name} (${f.pages} ${pageText})\n`;
          });
          
          const totalPageText = att.total_pages === 1 ? 'page' : 'pages';
          aiMessage += `\n**Total: ${att.total_pages} ${totalPageText}**`;
          if (att.max_attachment_page_count) {
            aiMessage += ` (Maximum Page Limit: ${att.max_attachment_page_count})`;
          }
          if (pageCountPassed) {
            aiMessage += ' ✅\n';
          } else if (att.page_count_ok === false) {
            aiMessage += ' ❌ EXCEEDED\n';
          } else {
            aiMessage += '\n';
          }
          aiMessage += '\n';
        }
        
        // Show excluded files
        if (excludedFiles.length > 0) {
          aiMessage += '**Files excluded from page count:**\n';
          excludedFiles.forEach(f => {
            aiMessage += `   • ${f.name} - ${f.exclusion_reason}\n`;
          });
          aiMessage += '\n';
        }
      }
      
      setFormData(zipResult);
      setAiResponse(aiMessage);
      setValidationErrors([]);
      setChatHistory([
        {
          role: 'user',
          content: `Uploaded ZIP file`,
          timestamp: new Date().toISOString()
        },
        {
          role: 'assistant',
          content: aiMessage,
          timestamp: new Date().toISOString()
        }
      ]);
    }} />;
  }

  // Fallback to old upload UI (shouldn't reach here normally)
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
