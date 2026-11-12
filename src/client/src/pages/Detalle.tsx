import { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Alert, Box, Breadcrumbs, Card, CardContent, CardHeader, Container, LinearProgress, Link, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import axios from 'axios';
import { api, fecha, mensajeError, VERIFICACIONES, type ComprobanteEstado, type Evento } from '../api';
import { EstadoChip, ResultadoChip } from '../components/Indicadores';

const TIPO_EVENTO: Record<string, string> = {
  REGISTRO: 'Registrado',
  CONSULTA: 'Consulta a la DGII',
  CAMBIO_ESTADO: 'Cambio de estado',
  ERROR_CONSULTA: 'Error al consultar la DGII',
  DOCUMENTO_RECHAZADO: 'XML distinto rechazado',
  DOCUMENTO_REEMPLAZADO: 'XML reemplazado',
};

export default function Detalle() {
  const { rnc = '', encf = '' } = useParams();
  const [c, setC] = useState<ComprobanteEstado | null>(null);
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    const base = `/comprobantes/${encodeURIComponent(rnc)}/${encodeURIComponent(encf)}`;
    Promise.all([api.get(base), api.get(`${base}/historial`)])
      .then(([a, b]) => { setC(a.data); setEventos(b.data); })
      .catch((e) => setError(axios.isAxiosError(e) && e.response?.status === 404
        ? 'Comprobante no registrado' : mensajeError(e)))
      .finally(() => setCargando(false));
  }, [rnc, encf]);

  return (
    <Container maxWidth="lg" sx={{ mt: 3, mb: 4 }}>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link component={RouterLink} to="/">Comprobantes</Link>
        <Typography color="text.primary">{encf}</Typography>
      </Breadcrumbs>
      {cargando && <LinearProgress />}
      {error && <Alert severity="error">{error}</Alert>}
      {c && (
        <Box sx={{ display: 'grid', gap: 2 }}>
          <Card variant="outlined">
            <CardHeader title={c.encf} subheader={`${c.razon_social_emisor ?? 'Emisor'} · RNC ${c.rnc_emisor}`}
              action={<EstadoChip estado={c.estado} />} />
            <CardContent sx={{ pt: 0 }}>
              <Typography variant="body2">Texto DGII: {c.estado_dgii_texto ?? '-'}</Typography>
              <Typography variant="body2">Última consulta: {fecha(c.ultima_consulta_dgii)}</Typography>
              <Typography variant="body2">
                Seguimiento: {c.seguimiento_activo ? `activo hasta ${fecha(c.seguimiento_hasta)}` : 'cerrado'}
              </Typography>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardHeader title="Verificaciones del XML" titleTypographyProps={{ variant: 'h6' }} />
            <TableContainer>
              <Table size="small">
                <TableBody>
                  {Object.entries(c.validacion).map(([k, v]) => (
                    <TableRow key={k}>
                      <TableCell sx={{ width: 220 }}>{VERIFICACIONES[k] ?? k}</TableCell>
                      <TableCell sx={{ width: 170 }}><ResultadoChip resultado={v.resultado} /></TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>{v.detalle || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>

          <Card variant="outlined">
            <CardHeader title="Historial" titleTypographyProps={{ variant: 'h6' }} />
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Fecha</TableCell>
                    <TableCell>Evento</TableCell>
                    <TableCell>Estado</TableCell>
                    <TableCell>Detalle</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {eventos.map((e, i) => (
                    <TableRow key={i}>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{fecha(e.fecha)}</TableCell>
                      <TableCell>{TIPO_EVENTO[e.tipo] ?? e.tipo}</TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>
                        {e.estado_nuevo ? `${e.estado_anterior ?? '-'} → ${e.estado_nuevo}` : (e.estado_dgii_texto ?? '')}
                      </TableCell>
                      <TableCell sx={{ color: 'text.secondary', wordBreak: 'break-word' }}>{e.detalle ?? ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </Box>
      )}
    </Container>
  );
}
