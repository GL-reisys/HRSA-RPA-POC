import { AppBar, Toolbar, Typography, Button } from '@mui/material';
import Link from 'next/link';

export default function Header() {
  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          RPA POC AVA
        </Typography>
        <Link href="/" passHref style={{ textDecoration: 'none', color: 'inherit' }}>
          <Button color="inherit">Home</Button>
        </Link>
        <Link href="/dashboard" passHref style={{ textDecoration: 'none', color: 'inherit' }}>
          <Button color="inherit">Dashboard</Button>
        </Link>
      </Toolbar>
    </AppBar>
  );
}
