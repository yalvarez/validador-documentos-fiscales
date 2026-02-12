from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2AuthorizationCodeBearer
from parametros_manager import ParametrosManager
from db.db_factory import get_db_wrapper
import os
from dotenv import load_dotenv
from jose import jwt, JWTError
from ldap3 import Server, Connection, ALL, NTLM
import requests

app = FastAPI()
security = HTTPBasic()

# Configuración Entra ID (Azure AD)
TENANT_ID = os.getenv('AZURE_TENANT_ID')
CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
JWKS_URL = f"{AUTHORITY}/discovery/v2.0/keys"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{AUTHORITY}/oauth2/v2.0/authorize",
    tokenUrl=f"{AUTHORITY}/oauth2/v2.0/token",
    scopes={"openid": "OpenID Connect scope"}
)

# Cargar configuración y base de datos
load_dotenv()
db_engine = os.getenv('DB_ENGINE', 'sqlite')
db_conn_str = os.getenv('DB_CONNECTION_STRING', './validador.db')
if db_engine == 'sqlite':
    db_config = {'db_path': db_conn_str}
elif db_engine == 'mysql':
    db_config = db_conn_str
elif db_engine == 'sqlserver':
    db_config = db_conn_str
else:
    raise ValueError('DB_ENGINE no soportado')
db = get_db_wrapper(db_engine, db_config)
parametros = ParametrosManager(db)

# Grupo permitido (Object ID del grupo de Azure AD)
ALLOWED_GROUP_ID = os.getenv('AZURE_ALLOWED_GROUP_ID')

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

@app.get("/parametros/")
def listar_parametros(user: str = Depends(get_current_user)):
    return parametros.all()

@app.get("/parametros/{clave}")
def obtener_parametro(clave: str, user: str = Depends(get_current_user)):
    valor = parametros.get(clave)
    if valor is None:
        raise HTTPException(status_code=404, detail="Parámetro no encontrado")
    return {"clave": clave, "valor": valor}

@app.post("/parametros/{clave}")
def actualizar_parametro(clave: str, valor: str, descripcion: str = None, user: str = Depends(get_current_user)):
    parametros.set(clave, valor, descripcion)
    return {"clave": clave, "valor": valor, "descripcion": descripcion}
