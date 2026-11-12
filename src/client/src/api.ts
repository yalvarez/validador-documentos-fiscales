import axios from 'axios';

export const api = axios.create({ baseURL: '/client/api' });

export type Resultado = 'OK' | 'FALLO' | 'NO_VERIFICABLE' | string;

export const VERIFICACIONES: Record<string, string> = {
  estructura: 'Estructura (XSD)',
  integridad: 'Integridad de la firma',
  vigencia: 'Vigencia del certificado',
  entidad_certificadora: 'Entidad certificadora',
  revocacion: 'Revocación',
  cruce: 'Cruce con el PDF',
  comprador: 'Comprador',
};

export interface ComprobanteResumen {
  rnc_emisor: string;
  encf: string;
  rnc_comprador: string | null;
  tipo_ecf: string | null;
  fecha_emision: string | null;
  monto_total: string | null;
  razon_social_emisor: string | null;
  origen: string;
  estado: string;
  estado_dgii_texto: string | null;
  ultima_consulta_dgii: string | null;
  seguimiento_activo: boolean;
  seguimiento_hasta: string | null;
  creado_en: string | null;
  verificaciones: Record<string, Resultado>;
}

export interface ComprobanteEstado {
  rnc_emisor: string;
  encf: string;
  razon_social_emisor: string | null;
  estado: string;
  estado_dgii_texto: string | null;
  ultima_consulta_dgii: string | null;
  seguimiento_activo: boolean;
  seguimiento_hasta: string | null;
  validacion: Record<string, { resultado: Resultado; detalle: string }>;
}

export interface Evento {
  fecha: string;
  tipo: string;
  estado_anterior: string | null;
  estado_nuevo: string | null;
  estado_dgii_texto: string | null;
  detalle: string | null;
}

export interface Parametro {
  clave: string;
  valor: string | null;
  por_defecto: string;
  descripcion: string;
  ultima_actualizacion: string | null;
}

export function mensajeError(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join('; ');
    if (e.response) return `Error ${e.response.status}`;
    return 'No se pudo conectar con la API';
  }
  return String(e);
}

export function fecha(iso: string | null | undefined): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('es-DO', { timeZone: 'America/Santo_Domingo', dateStyle: 'short', timeStyle: 'short' });
}

export function monto(v: string | null | undefined): string {
  if (v == null) return '-';
  return 'RD$ ' + Number(v).toLocaleString('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
