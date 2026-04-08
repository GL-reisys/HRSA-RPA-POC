import { Inter } from 'next/font/google';
import './styles/globals.css';
import { AppBar, Toolbar, Typography, Container, Box } from '@mui/material';
import ThemeRegistry from './ThemeRegistry';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: 'Application Validation Assistant (AVA)',
  description: 'AI-powered SF-424 form validation assistant',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ThemeRegistry>
          <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
            <AppBar position="static" sx={{ backgroundColor: '#003366' }}>
              <Toolbar>
                <Typography variant="h5" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
                  Application Validation Assistant (AVA)
                </Typography>
              </Toolbar>
            </AppBar>
            <Container component="main" sx={{ mt: 4, mb: 4, flex: 1 }} maxWidth="xl">
              {children}
            </Container>
          </Box>
        </ThemeRegistry>
      </body>
    </html>
  );
}
