import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Container, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
  Typography,
} from '@mui/material';
import { api, fecha, mensajeError, type Parametro } from '../api';

export default function Parametros() {
  const [params, setParams] = useState<Parametro[]>([]);
  const [edicion, setEdicion] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const cargar = useCallback(() => api.get<Parametro[]>('/parametros').then((r) => {
    setParams(r.data);
    setEdicion(Object.fromEntries(r.data.map((p) => [p.clave, p.valor ?? ''])));
  }).catch((e) => setError(mensajeError(e))), []);

  useEffect(() => { cargar(); }, [cargar]);

  const guardar = async (clave: string) => {
    setError(''); setAviso('');
    try {
      await api.put(`/parametros/${clave}`, { valor: edicion[clave] ?? '' });
      setAviso(`${clave} guardado`);
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 3, mb: 4 }}>
      <Typography variant="h5" gutterBottom>Parámetros</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Vacío = valor por defecto. Los cambios aplican a los próximos registros y ciclos del seguimiento.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {aviso && <Alert severity="success" sx={{ mb: 2 }}>{aviso}</Alert>}
      <Paper variant="outlined">
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Parámetro</TableCell>
                <TableCell>Valor</TableCell>
                <TableCell>Por defecto</TableCell>
                <TableCell>Actualizado</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {params.map((p) => (
                <TableRow key={p.clave}>
                  <TableCell>
                    <div><code>{p.clave}</code></div>
                    <Typography variant="caption" color="text.secondary">{p.descripcion}</Typography>
                  </TableCell>
                  <TableCell>
                    <TextField size="small" value={edicion[p.clave] ?? ''} placeholder={p.por_defecto}
                      onChange={(e) => setEdicion({ ...edicion, [p.clave]: e.target.value })} />
                  </TableCell>
                  <TableCell>{p.por_defecto}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{fecha(p.ultima_actualizacion)}</TableCell>
                  <TableCell>
                    <Button size="small" variant="contained"
                      disabled={(edicion[p.clave] ?? '').trim() === (p.valor ?? '')}
                      onClick={() => guardar(p.clave)}>Guardar</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Container>
  );
}
