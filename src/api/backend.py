import hashlib
import os
import requests
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Header
from starlette.concurrency import run_in_threadpool
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.schemas import ComprobanteEstadoOut, VerificacionOut
from api.schemas import ParametroOut, ParametroIn, FacturaOut, MensajeOut
from api.parametros_manager import ParametrosManager
from db.db_factory import get_db_wrapper
from db.config import leer_config_db
from common.pdf_processor.extractor import PDFProcessor
from common.validator.web_validator import WebValidator
import tempfile
from api.schemas import ValidacionFacturaOut, ValidarFacturaIn, ConsultaFacturaParamsIn, ValidarFacturaBase64In
import base64
from common.ecf.modelos import VERIFICACIONES, ZONA_RD
from common.ecf.lectura import ErrorLecturaECF
from common.ecf.registro import registrar_comprobante

MAX_BYTES_ARCHIVO = 10 * 1024 * 1024  # por archivo (XML o PDF)

API_KEYS = [k.strip() for k in (os.getenv('API_KEYS') or 'YomxbA2xGssmMF2xPmyrgsdxEHROstMP').split(',') if k.strip()]

app = FastAPI(title="Validador de Facturas DGII", version="1.0")
    
# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="API Key inválida")

def get_db():
    motor, config = leer_config_db()
    return get_db_wrapper(motor, config)

def _cerrar_db(db):
    if hasattr(db, 'close'):
        db.close()


def _guardar_factura(factura_dict):
    db = get_db()
    try:
        db.insert_factura(factura_dict)
    finally:
        _cerrar_db(db)

# def get_parametros_manager():    
#     return ParametrosManager(get_db())

# Configuración Entra ID (Azure AD)
# TENANT_ID = get_parametros_manager().get('AZURE_TENANT_ID')
# CLIENT_ID = get_parametros_manager().get('AZURE_CLIENT_ID')
# ALLOWED_GROUP_ID = get_parametros_manager().get('AZURE_ALLOWED_GROUP_ID')

# AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
# JWKS_URL = f"{AUTHORITY}/discovery/v2.0/keys"

# oauth2_scheme = OAuth2AuthorizationCodeBearer(
#     authorizationUrl=f"{AUTHORITY}/oauth2/v2.0/authorize",
#     tokenUrl=f"{AUTHORITY}/oauth2/v2.0/token",
#     scopes={"openid": "OpenID Connect scope"}
# )

# def get_jwks():
#     resp = requests.get(JWKS_URL)
#     resp.raise_for_status()
#     return resp.json()

# --- ENDPOINT PDF BASE64 ---
@app.post("/validar-factura-pdf-base64", response_model=ValidacionFacturaOut, description="Valida una factura a partir de un PDF codificado en base64. El cuerpo debe contener el PDF en base64 y opcionalmente el RNC del emisor para validación adicional. El endpoint decodifica el PDF, extrae la URL del QR, consulta la DGII y devuelve el estado de la factura junto con la razón social del emisor si está disponible." )
async def validar_factura_pdf_base64(
    body: ValidarFacturaBase64In,
    x_api_key: str = Depends(verify_api_key)
):
    # Decodificar el PDF desde base64
    try:
        pdf_bytes = base64.b64decode(body.pdf_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 inválido")

    # Guardar PDF temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
        tmp_pdf.write(pdf_bytes)
        tmp_pdf.flush()
        pdf_path = tmp_pdf.name

    # Extraer datos del QR
    pdf_proc = PDFProcessor(pdf_path)
    qr_url = pdf_proc.extract_qr_url()
    params = pdf_proc.extract_qr_params() if qr_url else {}

    # Validar RNC del emisor
    rnc_pdf = params.get('rncemisor') or params.get('RNCEmisor')
    rnc_emisor = body.rnc_emisor

    # Validar comprobante
    estado = None
    razon_social_emisor = None

    if rnc_emisor and rnc_pdf and rnc_emisor != rnc_pdf:
        estado = "rnc-no-coincide"
    else:
        if qr_url:
            web_validator = WebValidator()
            web_result = web_validator.validate(qr_url)
            if isinstance(web_result, dict):
                estado = web_result.get('estado')
                razon_social_emisor = web_result.get('razon_social_emisor')
            else:
                estado = web_result

    # Guardar en BD para trazabilidad
    factura_dict = {
        'rncemisor': params.get('rncemisor') or params.get('RNCEmisor'),
        'rnccomprador': params.get('rnccomprador') or params.get('RNCComprador'),
        'ncfelectronico': params.get('ncfelectronico') or params.get('ENCF'),
        'fechaemision': params.get('fechaemision') or params.get('FechaEmision'),
        'montototal': params.get('montototal') or params.get('MontoTotal'),
        'fechafirma': params.get('fechafirma') or params.get('FechaFirma'),
        'codigoseguridad': params.get('codigoseguridad') or params.get('CodigoSeguridad'),
        'url_validacion': qr_url,
        'razon_social_emisor': razon_social_emisor,
        'estado': estado
    }
    _guardar_factura(factura_dict)

    return ValidacionFacturaOut(
        rnc_emisor=factura_dict['rncemisor'],
        razon_social_emisor=factura_dict['razon_social_emisor'],
        estado=factura_dict['estado']
    )

@app.post("/validar-factura-pdf-multipart", response_model=ValidacionFacturaOut, description="Valida una factura a partir de un PDF enviado como multipart/form-data. El archivo PDF se procesa para extraer la URL del QR, se consulta la DGII y se devuelve el estado de la factura junto con la razón social del emisor si está disponible. Opcionalmente se puede enviar el RNC del emisor para validación adicional." )
async def validar_factura_pdf_multipart(
    file: UploadFile = File(...),
    rnc_emisor: str ='',
    x_api_key: str = Depends(verify_api_key)
):
    # Guardar PDF temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
        content = await file.read()
        tmp_pdf.write(content)
        tmp_pdf.flush()
        pdf_path = tmp_pdf.name

    # Extraer datos del QR
    pdf_proc = PDFProcessor(pdf_path)
    qr_url = pdf_proc.extract_qr_url()
    params = pdf_proc.extract_qr_params() if qr_url else {}

    # Validar RNC del emisor
    rnc_pdf = params.get('rncemisor') or params.get('RNCEmisor')
    
    # Validar comprobante
    estado = None
    razon_social_emisor = None

    if rnc_emisor and rnc_pdf and rnc_emisor != rnc_pdf:
        estado = "rnc-no-coincide"
    else:
        if qr_url:
            web_validator = WebValidator()
            web_result = web_validator.validate(qr_url)
            if isinstance(web_result, dict):
                estado = web_result.get('estado')
                razon_social_emisor = web_result.get('razon_social_emisor')
            else:
                estado = web_result

    # Guardar en BD para trazabilidad
    factura_dict = {
        'rncemisor': params.get('rncemisor') or params.get('RNCEmisor'),
        'rnccomprador': params.get('rnccomprador') or params.get('RNCComprador'),
        'ncfelectronico': params.get('ncfelectronico') or params.get('ENCF'),
        'fechaemision': params.get('fechaemision') or params.get('FechaEmision'),
        'montototal': params.get('montototal') or params.get('MontoTotal'),
        'fechafirma': params.get('fechafirma') or params.get('FechaFirma'),
        'codigoseguridad': params.get('codigoseguridad') or params.get('CodigoSeguridad'),
        'url_validacion': qr_url,
        'razon_social_emisor': razon_social_emisor,
        'estado': estado
    }
    _guardar_factura(factura_dict)

    return ValidacionFacturaOut(
        rnc_emisor=factura_dict['rncemisor'],
        razon_social_emisor=factura_dict['razon_social_emisor'],
        estado=factura_dict['estado']
    )


# Nuevo endpoint: consulta por parámetros de URL del PDF
@app.post("/validar-factura-params", response_model=ValidacionFacturaOut, description="Valida una factura a partir de parámetros de URL del PDF. El endpoint construye la URL de consulta igual que la del PDF, consulta la DGII y devuelve el estado de la factura junto con la razón social del emisor si está disponible." )
def validar_factura_params(
    body: ConsultaFacturaParamsIn,
    x_api_key: str = Depends(verify_api_key)
):
    # Construir la URL de consulta igual que la del PDF
    base_url = "https://ecf.dgii.gov.do/eCF/ConsultaTimbre"
    params = []
    if body.RncEmisor:
        params.append(f"RncEmisor={body.RncEmisor}")
    if body.RncComprador:
        params.append(f"RncComprador={body.RncComprador}")
    if body.ENCF:
        params.append(f"ENCF={body.ENCF}")
    if body.FechaEmision:
        params.append(f"FechaEmision={body.FechaEmision}")
    if body.MontoTotal:
        params.append(f"MontoTotal={body.MontoTotal}")
    if body.FechaFirma:
        params.append(f"FechaFirma={body.FechaFirma}")
    if body.CodigoSeguridad:
        params.append(f"CodigoSeguridad={body.CodigoSeguridad}")
    url = base_url + "?" + "&".join(params)

    # Validar usando el scrapper
    web_validator = WebValidator()
    web_result = web_validator.validate(url)
    estado = None
    razon_social_emisor = None
    if isinstance(web_result, dict):
        estado = web_result.get('estado')
        razon_social_emisor = web_result.get('razon_social_emisor')
    else:
        estado = web_result

    return ValidacionFacturaOut(
        rnc_emisor=body.RncEmisor,
        razon_social_emisor=razon_social_emisor,
        estado=estado
    )


def _validacion_ordenada(detalle: dict) -> dict:
    """Las verificaciones en el orden canónico (JSONB no conserva el orden de las claves)."""
    claves = [k for k in VERIFICACIONES if k in detalle] + [k for k in detalle if k not in VERIFICACIONES]
    return {k: VerificacionOut(**detalle[k]) for k in claves}


def _a_zona_rd(fecha):
    return fecha.astimezone(ZONA_RD) if fecha is not None else None


def _comprobante_out(c) -> ComprobanteEstadoOut:
    return ComprobanteEstadoOut(
        rnc_emisor=c['rnc_emisor'],
        encf=c['encf'],
        razon_social_emisor=c['razon_social_emisor'],
        estado=c['estado'],
        estado_dgii_texto=c['estado_dgii_texto'],
        ultima_consulta_dgii=_a_zona_rd(c['ultima_consulta_dgii']),
        seguimiento_activo=c['seguimiento_activo'],
        seguimiento_hasta=_a_zona_rd(c['seguimiento_hasta']),
        validacion=_validacion_ordenada(c['validacion_detalle'] or {}),
    )


def _exigir_postgres():
    if leer_config_db()[0] != 'postgres':
        raise HTTPException(status_code=503, detail="Requiere DB_ENGINE=postgres")


async def _leer_archivo(archivo: UploadFile | None, nombre: str) -> bytes | None:
    if archivo is None:
        return None
    datos = await archivo.read(MAX_BYTES_ARCHIVO + 1)
    if len(datos) > MAX_BYTES_ARCHIVO:
        raise HTTPException(status_code=413, detail=f"El archivo '{nombre}' supera {MAX_BYTES_ARCHIVO} bytes")
    return datos or None


@app.post("/comprobantes", response_model=ComprobanteEstadoOut,
          responses={409: {"description": "El comprobante ya está registrado con otro XML; no se reemplaza"},
                     413: {"description": "Archivo demasiado grande"},
                     422: {"description": "El XML no es un e-CF legible (mal formado, o sin RNCEmisor o eNCF)"},
                     503: {"description": "Requiere DB_ENGINE=postgres"}},
          description="Registra un e-CF: valida el XML (estructura contra la XSD de la DGII, integridad de la firma, "
                      "certificado del firmante, comprador) y consulta su estado en la DGII con una URL construida "
                      "siempre desde el XML firmado. El PDF es opcional: si viene, los datos de su QR se cruzan con "
                      "el XML (verificación `cruce`); sin PDF, `cruce` da NO_VERIFICABLE. El comprobante queda en "
                      "seguimiento periódico; su último estado se consulta con GET /comprobantes/{rnc_emisor}/{encf}. "
                      "Reenviar el mismo XML es idempotente (sirve para agregar el PDF después); un XML distinto "
                      "para un e-CF ya registrado se rechaza con 409 y nunca reemplaza al guardado.")
async def registrar_comprobante_api(xml: UploadFile = File(..., description="e-CF firmado (XML)"),
                                    pdf: UploadFile | None = File(None, description="Representación impresa (PDF con QR), opcional"),
                                    x_api_key: str = Depends(verify_api_key)):
    _exigir_postgres()
    xml_bytes = await _leer_archivo(xml, 'xml')
    if not xml_bytes:
        raise HTTPException(status_code=422, detail="El archivo 'xml' está vacío")
    pdf_bytes = await _leer_archivo(pdf, 'pdf')

    def _registrar():
        db = get_db()
        try:
            return registrar_comprobante(db, xml_bytes, pdf_bytes, origen='api')
        finally:
            _cerrar_db(db)
    try:
        c = await run_in_threadpool(_registrar)
    except ErrorLecturaECF as e:
        raise HTTPException(status_code=422, detail=str(e))
    if c['xml_hash_sha256'] != hashlib.sha256(xml_bytes).hexdigest():
        raise HTTPException(status_code=409, detail="El comprobante ya está registrado con otro XML; no se reemplaza")
    return _comprobante_out(c)


@app.get("/comprobantes/{rnc_emisor}/{encf}", response_model=ComprobanteEstadoOut,
         responses={404: {"description": "Comprobante no registrado: {\"registrado\": false}"},
                    503: {"description": "Requiere DB_ENGINE=postgres"}},
         description="Devuelve el último estado conocido de un e-CF registrado, con el resultado de cada verificación del XML. Fechas en zona horaria de RD (-04:00).")
def consultar_comprobante(rnc_emisor: str, encf: str, x_api_key: str = Depends(verify_api_key)):
    _exigir_postgres()
    db = get_db()
    try:
        c = db.get_comprobante(rnc_emisor, encf)
    finally:
        _cerrar_db(db)
    if c is None:
        return JSONResponse(status_code=404, content={"registrado": False})
    return _comprobante_out(c)


# def get_current_user(token: str = Depends(oauth2_scheme)):
#     try:
#         jwks = get_jwks()
#         unverified_header = jwt.get_unverified_header(token)
#         for key in jwks["keys"]:
#             if key["kid"] == unverified_header["kid"]:
#                 public_key = jwt.construct_rsa_public_key(key)
#                 payload = jwt.decode(token, public_key, algorithms=[key["alg"]], audience=CLIENT_ID)
#                 # Validar grupo
#                 groups = payload.get('groups', [])
#                 if ALLOWED_GROUP_ID and ALLOWED_GROUP_ID not in groups:
#                     raise HTTPException(status_code=403, detail="Usuario no autorizado (grupo)")
#                 return payload
#         raise HTTPException(status_code=401, detail="No se pudo validar el token")
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Token inválido")


# # --- ENDPOINTS GET PARA FACTURAS Y MENSAJES ---
# @app.get("/facturas/", response_model=list[FacturaOut])
# def listar_facturas():
#     db = get_db()  # No usar el wrapper de parámetros para evitar problemas de conexión, crear uno nuevo directamente
#     rows = db.fetchall('SELECT id, message_id, rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion, razon_social_emisor, estado_envio, mensaje_error, fecha FROM facturas ORDER BY fecha DESC')
#     return [
#         FacturaOut(
#             id=row[0],
#             message_id=row[1],
#             rncemisor=row[2],
#             rnccomprador=row[3],
#             ncfelectronico=row[4],
#             fechaemision=row[5],
#             montototal=row[6],
#             fechafirma=row[7],
#             codigoseguridad=row[8],
#             estado=row[9],
#             url_validacion=row[10],
#             razon_social_emisor=row[11],
#             estado_envio=row[12],
#             mensaje_error=row[13],
#             fecha=row[14],
#         ) for row in rows
#     ]

# @app.get("/parametros/", response_model=list[ParametroOut])
# def listar_parametros(parametros: ParametrosManager = Depends(get_parametros_manager)):
#     rows = parametros.all()
#     return [
#         ParametroOut(
#             clave=row[0],
#             valor=row[1],
#             descripcion=row[2],
#             ultima_actualizacion=row[3],
#         )
#         for row in rows
#     ]

# @app.get("/parametros/{clave}", response_model=ParametroOut)
# def obtener_parametro(clave: str, parametros: ParametrosManager = Depends(get_parametros_manager)):
#     row = parametros.get(clave, return_full=True)
#     if row is None:
#         raise HTTPException(status_code=404, detail="Parámetro no encontrado")
#     return ParametroOut(
#         clave=row[0],
#         valor=row[1],
#         descripcion=row[2],
#         ultima_actualizacion=row[3],
#     )

# @app.post("/parametros/{clave}", response_model=ParametroOut)
# def actualizar_parametro(clave: str, body: ParametroIn, parametros: ParametrosManager = Depends(get_parametros_manager)):
#     parametros.set(clave, body.valor, body.descripcion)
#     # Buscar el registro actualizado
#     row = parametros.get(clave, return_full=True)
#     return ParametroOut(
#         clave=row[0],
#         valor=row[1],
#         descripcion=row[2],
#         ultima_actualizacion=row[3],
#     )
