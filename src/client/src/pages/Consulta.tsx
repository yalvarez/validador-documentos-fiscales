import { useEffect, useState } from 'react';
import axios from 'axios';
import { Container, Typography, Table, TableBody, TableCell, TableHead, TableRow, TablePagination, Paper, Box, CircularProgress, TextField, Button } from '@mui/material';

interface Factura {
  id: number;
  message_id: string;
  rncemisor: string;
  rnccomprador: string;
  ncfelectronico: string;
  fechaemision: string;
  montototal: string;
  estado: string;
  estado_envio: string;
  fecha: string;
}

export default function Consulta() {
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [filtro, setFiltro] = useState('');

  useEffect(() => {
    const fetchFacturas = async () => {
      setLoading(true);
      const res = await axios.get('/facturas', {
        baseURL: window.VITE_API_URL,
        params: filtro ? { filtro } : {},
      });
      setFacturas(res.data);
      setLoading(false);
    };
    fetchFacturas();
  }, [filtro]);

  const handleChangePage = (_: any, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: any) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  if (loading) return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
      <CircularProgress />
    </Box>
  );

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>Consulta de Facturas</Typography>
        <Box sx={{ mb: 2, display: 'flex', gap: 2 }}>
          <TextField label="Buscar por RNC, NCF o estado" value={filtro} onChange={e => setFiltro(e.target.value)} size="small" />
          <Button variant="outlined" onClick={() => setFiltro('')}>Limpiar</Button>
        </Box>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Emisor</TableCell>
              <TableCell>Comprador</TableCell>
              <TableCell>NCF</TableCell>
              <TableCell>Fecha</TableCell>
              <TableCell>Monto</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell>Envio</TableCell>
              <TableCell>Fecha Registro</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {facturas.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage).map(f => (
              <TableRow key={f.id}>
                <TableCell>{f.id}</TableCell>
                <TableCell>{f.rncemisor}</TableCell>
                <TableCell>{f.rnccomprador}</TableCell>
                <TableCell>{f.ncfelectronico}</TableCell>
                <TableCell>{f.fechaemision}</TableCell>
                <TableCell>{f.montototal}</TableCell>
                <TableCell>{f.estado}</TableCell>
                <TableCell>{f.estado_envio}</TableCell>
                <TableCell>{f.fecha}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={facturas.length}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>
    </Container>
  );
}
