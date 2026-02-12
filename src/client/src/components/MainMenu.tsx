import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';

const menuItems = [
  { label: 'Dashboard', path: '/dashboard' },
  { label: 'Parámetros', path: '/parametros' },
  { label: 'Consulta', path: '/consulta' },
];

export default function MainMenu() {
  const location = useLocation();
  const isAuthenticated = useIsAuthenticated();
  const { instance } = useMsal();

  const handleLogout = () => instance.logoutRedirect();

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Validador Documentos Fiscales
        </Typography>
        {isAuthenticated && menuItems.map(item => (
          <Button
            key={item.path}
            color={location.pathname === item.path ? 'secondary' : 'inherit'}
            component={RouterLink}
            to={item.path}
            sx={{ mx: 1 }}
          >
            {item.label}
          </Button>
        ))}
        {isAuthenticated && (
          <Button color="inherit" onClick={handleLogout} sx={{ ml: 2 }}>
            Cerrar sesión
          </Button>
        )}
      </Toolbar>
    </AppBar>
  );
}
