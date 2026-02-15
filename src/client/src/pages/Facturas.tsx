import { useEffect, useState } from 'react';
import axios from 'axios';
import { Container, Typography, Grid, Card, CardContent, CardHeader, Chip, Box, Link } from '@mui/material';

interface Factura {
  id?: number;
  message_id?: string;
  rncemisor?: string;
  rnccomprador?: string;
  ncfelectronico?: string;
  fechaemision?: string;
  montototal?: string;
  fechafirma?: string;
  codigoseguridad?: string;
  estado?: string;
  url_validacion?: string;
  razon_social_emisor?: string;
  estado_envio?: string;
  mensaje_error?: string;
  fecha?: string;
}

export default function Facturas() {
  const [facturas, setFacturas] = useState<Factura[]>([]);

  useEffect(() => {
    const fetchFacturas = async () => {
      const res = await axios.get('/facturas/', {
        baseURL: import.meta.env.VITE_API_URL,
      });
      setFacturas(res.data);
    };
    fetchFacturas();
  }, []);

  return (
    <Container maxWidth="xl" sx={{ mt: 4 }}>
      <Typography variant="h5" gutterBottom>Facturas</Typography>
      <Grid container spacing={3}>
        {facturas.map(f => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={f.id}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardHeader
                title={`NCF: ${f.ncfelectronico || ''}`}
                subheader={`Emisor: ${f.rncemisor || ''}`}
                action={
                  <Chip
                    label={f.estado || 'Sin estado'}
                    color={f.estado?.toLowerCase() === 'aceptado' ? 'success' : f.estado?.toLowerCase() === 'rechazado' ? 'error' : 'default'}
                    size="small"
                  />
                }
              />
              <CardContent>
                <Box mb={1}>
                  <strong>Razón social emisor:</strong> {f.razon_social_emisor || '-'}
                </Box>
                <Box mb={1}>
                  <strong>Comprador:</strong> {f.rnccomprador || '-'}
                </Box>
                <Box mb={1}>
                  <strong>Fecha Emisión:</strong> {f.fechaemision || '-'}
                </Box>
                <Box mb={1}>
                  <strong>Monto:</strong> {f.montototal || '-'}
                </Box>
                <Box mb={1}>
                  <strong>Fecha Firma:</strong> {f.fechafirma || '-'}
                </Box>
                <Box mb={1}>
                  <strong>Código Seguridad:</strong> {f.codigoseguridad || '-'}
                </Box>
                <Box mb={1}>
                  <strong>URL de Validación:</strong> {f.url_validacion ? (
                    <Link href={f.url_validacion} target="_blank" rel="noopener noreferrer" underline="hover">
                      Verificar
                    </Link>
                  ) : '-'}
                </Box>
                <Box mb={1}>
                  <strong>Envío:</strong> {f.estado_envio || '-'}
                </Box>
                {f.mensaje_error && (
                  <Box mb={1} color="error.main">
                    <strong>Error:</strong> {f.mensaje_error}
                  </Box>
                )}
                <Box mb={1}>
                  <strong>Fecha Registro:</strong> {f.fecha || '-'}
                </Box>
                <Box mb={1}>
                  <strong>ID Mensaje:</strong> {f.message_id || '-'}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
}
