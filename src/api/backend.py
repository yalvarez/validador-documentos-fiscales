import os
import requests
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Header
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
from api.schemas import ParametroOut, ParametroIn, FacturaOut, MensajeOut
from api.parametros_manager import ParametrosManager
from db.db_factory import get_db_wrapper
from dotenv import load_dotenv
from jose import jwt, JWTError
from ldap3 import Server, Connection, ALL, NTLM
from common.pdf_processor.extractor import PDFProcessor
from common.validator.web_validator import WebValidator
import tempfile

load_dotenv()

API_KEYS = [k.strip() for k in os.getenv('API_KEYS', 'YomxbA2xGssmMF2xPmyrgsdxEHROstMP').split(',') if k.strip()]
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite')
DB_CONN_STR = os.getenv('DB_CONNECTION_STRING', './db.sqlite3')

app = FastAPI()
    
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
    db_config = {'db_path': DB_CONN_STR} if DB_ENGINE == 'sqlite' else DB_CONN_STR
    return get_db_wrapper(DB_ENGINE, db_config)

def get_parametros_manager():    
    return ParametrosManager(get_db())

# Configuración Entra ID (Azure AD)
TENANT_ID = get_parametros_manager().get('AZURE_TENANT_ID')
CLIENT_ID = get_parametros_manager().get('AZURE_CLIENT_ID')
ALLOWED_GROUP_ID = get_parametros_manager().get('AZURE_ALLOWED_GROUP_ID')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
JWKS_URL = f"{AUTHORITY}/discovery/v2.0/keys"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{AUTHORITY}/oauth2/v2.0/authorize",
    tokenUrl=f"{AUTHORITY}/oauth2/v2.0/token",
    scopes={"openid": "OpenID Connect scope"}
)

def get_jwks():
    resp = requests.get(JWKS_URL)
    resp.raise_for_status()
    return resp.json()

from api.schemas import ValidacionFacturaOut, ValidarFacturaIn, ConsultaFacturaParamsIn

# Nuevo endpoint: consulta por parámetros de URL del PDF
@app.post("/consulta-factura-params", response_model=ValidacionFacturaOut)
def consulta_factura_params(
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

@app.post("/validar-pdf", response_model=ValidacionFacturaOut)
async def validar_pdf(
    file: UploadFile = File(...),
    rnc_emisor: str = None,
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
    db = get_db()
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
    
    db.insert_factura(factura_dict)

    return ValidacionFacturaOut(
        rnc_emisor=factura_dict['rncemisor'],
        razon_social_emisor=factura_dict['razon_social_emisor'],
        estado=factura_dict['estado']
    )

# --- ENDPOINTS GET PARA FACTURAS Y MENSAJES ---
@app.get("/facturas/", response_model=list[FacturaOut])
def listar_facturas():
    db = get_db()  # No usar el wrapper de parámetros para evitar problemas de conexión, crear uno nuevo directamente
    rows = db.fetchall('SELECT id, message_id, rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion, razon_social_emisor, estado_envio, mensaje_error, fecha FROM facturas ORDER BY fecha DESC')
    return [
        FacturaOut(
            id=row[0],
            message_id=row[1],
            rncemisor=row[2],
            rnccomprador=row[3],
            ncfelectronico=row[4],
            fechaemision=row[5],
            montototal=row[6],
            fechafirma=row[7],
            codigoseguridad=row[8],
            estado=row[9],
            url_validacion=row[10],
            razon_social_emisor=row[11],
            estado_envio=row[12],
            mensaje_error=row[13],
            fecha=row[14],
        ) for row in rows
    ]

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                public_key = jwt.construct_rsa_public_key(key)
                payload = jwt.decode(token, public_key, algorithms=[key["alg"]], audience=CLIENT_ID)
                # Validar grupo
                groups = payload.get('groups', [])
                if ALLOWED_GROUP_ID and ALLOWED_GROUP_ID not in groups:
                    raise HTTPException(status_code=403, detail="Usuario no autorizado (grupo)")
                return payload
        raise HTTPException(status_code=401, detail="No se pudo validar el token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

@app.get("/parametros/", response_model=list[ParametroOut])
def listar_parametros(parametros: ParametrosManager = Depends(get_parametros_manager)):
    rows = parametros.all()
    return [
        ParametroOut(
            clave=row[0],
            valor=row[1],
            descripcion=row[2],
            ultima_actualizacion=row[3],
        )
        for row in rows
    ]

@app.get("/parametros/{clave}", response_model=ParametroOut)
def obtener_parametro(clave: str, parametros: ParametrosManager = Depends(get_parametros_manager)):
    row = parametros.get(clave, return_full=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Parámetro no encontrado")
    return ParametroOut(
        clave=row[0],
        valor=row[1],
        descripcion=row[2],
        ultima_actualizacion=row[3],
    )

@app.post("/parametros/{clave}", response_model=ParametroOut)
def actualizar_parametro(clave: str, body: ParametroIn, parametros: ParametrosManager = Depends(get_parametros_manager)):
    parametros.set(clave, body.valor, body.descripcion)
    # Buscar el registro actualizado
    row = parametros.get(clave, return_full=True)
    return ParametroOut(
        clave=row[0],
        valor=row[1],
        descripcion=row[2],
        ultima_actualizacion=row[3],
    )
