import mysql.connector
from .base_db_wrapper import BaseDBWrapper

class MySQLDBWrapper(BaseDBWrapper):
    def is_message_processed(self, message_id):
        cur = self.conn.cursor()
        cur.execute('SELECT 1 FROM mensajes_recibidos WHERE message_id = %s', (message_id,))
        return cur.fetchone() is not None
    def __init__(self, config):
        self.conn = mysql.connector.connect(**config)
        self.create_facturas_table()
        self.create_mensajes_table()
        self.create_parametros_table()

    def execute(self, query, params=None):
        cur = self.conn.cursor()
        cur.execute(query, params or [])
        self.conn.commit()
        return cur

    def fetchall(self, query, params=None):
        cur = self.conn.cursor()
        cur.execute(query, params or [])
        return cur.fetchall()

    def insert_factura(self, factura_dict, estado):
        self.conn.cursor().execute('''
            INSERT INTO facturas (
                message_id, rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            factura_dict.get('message_id'),
            factura_dict.get('rncemisor'),
            factura_dict.get('rnccomprador'),
            factura_dict.get('ncfelectronico'),
            factura_dict.get('fechaemision'),
            factura_dict.get('montototal'),
            factura_dict.get('fechafirma'),
            factura_dict.get('codigoseguridad'),
            estado,
            factura_dict.get('url_validacion')
        ))
        self.conn.commit()

    def insert_mensaje(self, message_id, remitente, asunto):
        self.conn.cursor().execute('''
            INSERT INTO mensajes_recibidos (message_id, remitente, asunto)
            VALUES (%s, %s, %s)
        ''', (message_id, remitente, asunto))
        self.conn.commit()

    def update_factura_estado(self, message_id, nuevo_estado):
        self.conn.cursor().execute('''
            UPDATE facturas SET estado = %s, fecha = CURRENT_TIMESTAMP WHERE message_id = %s
        ''', (nuevo_estado, message_id))
        self.conn.commit()

    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        self.conn.cursor().execute('''
            UPDATE facturas SET estado_envio = %s, mensaje_error = %s, fecha = CURRENT_TIMESTAMP WHERE message_id = %s
        ''', (estado_envio, mensaje_error, message_id))
        self.conn.commit()

    def create_facturas_table(self):
        self.conn.cursor().execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id VARCHAR(255),
                rncemisor VARCHAR(255),
                rnccomprador VARCHAR(255),
                ncfelectronico VARCHAR(255),
                fechaemision VARCHAR(255),
                montototal VARCHAR(255),
                fechafirma VARCHAR(255),
                codigoseguridad VARCHAR(255),
                estado VARCHAR(255),
                url_validacion VARCHAR(255),
                estado_envio VARCHAR(32) DEFAULT 'NO ENVIADO',
                mensaje_error TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_mensajes_table(self):
        self.conn.cursor().execute('''
            CREATE TABLE IF NOT EXISTS mensajes_recibidos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id VARCHAR(255),
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remitente VARCHAR(255),
                asunto VARCHAR(255)
            )
        ''')
        self.conn.commit()

    def create_parametros_table(self):
        self.conn.cursor().execute('''
            CREATE TABLE IF NOT EXISTS parametros (
                id INT AUTO_INCREMENT PRIMARY KEY,
                clave VARCHAR(255) UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                descripcion TEXT,
                ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def get_param(self, clave):
        cur = self.conn.cursor()
        cur.execute('SELECT valor FROM parametros WHERE clave = %s', (clave,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_param(self, clave, valor, descripcion=None):
        self.conn.cursor().execute('''
            INSERT INTO parametros (clave, valor, descripcion, ultima_actualizacion)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE valor=VALUES(valor), descripcion=VALUES(descripcion), ultima_actualizacion=CURRENT_TIMESTAMP
        ''', (clave, valor, descripcion))
        self.conn.commit()

    def get_all_params(self):
        cur = self.conn.cursor()
        cur.execute('SELECT clave, valor, descripcion, ultima_actualizacion FROM parametros')
        return cur.fetchall()
