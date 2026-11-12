import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Alert, Box, Button, Card, CardContent, Container, Link, Typography } from '@mui/material';
import { api, mensajeError, type ComprobanteEstado } from '../api';
import { EstadoChip } from '../components/Indicadores';

export default function Registrar() {
  const [xml, setXml] = useState<File | null>(null);
  const [pdf, setPdf] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<ComprobanteEstado | null>(null);

  const enviar = async () => {
    if (!xml) return;
    const datos = new FormData();
    datos.append('xml', xml);
    if (pdf) datos.append('pdf', pdf);
    setEnviando(true); setError(''); setResultado(null);
    try {
      setResultado((await api.post('/comprobantes', datos)).data);
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 3, mb: 4 }}>
      <Typography variant="h5" gutterBottom>Registrar un e-CF</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        El XML basta para validar y consultar la DGII. El PDF es opcional: si lo adjunta, los datos de su QR
        se cruzan con el XML. Un comprobante ya registrado no se reemplaza con otro XML.
      </Typography>
      <Card variant="outlined">
        <CardContent sx={{ display: 'grid', gap: 2 }}>
          <Button variant="outlined" component="label">
            {xml ? `XML: ${xml.name}` : 'Elegir XML (obligatorio)'}
            <input hidden type="file" accept=".xml,application/xml,text/xml"
              onChange={(e) => setXml(e.target.files?.[0] ?? null)} />
          </Button>
          <Button variant="outlined" component="label">
            {pdf ? `PDF: ${pdf.name}` : 'Elegir PDF (opcional)'}
            <input hidden type="file" accept=".pdf,application/pdf"
              onChange={(e) => setPdf(e.target.files?.[0] ?? null)} />
          </Button>
          <Button variant="contained" disabled={!xml || enviando} onClick={enviar}>
            {enviando ? 'Validando y consultando la DGII…' : 'Registrar'}
          </Button>
        </CardContent>
      </Card>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {resultado && (
        <Alert severity="success" sx={{ mt: 2 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
            Registrado <EstadoChip estado={resultado.estado} />
          </Box>
          <Link component={RouterLink} to={`/comprobantes/${resultado.rnc_emisor}/${resultado.encf}`}>
            Ver {resultado.encf}
          </Link>
        </Alert>
      )}
    </Container>
  );
}
