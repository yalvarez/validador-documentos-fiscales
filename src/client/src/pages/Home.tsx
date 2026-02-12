import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import { Button, Box, Typography } from '@mui/material';

export default function Home() {
  const { instance } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const handleLogin = () => {
    instance.loginRedirect();
  };
  const handleLogout = () => {
    instance.logoutRedirect();
  };

  return (
    <Box sx={{ p: 4 }}>
      <Typography variant="h4" gutterBottom>
        Validador Documentos Fiscales
      </Typography>
      {isAuthenticated ? (
        <Button variant="contained" color="secondary" onClick={handleLogout}>
          Cerrar sesión
        </Button>
      ) : (
        <Button variant="contained" color="primary" onClick={handleLogin}>
          Iniciar sesión con Microsoft
        </Button>
      )}
    </Box>
  );
}
