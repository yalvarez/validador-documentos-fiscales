import { CssBaseline, ThemeProvider } from '@mui/material';
import { BrowserRouter } from 'react-router-dom';
import MainMenu from './components/MainMenu';
import AppRoutes from './routes';
import theme from './theme';

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter basename="/client">
        <MainMenu />
        <AppRoutes />
      </BrowserRouter>
    </ThemeProvider>
  );
}
