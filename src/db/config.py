import os


def leer_config_db():
    """Lee el motor y la conexión de la BD desde el entorno.

    Por defecto: sqlite con ./db.sqlite3 (comportamiento histórico).
    """
    motor = os.getenv('DB_ENGINE', 'sqlite')
    conexion = os.getenv('DB_CONNECTION_STRING', './db.sqlite3')
    if motor == 'sqlite':
        return motor, {'db_path': conexion}
    return motor, conexion
