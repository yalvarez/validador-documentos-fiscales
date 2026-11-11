from dataclasses import dataclass
from datetime import timedelta, timezone

ZONA_RD = timezone(timedelta(hours=-4))

# Resultados de una verificación
OK = 'OK'
FALLO = 'FALLO'
NO_VERIFICABLE = 'NO_VERIFICABLE'

# Estados del comprobante
PENDIENTE = 'PENDIENTE'
ACEPTADO = 'ACEPTADO'
ACEPTADO_CONDICIONAL = 'ACEPTADO_CONDICIONAL'
RECHAZADO = 'RECHAZADO'
NO_ENCONTRADO = 'NO_ENCONTRADO'
DESCONOCIDO = 'DESCONOCIDO'

# Tipos de evento
REGISTRO = 'REGISTRO'
CONSULTA = 'CONSULTA'
CAMBIO_ESTADO = 'CAMBIO_ESTADO'
ERROR_CONSULTA = 'ERROR_CONSULTA'
DOCUMENTO_REEMPLAZADO = 'DOCUMENTO_REEMPLAZADO'


@dataclass
class Verificacion:
    resultado: str
    detalle: str = ''


@dataclass
class ResultadoValidacionXML:
    estructura: Verificacion
    integridad: Verificacion
    vigencia: Verificacion
    entidad_certificadora: Verificacion
    revocacion: Verificacion
    cruce: Verificacion
    comprador: Verificacion
    certificado_titular: str | None = None
    certificado_emisor: str | None = None
    certificado_serie: str | None = None

    def a_dict(self) -> dict[str, dict[str, str]]:
        campos = ('estructura', 'integridad', 'vigencia', 'entidad_certificadora',
                  'revocacion', 'cruce', 'comprador')
        return {c: {'resultado': getattr(self, c).resultado, 'detalle': getattr(self, c).detalle}
                for c in campos}
