import { Box, Typography, Button, Paper } from '@mui/material';
import Link from 'next/link';
import DescriptionIcon from '@mui/icons-material/Description';

export default function Home() {
  return (
    <Box sx={{ textAlign: 'center', mt: 8 }}>
      <Paper elevation={3} sx={{ p: 6, maxWidth: 600, mx: 'auto' }}>
        <DescriptionIcon sx={{ fontSize: 80, color: 'primary.main', mb: 2 }} />
        <Typography variant="h3" component="h1" gutterBottom>
          Welcome to RPA POC AVA
        </Typography>
        <Typography variant="h6" color="text.secondary" paragraph>
          Document Validation Application
        </Typography>
        <Typography variant="body1" paragraph sx={{ mt: 3 }}>
          Upload and validate PDF documents with automated processing and validation.
        </Typography>
        <Link href="/dashboard" passHref style={{ textDecoration: 'none' }}>
          <Button variant="contained" size="large" sx={{ mt: 2 }}>
            Go to Dashboard
          </Button>
        </Link>
      </Paper>
    </Box>
  );
}
