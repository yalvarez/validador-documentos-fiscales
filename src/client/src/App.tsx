import { MsalProvider } from '@azure/msal-react';
import { PublicClientApplication } from '@azure/msal-browser';
import { ThemeProvider, CssBaseline } from '@mui/material';
import theme from './theme';
import AppRoutes from './routes';
import { BrowserRouter } from 'react-router-dom';
import MainMenu from './components/MainMenu';
import { useEffect, useState } from 'react';

function App() {
  const [msalInstance, setMsalInstance] = useState<PublicClientApplication | null>(null);

  useEffect(() => {
    fetch('/config.json')
      .then(res => res.json())
      .then(config => {
        const msalConfig = {
          auth: {
            clientId: config.VITE_AZURE_CLIENT_ID,
            authority: `https://login.microsoftonline.com/${config.VITE_AZURE_TENANT_ID}`,
            redirectUri: window.location.origin,
          },
          cache: {
            cacheLocation: 'localStorage',
            storeAuthStateInCookie: false,
          },
        };
        setMsalInstance(new PublicClientApplication(msalConfig));
        // Puedes guardar config.VITE_API_URL en window/globalThis para usarlo en axios
        window.VITE_API_URL = config.VITE_API_URL;
      });
  }, []);

  if (!msalInstance) return null; // O un loader/spinner

  return (
    <MsalProvider instance={msalInstance}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <MainMenu />
          <AppRoutes />
        </BrowserRouter>
      </ThemeProvider>
    </MsalProvider>
  );
}

export default App;