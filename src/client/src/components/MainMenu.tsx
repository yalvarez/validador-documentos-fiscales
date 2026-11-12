import { AppBar, Button, Toolbar, Typography } from '@mui/material';
import { Link as RouterLink, useLocation } from 'react-router-dom';

const menu = [
  { label: 'Comprobantes', path: '/' },
  { label: 'Registrar', path: '/registrar' },
  { label: 'Parámetros', path: '/parametros' },
];

export default function MainMenu() {
  const { pathname } = useLocation();
  const activo = (p: string) => (p === '/' ? pathname === '/' || pathname.startsWith('/comprobantes') : pathname === p);
  return (
    <AppBar position="static">
      <Toolbar sx={{ flexWrap: 'wrap' }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>Validador e-CF</Typography>
        {menu.map((m) => (
          <Button key={m.path} component={RouterLink} to={m.path} color="inherit"
            sx={{
              mx: 0.5, borderRadius: 0,
              borderBottom: activo(m.path) ? '2px solid currentColor' : '2px solid transparent',
            }}>
            {m.label}
          </Button>
        ))}
      </Toolbar>
    </AppBar>
  );
}
