import { useEffect, useState } from 'react';
import axios from 'axios';
import { Container, Typography, Grid, Paper, Box, CircularProgress } from '@mui/material';

interface DashboardData {
  totalMensajes: number;
  totalFacturas: number;
  facturasAceptadas: number;
  facturasRechazadas: number;
  facturasPendientes: number;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      const res = await axios.get('/dashboard', {
        baseURL: import.meta.env.VITE_API_URL,
      });
      setData(res.data);
      setLoading(false);
    };
    fetchDashboard();
  }, []);

  if (loading || !data) return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
      <CircularProgress />
    </Box>
  );

  return (
    <Container maxWidth="md" sx={{ mt: 4 }}>
      <Typography variant="h5" gutterBottom>Dashboard</Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">Mensajes</Typography>
            <Typography variant="h4">{data.totalMensajes}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">Facturas</Typography>
            <Typography variant="h4">{data.totalFacturas}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">Aceptadas</Typography>
            <Typography variant="h4" color="success.main">{data.facturasAceptadas}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">Rechazadas</Typography>
            <Typography variant="h4" color="error.main">{data.facturasRechazadas}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">Pendientes</Typography>
            <Typography variant="h4" color="warning.main">{data.facturasPendientes}</Typography>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}
