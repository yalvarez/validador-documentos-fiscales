import { Navigate, Route, Routes } from 'react-router-dom';
import Comprobantes from './pages/Comprobantes';
import Detalle from './pages/Detalle';
import Parametros from './pages/Parametros';
import Registrar from './pages/Registrar';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Comprobantes />} />
      <Route path="/comprobantes/:rnc/:encf" element={<Detalle />} />
      <Route path="/registrar" element={<Registrar />} />
      <Route path="/parametros" element={<Parametros />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}
