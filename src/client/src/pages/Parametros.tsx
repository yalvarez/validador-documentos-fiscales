import { useEffect, useState } from 'react';
import axios from 'axios';
import { Container, Typography, Table, TableBody, TableCell, TableHead, TableRow, Button, TextField, Paper } from '@mui/material';

interface Parametro {
  clave: string;
  valor: string;
  descripcion?: string;
  ultima_actualizacion?: string;
}

export default function Parametros() {
  const [parametros, setParametros] = useState<Parametro[]>([]);
  const [edit, setEdit] = useState<{ [clave: string]: string }>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchParametros = async () => {
      setLoading(true);
      const res = await axios.get('/parametros/', {
        baseURL: import.meta.env.VITE_API_URL,
      });
      setParametros(res.data);
      setLoading(false);
    };
    fetchParametros();
  }, []);

  const handleEdit = (clave: string, valor: string) => {
    setEdit((prev) => ({ ...prev, [clave]: valor }));
  };

  const handleSave = async (clave: string) => {
    await axios.post(`/parametros/${clave}`, { valor: edit[clave] }, {
      baseURL: import.meta.env.VITE_API_URL,
    });
    setEdit((prev) => {
      const newEdit = { ...prev };
      delete newEdit[clave];
      return newEdit;
    });
    // Refrescar
    const res = await axios.get('/parametros/', {
      baseURL: import.meta.env.VITE_API_URL,
    });
    setParametros(res.data);
  };

  return (
    <Container maxWidth="md" sx={{ mt: 4 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>Parámetros de Configuración</Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Clave</TableCell>
              <TableCell>Valor</TableCell>
              <TableCell>Descripción</TableCell>
              <TableCell>Última actualización</TableCell>
              <TableCell>Acción</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {parametros.map((p) => (
              <TableRow key={p.clave}>
                <TableCell>{p.clave}</TableCell>
                <TableCell>
                  <TextField
                    value={edit[p.clave] ?? p.valor}
                    onChange={e => handleEdit(p.clave, e.target.value)}
                    size="small"
                  />
                </TableCell>
                <TableCell>{p.descripcion}</TableCell>
                <TableCell>{p.ultima_actualizacion}</TableCell>
                <TableCell>
                  <Button variant="contained" size="small" onClick={() => handleSave(p.clave)} disabled={loading}>
                    Guardar
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Container>
  );
}
