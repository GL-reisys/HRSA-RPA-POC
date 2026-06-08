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
      setError('Invalid Application filename extension - Please use a ZIP file with a Funding Opportunity Number');
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
      
      // Calculate status for each section - only count page count if there are actual attachment files (not just forms)
      const hasPageCount = zipResult.attachments && zipResult.attachments.files && zipResult.attachments.files.length > 0;
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
      
      // If NOFO mismatch or deadline passed, page count should fail
      const hasNofoMismatch = zipResult.sf424_validation?.nofo_mismatch;
      const hasDeadlineError = zipResult.sf424_validation?.validation_results?.errors?.some(err => 
        err.user_message && err.user_message.includes('deadline has passed')
      );
      const shouldSkipPageCount = hasNofoMismatch || hasDeadlineError;
      const adjustedPageCountPassed = shouldSkipPageCount ? false : pageCountPassed;
      
      // 1. SUMMARY SECTION (new design matching Designer.png)
      const passedCount = [sf424Passed, ppopPassed, adjustedPageCountPassed].filter(Boolean).length;
      const failedCount = [hasSF424 && !sf424Passed, hasPPOP && !ppopPassed, hasPageCount && !adjustedPageCountPassed].filter(Boolean).length;
      
      // Left-aligned validation summary with exact spacing
      aiMessage += '<div style="font-size: 18px; font-weight: 700; color: #003d6b;">📋 Validation Summary</div>\n';
      aiMessage += `✅ ${passedCount} Passed   ❌ ${failedCount} Failed\n\n`;
      aiMessage += '--------------------------------\n';
      
      if (hasSF424) {
        const badge = sf424Passed ? '✅ PASSED' : '❌ FAILED';
        aiMessage += `SF-424      ${badge}\n`;
      }
      
      if (hasPPOP) {
        const badge = ppopPassed ? '✅ PASSED' : '❌ FAILED';
        aiMessage += `Performance Site      ${badge}\n`;
      }
      
      if (hasPageCount) {
        const badge = adjustedPageCountPassed ? '✅ PASSED' : '❌ FAILED';
        aiMessage += `Application Page Limit      ${badge}\n`;
      }
      
      if (!hasPageCount && !hasPPOP && !hasSF424) {
        aiMessage += '⚠️ No forms found for validation\n';
      }
      
      aiMessage += '--------------------------------\n\n';
      
      // 2. SF-424 SECTION
      if (hasSF424) {
        aiMessage += '<div style="font-size: 16px; font-weight: 700; margin: 8px 0; color: #003d6b; display: flex; align-items: center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#003d6b" stroke-width="2" style="margin-right: 8px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>SF-424 Validation</div>\n';
        
        const sf424 = zipResult.sf424_validation;
        
        // Check for NOFO mismatch first
        if (sf424.nofo_mismatch) {
          const expected = sf424.nofo_error.expected || '';
          const actual = sf424.nofo_error.actual || '';
          aiMessage += `❌ <strong>Funding Opportunity Number mismatch:</strong> Application zip filename has <strong>${expected}</strong> but SF-424 has <strong>${actual}</strong>\n`;
          aiMessage += 'Please ensure the funding opportunity number in your SF-424 matches the Application zip filename.\n\n';
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
                aiMessage += `<span style="color: #991b1b; font-weight: 700;">${index + 1}. ${err.user_message}</span>\n`;
                
                if (err.field_location) {
                  aiMessage += `   • ${err.field_location}\n`;
                }
                
                // Only show image if it exists and is not empty
                if (err.image_path && err.image_path.trim() !== '') {
                  aiMessage += `   <img src="${err.image_path}" alt="${err.field_name} field" style="max-width: 100%; margin: 8px 0; border: 1px solid #e5e7eb; border-radius: 4px;" />\n`;
                }
                
                if (err.current_value) {
                  aiMessage += `   • Current Value: ${err.current_value}\n`;
                }
                
                aiMessage += '\n';
                
                // Only show guidance if it exists and is not empty
                if (err.guidance && err.guidance.trim() !== '') {
                  aiMessage += '   <span style="color: #004d99; font-weight: 600;">How to Fix:</span>\n';
                  const guidanceText = err.guidance.replace(/<br>/g, '\n   ');
                  const cleanGuidance = guidanceText.replace(/<[^>]+>/g, '');
                  cleanGuidance.split('\n').forEach(line => {
                    if (line.trim()) {
                      aiMessage += `   ${line.trim()}\n`;
                    }
                  });
                  aiMessage += '\n';
                }
                aiMessage += '\n';
              });
            }
          }
        }
      }
      
      // 3. PPOP SECTION
      if (hasPPOP) {
        aiMessage += '<div style="font-size: 16px; font-weight: 700; margin: 8px 0; color: #003d6b; display: flex; align-items: center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#003d6b" stroke-width="2" style="margin-right: 8px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>Performance Site</div>\n';
        if (ppopPassed) {
          aiMessage += '✅ Address provided in the Performance Site form passed all validations\n\n';
        } else if (zipResult.ppop_validation.validation_results?.errors) {
          const ppopErrors = zipResult.ppop_validation.validation_results.errors;
          ppopErrors.forEach((err, index) => {
            aiMessage += `❌ ${err.user_message}\n`;
          });
          aiMessage += '\n';
        }
      }
      
      // 4. PAGE COUNT SECTION - Show NOFO error if mismatch exists
      if (hasPageCount) {
        aiMessage += '<div style="font-size: 16px; font-weight: 700; margin: 8px 0; color: #003d6b; display: flex; align-items: center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#003d6b" stroke-width="2" style="margin-right: 8px;"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>Application Page Limit Validation</div>\n';
        
        // Show NOFO mismatch error if it exists
        if (hasNofoMismatch) {
          const sf424 = zipResult.sf424_validation;
          const expected = sf424.nofo_error?.expected || '';
          const actual = sf424.nofo_error?.actual || '';
          aiMessage += `❌ <strong>Funding Opportunity Number mismatch:</strong> Application zip filename has <strong>${expected}</strong> but SF-424 has <strong>${actual}</strong>\n`;
          aiMessage += 'Please ensure the funding opportunity number in your SF-424 matches the Application zip filename.\n\n';
        } else {
          // Only show page count details if no NOFO mismatch
          const att = zipResult.attachments;
          const countedFiles = att.files || [];
          const excludedFiles = att.excluded_files || [];
          
          // Check if page limit is exceeded
          if (att.max_attachment_page_count && !att.page_count_ok) {
            // Show error message for page limit exceeded
            aiMessage += '**Upload failed ❌**\n\n';
            aiMessage += `**Total attached pages: ${att.total_pages}**\n`;
            aiMessage += `**Maximum allowed: ${att.max_attachment_page_count}**\n\n`;
            aiMessage += 'The document exceeds the allowed page limit.\n';
            aiMessage += 'Please reduce the number of pages and try again.\n\n';
          } else {
            // Show total pages with icon and status
            if (adjustedPageCountPassed) {
              aiMessage += '**Upload passed ✅**\n\n';
            } else if (hasPageCount) {
              aiMessage += '**Upload failed ❌**\n\n';
            }
            
            if (att.max_attachment_page_count) {
              aiMessage += `**Total attachment pages: ${att.total_pages}**\n`;
              aiMessage += `**Maximum allowed: ${att.max_attachment_page_count}**\n\n`;
            } else {
              aiMessage += `**Total attachment pages: ${att.total_pages}**\n\n`;
            }
          }
          
          // Show counted files
          if (countedFiles.length > 0) {
            aiMessage += '**Attachments/documents that count toward the page limit:**\n';
            countedFiles.forEach(f => {
              const pageText = f.pages === 1 ? 'page' : 'pages';
              aiMessage += `• ${f.name} (${f.pages} ${pageText})\n`;
            });
            aiMessage += '\n';
          }
          
          // Show excluded files
          if (excludedFiles.length > 0) {
            aiMessage += '**Attachments/documents that do not count toward the page limit:**\n';
            excludedFiles.forEach(f => {
              aiMessage += `   • ${f.name} - ${f.exclusion_reason}\n`;
            });
            aiMessage += '\n';
          }
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
    maxFiles: 1,
    multiple: false,
    noClick: false,
    noKeyboard: false
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
      
      // Calculate status for each section - only count page count if there are actual attachment files (not just forms)
      const hasPageCount = zipResult.attachments && zipResult.attachments.files && zipResult.attachments.files.length > 0;
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
      
      // If NOFO mismatch or deadline passed, page count should fail
      const hasNofoMismatch = zipResult.sf424_validation?.nofo_mismatch;
      const hasDeadlineError = zipResult.sf424_validation?.validation_results?.errors?.some(err => 
        err.user_message && err.user_message.includes('deadline has passed')
      );
      const shouldSkipPageCount = hasNofoMismatch || hasDeadlineError;
      const adjustedPageCountPassed = shouldSkipPageCount ? false : pageCountPassed;
      
      // 1. SUMMARY SECTION (new design matching Designer.png)
      const passedCount = [sf424Passed, ppopPassed, adjustedPageCountPassed].filter(Boolean).length;
      const failedCount = [hasSF424 && !sf424Passed, hasPPOP && !ppopPassed, hasPageCount && !adjustedPageCountPassed].filter(Boolean).length;
      
      // Left-aligned validation summary with exact spacing
      aiMessage += '<div style="font-size: 18px; font-weight: 700; color: #003d6b;">📋 Validation Summary</div>\n';
      aiMessage += `✅ ${passedCount} Passed   ❌ ${failedCount} Failed\n\n`;
      aiMessage += '--------------------------------\n';
      
      if (hasSF424) {
        const badge = sf424Passed ? '✅ PASSED' : '❌ FAILED';
        aiMessage += `SF-424      ${badge}\n`;
      }
      
      if (hasPPOP) {
        const badge = ppopPassed ? '✅ PASSED' : '❌ FAILED';
        aiMessage += `Performance Site      ${badge}\n`;
      }
      
      if (hasPageCount) {
        const badge = adjustedPageCountPassed ? '✅ PASSED' : '❌ FAILED';
        aiMessage += `Application Page Limit      ${badge}\n`;
      }
      
      if (!hasPageCount && !hasPPOP && !hasSF424) {
        aiMessage += '⚠️ No forms found for validation\n';
      }
      
      aiMessage += '--------------------------------\n\n';
      
      // 2. SF-424 SECTION
      if (hasSF424) {
        aiMessage += '<div style="font-size: 16px; font-weight: 700; margin: 8px 0; color: #003d6b; display: flex; align-items: center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#003d6b" stroke-width="2" style="margin-right: 8px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>SF-424 Validation</div>\n';
        
        const sf424 = zipResult.sf424_validation;
        
        // Check for NOFO mismatch first
        if (sf424.nofo_mismatch) {
          const expected = sf424.nofo_error.expected || '';
          const actual = sf424.nofo_error.actual || '';
          aiMessage += `❌ <strong>Funding Opportunity Number mismatch:</strong> Application zip filename has <strong>${expected}</strong> but SF-424 has <strong>${actual}</strong>\n`;
          aiMessage += 'Please ensure the funding opportunity number in your SF-424 matches the Application zip filename.\n\n';
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
                aiMessage += `<span style="color: #991b1b; font-weight: 700;">${index + 1}. ${err.user_message}</span>\n`;
                
                if (err.field_location) {
                  aiMessage += `   • ${err.field_location}\n`;
                }
                
                // Only show image if it exists and is not empty
                if (err.image_path && err.image_path.trim() !== '') {
                  aiMessage += `   <img src="${err.image_path}" alt="${err.field_name} field" style="max-width: 100%; margin: 8px 0; border: 1px solid #e5e7eb; border-radius: 4px;" />\n`;
                }
                
                if (err.current_value) {
                  aiMessage += `   • Current Value: ${err.current_value}\n`;
                }
                
                aiMessage += '\n';
                
                // Only show guidance if it exists and is not empty
                if (err.guidance && err.guidance.trim() !== '') {
                  aiMessage += '   <span style="color: #004d99; font-weight: 600;">How to Fix:</span>\n';
                  const guidanceText = err.guidance.replace(/<br>/g, '\n   ');
                  const cleanGuidance = guidanceText.replace(/<[^>]+>/g, '');
                  cleanGuidance.split('\n').forEach(line => {
                    if (line.trim()) {
                      aiMessage += `   ${line.trim()}\n`;
                    }
                  });
                  aiMessage += '\n';
                }
                aiMessage += '\n';
              });
            }
          }
        }
      }
      
      // 3. PPOP SECTION
      if (hasPPOP) {
        aiMessage += '<div style="font-size: 16px; font-weight: 700; margin: 8px 0; color: #003d6b; display: flex; align-items: center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#003d6b" stroke-width="2" style="margin-right: 8px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>Performance Site</div>\n';
        if (ppopPassed) {
          aiMessage += '✅ Address provided in the Performance Site form passed all validations\n\n';
        } else if (zipResult.ppop_validation.validation_results?.errors) {
          const ppopErrors = zipResult.ppop_validation.validation_results.errors;
          ppopErrors.forEach((err, index) => {
            aiMessage += `❌ ${err.user_message}\n`;
          });
          aiMessage += '\n';
        }
      }
      
      // 4. PAGE COUNT SECTION - Show NOFO error if mismatch exists
      if (hasPageCount) {
        aiMessage += '<div style="font-size: 16px; font-weight: 700; margin: 8px 0; color: #003d6b; display: flex; align-items: center;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#003d6b" stroke-width="2" style="margin-right: 8px;"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>Application Page Limit Validation</div>\n';
        
        // Show NOFO mismatch error if it exists
        if (hasNofoMismatch) {
          const sf424 = zipResult.sf424_validation;
          const expected = sf424.nofo_error?.expected || '';
          const actual = sf424.nofo_error?.actual || '';
          aiMessage += `❌ <strong>Funding Opportunity Number mismatch:</strong> Application zip filename has <strong>${expected}</strong> but SF-424 has <strong>${actual}</strong>\n`;
          aiMessage += 'Please ensure the funding opportunity number in your SF-424 matches the Application zip filename.\n\n';
        } else {
          // Only show page count details if no NOFO mismatch
          const att = zipResult.attachments;
          const countedFiles = att.files || [];
          const excludedFiles = att.excluded_files || [];
          
          // Check if page limit is exceeded
          if (att.max_attachment_page_count && !att.page_count_ok) {
            // Show error message for page limit exceeded
            aiMessage += '**Upload failed ❌**\n\n';
            aiMessage += `**Total attached pages: ${att.total_pages}**\n`;
            aiMessage += `**Maximum allowed: ${att.max_attachment_page_count}**\n\n`;
            aiMessage += 'The document exceeds the allowed page limit.\n';
            aiMessage += 'Please reduce the number of pages and try again.\n\n';
          } else {
            // Show total pages with icon and status
            if (adjustedPageCountPassed) {
              aiMessage += '**Upload passed ✅**\n\n';
            } else if (hasPageCount) {
              aiMessage += '**Upload failed ❌**\n\n';
            }
            
            if (att.max_attachment_page_count) {
              aiMessage += `**Total attachment pages: ${att.total_pages}**\n`;
              aiMessage += `**Maximum allowed: ${att.max_attachment_page_count}**\n\n`;
            } else {
              aiMessage += `**Total attachment pages: ${att.total_pages}**\n\n`;
            }
          }
          
          // Show counted files
          if (countedFiles.length > 0) {
            aiMessage += '**Attachments/documents that count toward the page limit:**\n';
            countedFiles.forEach(f => {
              const pageText = f.pages === 1 ? 'page' : 'pages';
              aiMessage += `• ${f.name} (${f.pages} ${pageText})\n`;
            });
            aiMessage += '\n';
          }
          
          // Show excluded files
          if (excludedFiles.length > 0) {
            aiMessage += '**Attachments/documents that do not count toward the page limit:**\n';
            excludedFiles.forEach(f => {
              aiMessage += `   • ${f.name} - ${f.exclusion_reason}\n`;
            });
            aiMessage += '\n';
          }
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
        {uploading ? (
          <Box sx={{ py: 4 }}>
            <CircularProgress size={60} sx={{ mb: 3, color: '#1e4d5a' }} />
            <Typography variant="h6" sx={{ color: '#424242', fontWeight: 500, mb: 1 }}>
              Processing ZIP file...
            </Typography>
            <Typography variant="body2" sx={{ color: '#424242' }}>
              Validating SF-424, PPOP, and attachments...
            </Typography>
          </Box>
        ) : (
          <Box>
            <Typography variant="h6" sx={{ color: '#1e4d5a', fontWeight: 600, mb: 2 }}>
              Upload ZIP File Containing Forms & Attachments
            </Typography>
            <Typography variant="body1" sx={{ mb: 4, color: '#424242' }}>
              Application Package provided
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
              <input {...getInputProps()} aria-label="Upload ZIP file containing your application forms and attachments" title="Upload ZIP file containing your application forms and attachments" />
              <UploadFileIcon sx={{ fontSize: 60, color: '#1e4d5a', mb: 2 }} />
              <Typography variant="body1" sx={{ color: '#424242', mb: 1 }}>
                Drag and drop your ZIP file here
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                or click to browse
              </Typography>
              <Typography variant="caption" sx={{ mt: 2, display: 'block', color: '#424242' }}>
                ZIP files only (Max 200MB)
              </Typography>
            </Box>

            {error && (
              <Alert severity="error" role="alert" aria-live="assertive" sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            <Button
              variant="text"
              component="a"
              href="https://help.hrsa.gov/x/MoAfFg"
              target="_blank"
              rel="noopener noreferrer"
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
