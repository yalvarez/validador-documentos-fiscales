
import os
import requests
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
from api.schemas import ParametroOut, ParametroIn, FacturaOut, MensajeOut
from api.parametros_manager import ParametrosManager
from db.db_factory import get_db_wrapper
from dotenv import load_dotenv
from jose import jwt, JWTError
from ldap3 import Server, Connection, ALL, NTLM

load_dotenv()

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

@app.get("/mensajes/", response_model=list[MensajeOut])
def listar_mensajes():
    db = get_db()  # No usar el wrapper de parámetros para evitar problemas de conexión, crear uno nuevo directamente
    rows = db.fetchall('SELECT id, message_id, fecha, remitente, asunto FROM mensajes_recibidos ORDER BY fecha DESC')
    return [
        MensajeOut(
            id=row[0],
            message_id=row[1],
            fecha=row[2],
            remitente=row[3],
            asunto=row[4],
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
