import { useEffect, useState } from 'react';
import axios from 'axios';
import { Container, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper } from '@mui/material';

interface Mensaje {
  id?: number;
  message_id?: string;
  fecha?: string;
  remitente?: string;
  asunto?: string;
}

export default function Mensajes() {
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);

  useEffect(() => {
    const fetchMensajes = async () => {
      const res = await axios.get('/mensajes/', {
        baseURL: import.meta.env.VITE_API_URL,
      });
      setMensajes(res.data);
    };
    fetchMensajes();
  }, []);

  return (
    <Container maxWidth="xl" sx={{ mt: 4 }}>
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>Mensajes Recibidos</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Message ID</TableCell>
              <TableCell>Fecha</TableCell>
              <TableCell>Remitente</TableCell>
              <TableCell>Asunto</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {mensajes.map(m => (
              <TableRow key={m.id}>
                <TableCell>{m.id}</TableCell>
                <TableCell>{m.message_id}</TableCell>
                <TableCell>{m.fecha}</TableCell>
                <TableCell>{m.remitente}</TableCell>
                <TableCell>{m.asunto}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Container>
  );
}
