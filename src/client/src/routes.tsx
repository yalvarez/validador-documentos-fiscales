import { Route, Routes, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import Parametros from './pages/Parametros';
import Dashboard from './pages/Dashboard';
import Consulta from './pages/Consulta';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Parametros />} />
      <Route path="/parametros" element={<Parametros />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/consulta" element={<Consulta />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}
