import { Route, Routes, Navigate } from 'react-router-dom';
import Parametros from './pages/Parametros';
import Dashboard from './pages/Dashboard';
import Consulta from './pages/Consulta';
import Facturas from './pages/Facturas';
import Mensajes from './pages/Mensajes';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Facturas />} />
      <Route path="/parametros" element={<Parametros />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/consulta" element={<Consulta />} />
      <Route path="/facturas" element={<Facturas />} />
      <Route path="/mensajes" element={<Mensajes />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}
