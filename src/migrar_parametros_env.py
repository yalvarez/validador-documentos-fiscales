import os
from dotenv import load_dotenv
from db.db_factory import get_db_wrapper

def migrate_env_params_to_db():
    load_dotenv()
    # Configuración de base de datos
    db_engine = os.getenv('DB_ENGINE', 'sqlite')
    db_conn_str = os.getenv('DB_CONNECTION_STRING', './validador.db')
    if db_engine == 'sqlite':
        db_config = {'db_path': db_conn_str}
    elif db_engine == 'mysql':
        db_config = db_conn_str  # Ajusta según tu factory
    elif db_engine == 'sqlserver':
        db_config = db_conn_str
    else:
        raise ValueError('DB_ENGINE no soportado')
    db = get_db_wrapper(db_engine, db_config)

    # Lista de claves a migrar (ajusta según tus necesidades)
    claves = [
        'O365_CLIENT_ID', 'O365_CLIENT_SECRET',
        'EMAIL_PROVIDER', 'EMAIL_USER', 'EMAIL_PASS',
        'ATTACHMENTS_DIR', 'LOG_FILE',
        'API_URL', 'API_KEY',
        'CHECK_INTERVAL', 'MAILBOX_FOLDER'
    ]
    for clave in claves:
        valor = os.getenv(clave)
        if valor is not None and db.get_param(clave) is None:
            db.set_param(clave, valor, descripcion=f'Parametro migrado desde .env')
            print(f'Parametro migrado: {clave}')
        else:
            print(f'Parametro ya existe o no definido: {clave}')

if __name__ == '__main__':
    migrate_env_params_to_db()
