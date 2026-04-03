'use client';

import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Paper, Alert } from '@mui/material';
import DocumentUpload from '../components/DocumentUpload';
import DocumentList from '../components/DocumentList';
import axios from 'axios';

export default function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [config, setConfig] = useState({ apiUrl: 'http://localhost:5000' });

  useEffect(() => {
    fetch('/config.json')
      .then(res => res.json())
      .then(data => setConfig(data))
      .catch(err => console.error('Error loading config:', err));
  }, []);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${config.apiUrl}/api/documents`);
      setDocuments(response.data.documents || []);
      setError(null);
    } catch (err) {
      setError('Failed to fetch documents. Please ensure the backend is running.');
      console.error('Error fetching documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [config.apiUrl]);

  const handleUploadSuccess = () => {
    fetchDocuments();
  };

  const handleDelete = async (docId) => {
    try {
      await axios.delete(`${config.apiUrl}/api/documents/${docId}`);
      fetchDocuments();
    } catch (err) {
      console.error('Error deleting document:', err);
      setError('Failed to delete document');
    }
  };

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Document Dashboard
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper elevation={3} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Upload Document
            </Typography>
            <DocumentUpload 
              apiUrl={config.apiUrl} 
              onUploadSuccess={handleUploadSuccess}
            />
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper elevation={3} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Document List
            </Typography>
            <DocumentList 
              documents={documents} 
              loading={loading}
              onDelete={handleDelete}
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
