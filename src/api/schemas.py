from pydantic import BaseModel
from typing import Optional

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
