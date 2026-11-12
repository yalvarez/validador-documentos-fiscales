import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Alert, Box, Container, FormControlLabel, LinearProgress, Link, MenuItem, Paper, Switch, Table, TableBody,
  TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography,
} from '@mui/material';
import { api, fecha, mensajeError, monto, type ComprobanteResumen } from '../api';
import { EstadoChip, Semaforo } from '../components/Indicadores';

const ESTADOS = ['', 'PENDIENTE', 'ACEPTADO', 'ACEPTADO_CONDICIONAL', 'RECHAZADO', 'NO_ENCONTRADO', 'DESCONOCIDO'];

export default function Comprobantes() {
  const [items, setItems] = useState<ComprobanteResumen[]>([]);
  const [total, setTotal] = useState(0);
  const [respondida, setRespondida] = useState('');
  const [error, setError] = useState('');
  const [pagina, setPagina] = useState(0);
  const [porPagina, setPorPagina] = useState(25);
  const [texto, setTexto] = useState('');
  const [q, setQ] = useState('');
  const [estado, setEstado] = useState('');
  const [conFallo, setConFallo] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setQ(texto); setPagina(0); }, 350);
    return () => clearTimeout(t);
  }, [texto]);

  // Cargando = la consulta pedida todavía no respondió.
  const consulta = JSON.stringify([q, estado, conFallo, pagina, porPagina]);
  const cargando = respondida !== consulta;

  useEffect(() => {
    let vigente = true;
    api.get('/comprobantes', {
      params: {
        q: q || undefined, estado: estado || undefined, con_fallo: conFallo || undefined,
        limite: porPagina, desde: pagina * porPagina,
      },
    }).then((r) => {
      if (!vigente) return;
      setItems(r.data.items); setTotal(r.data.total); setError('');
    }).catch((e) => { if (vigente) setError(mensajeError(e)); })
      .finally(() => { if (vigente) setRespondida(consulta); });
    return () => { vigente = false; };
  }, [consulta, q, estado, conFallo, pagina, porPagina]);

  return (
    <Container maxWidth="xl" sx={{ mt: 3, mb: 4 }}>
      <Typography variant="h5" gutterBottom>Comprobantes</Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', mb: 2 }}>
        <TextField size="small" label="Buscar e-NCF, RNC o razón social" value={texto}
          onChange={(e) => setTexto(e.target.value)} sx={{ minWidth: 300 }} />
        <TextField size="small" select label="Estado DGII" value={estado} sx={{ minWidth: 200 }}
          onChange={(e) => { setEstado(e.target.value); setPagina(0); }}>
          {ESTADOS.map((s) => <MenuItem key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'Todos'}</MenuItem>)}
        </TextField>
        <FormControlLabel label="Solo con verificaciones en FALLO" control={
          <Switch checked={conFallo} onChange={(e) => { setConFallo(e.target.checked); setPagina(0); }} />} />
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper variant="outlined">
        {cargando && <LinearProgress />}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>e-NCF</TableCell>
                <TableCell>Emisor</TableCell>
                <TableCell>Emisión</TableCell>
                <TableCell align="right">Monto</TableCell>
                <TableCell>Estado DGII</TableCell>
                <TableCell>Verificaciones</TableCell>
                <TableCell>Última consulta</TableCell>
                <TableCell>Registrado</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((c) => (
                <TableRow key={`${c.rnc_emisor}/${c.encf}`} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/comprobantes/${c.rnc_emisor}/${c.encf}`}>{c.encf}</Link>
                  </TableCell>
                  <TableCell>
                    <div>{c.razon_social_emisor ?? '-'}</div>
                    <Typography variant="caption" color="text.secondary">{c.rnc_emisor}</Typography>
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{c.fecha_emision ?? '-'}</TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{monto(c.monto_total)}</TableCell>
                  <TableCell>
                    <EstadoChip estado={c.estado} />
                    {c.seguimiento_activo && (
                      <Typography variant="caption" display="block" color="text.secondary">en seguimiento</Typography>
                    )}
                  </TableCell>
                  <TableCell><Semaforo verificaciones={c.verificaciones} /></TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{fecha(c.ultima_consulta_dgii)}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{fecha(c.creado_en)}</TableCell>
                </TableRow>
              ))}
              {!cargando && items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                    No hay comprobantes{q || estado || conFallo ? ' con esos filtros' : ' registrados'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination component="div" count={total} page={pagina} rowsPerPage={porPagina}
          rowsPerPageOptions={[25, 50, 100]} labelRowsPerPage="Por página"
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} de ${count}`}
          onPageChange={(_, p) => setPagina(p)}
          onRowsPerPageChange={(e) => { setPorPagina(parseInt(e.target.value, 10)); setPagina(0); }} />
      </Paper>
    </Container>
  );
}
