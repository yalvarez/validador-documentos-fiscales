from datetime import datetime

from pydantic import BaseModel
from typing import Optional
from fastapi import UploadFile, File


class ValidarFacturaIn(BaseModel):
    rnc_emisor: str

# Esquema para recibir PDF en base64
class ValidarFacturaBase64In(BaseModel):
    pdf_base64: str
    rnc_emisor: str = None

class ValidacionFacturaOut(BaseModel):
    rnc_emisor: Optional[str] = None
    razon_social_emisor: Optional[str] = None
    estado: Optional[str] = None

class FacturaOut(BaseModel):
    id: Optional[int] = None
    message_id: Optional[str] = None
    rncemisor: Optional[str] = None
    rnccomprador: Optional[str] = None
    ncfelectronico: Optional[str] = None
    fechaemision: Optional[str] = None
    montototal: Optional[str] = None
    fechafirma: Optional[str] = None
    codigoseguridad: Optional[str] = None
    estado: Optional[str] = None
    url_validacion: Optional[str] = None
    razon_social_emisor: Optional[str] = None
    estado_envio: Optional[str] = None
    mensaje_error: Optional[str] = None
    fecha: Optional[str] = None

class MensajeOut(BaseModel):
    id: Optional[int] = None
    message_id: Optional[str] = None
    fecha: Optional[str] = None
    remitente: Optional[str] = None
    asunto: Optional[str] = None


class ParametroIn(BaseModel):
    valor: str
    descripcion: Optional[str] = None

class ParametroOut(BaseModel):
    clave: str
    valor: str
    descripcion: Optional[str] = None
    ultima_actualizacion: Optional[str] = None


# Esquema para los parámetros de la URL del PDF
class ConsultaFacturaParamsIn(BaseModel):
    RncEmisor: str
    RncComprador: Optional[str] = None
    ENCF: str
    FechaEmision: Optional[str] = None
    MontoTotal: Optional[str] = None
    FechaFirma: Optional[str] = None
    CodigoSeguridad: Optional[str] = None


class VerificacionOut(BaseModel):
    resultado: str
    detalle: str = ''


class ComprobanteEstadoOut(BaseModel):
    registrado: bool = True
    rnc_emisor: str
    encf: str
    razon_social_emisor: Optional[str] = None
    estado: str
    estado_dgii_texto: Optional[str] = None
    ultima_consulta_dgii: Optional[datetime] = None
    seguimiento_activo: bool
    seguimiento_hasta: Optional[datetime] = None
    validacion: dict[str, VerificacionOut]


class ComprobanteResumenOut(BaseModel):
    rnc_emisor: str
    encf: str
    rnc_comprador: Optional[str] = None
    tipo_ecf: Optional[str] = None
    fecha_emision: Optional[str] = None
    monto_total: Optional[str] = None
    razon_social_emisor: Optional[str] = None
    origen: str
    estado: str
    estado_dgii_texto: Optional[str] = None
    ultima_consulta_dgii: Optional[datetime] = None
    seguimiento_activo: bool
    seguimiento_hasta: Optional[datetime] = None
    creado_en: Optional[datetime] = None
    verificaciones: dict[str, str]


class ListaComprobantesOut(BaseModel):
    total: int
    items: list[ComprobanteResumenOut]


class EventoHistorialOut(BaseModel):
    fecha: datetime
    tipo: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    estado_dgii_texto: Optional[str] = None
    detalle: Optional[str] = None


class ParametroConsolaOut(BaseModel):
    clave: str
    valor: Optional[str] = None
    por_defecto: str
    descripcion: str
    ultima_actualizacion: Optional[datetime] = None


class ParametroValorIn(BaseModel):
    valor: str
