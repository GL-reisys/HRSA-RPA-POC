'use client';

import { useState } from 'react';
import { Box, Button, Typography, LinearProgress, Alert, Chip } from '@mui/material';
import FolderZipIcon from '@mui/icons-material/FolderZip';
import DescriptionIcon from '@mui/icons-material/Description';
import axios from 'axios';

export default function ZipUpload({ onUploadSuccess }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState(null);
  const [results, setResults] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.name.toLowerCase().endsWith('.zip')) {
      setSelectedFile(file);
      setMessage(null);
      setResults(null);
    } else {
      setMessage({ type: 'error', text: 'Please select a valid ZIP file' });
      setSelectedFile(null);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        setSelectedFile(file);
        setMessage(null);
        setResults(null);
      } else {
        setMessage({ type: 'error', text: 'Please select a valid ZIP file' });
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setMessage({ type: 'error', text: 'Please select a file first' });
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      setUploading(true);
      setMessage(null);
      setResults(null);

      // Backend will auto-extract announcement number from SF-424 in zip
      const response = await axios.post('/api/zip/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const data = response.data;
      
      setResults(data);
      setMessage({ 
        type: 'success', 
        text: `Successfully processed ${data.files_processed} files (${data.total_pages} pages)` 
      });
      setSelectedFile(null);
      
      if (onUploadSuccess) {
        onUploadSuccess(data);
      }
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Failed to upload file';
      setMessage({ type: 'error', text: errorMsg });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Box>
      <Box
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        sx={{
          border: '2px dashed',
          borderColor: dragActive ? 'primary.main' : 'grey.400',
          borderRadius: 2,
          p: 4,
          textAlign: 'center',
          backgroundColor: dragActive ? 'action.hover' : 'background.paper',
          cursor: 'pointer',
          transition: 'all 0.3s',
          mb: 2,
        }}
      >
        <input
          type="file"
          accept=".zip"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          id="zip-upload"
        />
        <label htmlFor="zip-upload">
          <FolderZipIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Drag and drop ZIP file here
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            ZIP file should contain application attachments
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            Announcement number will be extracted from SF-424 form
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            or
          </Typography>
          <Button variant="outlined" component="span" sx={{ mt: 1 }}>
            Browse Files
          </Button>
        </label>
      </Box>

      {selectedFile && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2">
            Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
          </Typography>
        </Box>
      )}

      {uploading && <LinearProgress sx={{ mb: 2 }} />}

      {message && (
        <Alert severity={message.type} sx={{ mb: 2 }}>
          {message.text}
        </Alert>
      )}

      {results && (
        <Box sx={{ mb: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: 1, borderColor: 'divider' }}>
          <Typography variant="h6" gutterBottom>
            Processing Results
          </Typography>
          
          {results.announcement_number && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Announcement Number (from SF-424):
              </Typography>
              <Chip label={results.announcement_number} color="primary" sx={{ mt: 1 }} />
            </Box>
          )}
          
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">
                Files Processed:
              </Typography>
              <Typography variant="h5">
                {results.files_processed}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                Total Pages:
              </Typography>
              <Typography variant="h5">
                {results.total_pages}
              </Typography>
            </Box>
          </Box>

          {results.converted_files && results.converted_files.length > 0 && (
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Files:
              </Typography>
              {results.converted_files.map((file, idx) => (
                <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <DescriptionIcon fontSize="small" color="action" />
                  <Typography variant="body2">
                    {file.original_name} 
                    {file.page_count > 0 && ` (${file.page_count} pages)`}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}

          {results.errors && results.errors.length > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              <Typography variant="body2">
                {results.errors.length} file(s) had issues during processing
              </Typography>
            </Alert>
          )}

          {results.output_zip && (
            <Button 
              variant="contained" 
              href={results.output_zip}
              download
              fullWidth
              sx={{ mt: 2 }}
            >
              Download Processed ZIP
            </Button>
          )}
        </Box>
      )}

      <Button
        variant="contained"
        onClick={handleUpload}
        disabled={!selectedFile || uploading}
        fullWidth
      >
        {uploading ? 'Processing...' : 'Upload and Process Attachments'}
      </Button>
    </Box>
  );
}
