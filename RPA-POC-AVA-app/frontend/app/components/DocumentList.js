'use client';

import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  CircularProgress,
  Typography,
  Box,
  Tooltip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';

export default function DocumentList({ documents, loading, onDelete }) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!documents || documents.length === 0) {
    return (
      <Typography variant="body1" color="text.secondary" sx={{ textAlign: 'center', p: 4 }}>
        No documents uploaded yet. Upload your first PDF to get started.
      </Typography>
    );
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getStatusChip = (status) => {
    if (status === 'validated') {
      return (
        <Chip
          icon={<CheckCircleIcon />}
          label="Validated"
          color="success"
          size="small"
        />
      );
    } else {
      return (
        <Chip
          icon={<ErrorIcon />}
          label="Invalid"
          color="error"
          size="small"
        />
      );
    }
  };

  return (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Filename</TableCell>
            <TableCell>Upload Date</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Pages</TableCell>
            <TableCell>Size (KB)</TableCell>
            <TableCell align="center">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {documents.map((doc) => (
            <TableRow key={doc.id} hover>
              <TableCell>{doc.filename}</TableCell>
              <TableCell>{formatDate(doc.upload_date)}</TableCell>
              <TableCell>{getStatusChip(doc.status)}</TableCell>
              <TableCell>
                {doc.validation_results?.page_count || 'N/A'}
              </TableCell>
              <TableCell>
                {doc.validation_results?.file_size
                  ? (doc.validation_results.file_size / 1024).toFixed(2)
                  : 'N/A'}
              </TableCell>
              <TableCell align="center">
                <Tooltip title="Delete document">
                  <IconButton
                    color="error"
                    onClick={() => onDelete(doc.id)}
                    size="small"
                  >
                    <DeleteIcon />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
