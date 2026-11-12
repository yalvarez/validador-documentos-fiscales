import { Chip, Tooltip } from '@mui/material';
import type { ChipProps } from '@mui/material';
import { VERIFICACIONES } from '../api';

const COLOR_ESTADO: Record<string, ChipProps['color']> = {
  ACEPTADO: 'success',
  ACEPTADO_CONDICIONAL: 'success',
  RECHAZADO: 'error',
  ANULADO: 'error',
  PENDIENTE: 'warning',
  NO_ENCONTRADO: 'warning',
  DESCONOCIDO: 'default',
};

export function EstadoChip({ estado }: { estado: string }) {
  return <Chip size="small" label={estado.replace(/_/g, ' ')} color={COLOR_ESTADO[estado] ?? 'default'} />;
}

const COLOR_RESULTADO: Record<string, ChipProps['color']> = { OK: 'success', FALLO: 'error' };
const LETRA: Record<string, string> = { OK: '✓', FALLO: '✗', NO_VERIFICABLE: '?' };

export function ResultadoChip({ resultado, etiqueta }: { resultado: string; etiqueta?: string }) {
  return (
    <Chip size="small" variant={resultado === 'NO_VERIFICABLE' ? 'outlined' : 'filled'}
      color={COLOR_RESULTADO[resultado] ?? 'default'}
      label={etiqueta ? `${etiqueta}: ${resultado.replace(/_/g, ' ')}` : resultado.replace(/_/g, ' ')} />
  );
}

export function Semaforo({ verificaciones }: { verificaciones: Record<string, string> }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {Object.entries(verificaciones).map(([k, r]) => (
        <Tooltip key={k} title={`${VERIFICACIONES[k] ?? k}: ${r.replace(/_/g, ' ')}`}>
          <Chip size="small" sx={{ minWidth: 26, '& .MuiChip-label': { px: 0.5 } }}
            variant={r === 'NO_VERIFICABLE' ? 'outlined' : 'filled'}
            color={COLOR_RESULTADO[r] ?? 'default'} label={LETRA[r] ?? '·'} />
        </Tooltip>
      ))}
    </span>
  );
}
