import sqlite3
from .base_db_wrapper import BaseDBWrapper

class SQLiteDBWrapper(BaseDBWrapper):
    def is_message_processed(self, message_id):
        cur = self.conn.execute('SELECT 1 FROM mensajes_recibidos WHERE message_id = ?', (message_id,))
        return cur.fetchone() is not None
    def __init__(self, db_path, conn=None):
        if conn is not None:
            self.conn = conn
        else:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
        self.conn.execute('''
            INSERT INTO facturas (
                message_id, rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion, razon_social_emisor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            factura_dict.get('url_validacion'),
            factura_dict.get('razon_social_emisor')
        ))
        self.conn.commit()

    def insert_mensaje(self, message_id, remitente, asunto):
        self.conn.execute('''
            INSERT INTO mensajes_recibidos (message_id, remitente, asunto)
            VALUES (?, ?, ?)
        ''', (message_id, remitente, asunto))
        self.conn.commit()

    def update_factura_estado(self, message_id, nuevo_estado):
        self.conn.execute('''
            UPDATE facturas SET estado = ?, fecha = CURRENT_TIMESTAMP WHERE message_id = ?
        ''', (nuevo_estado, message_id))
        self.conn.commit()

    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        self.conn.execute('''
            UPDATE facturas SET estado_envio = ?, mensaje_error = ?, fecha = CURRENT_TIMESTAMP WHERE message_id = ?
        ''', (estado_envio, mensaje_error, message_id))
        self.conn.commit()

    def create_facturas_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                rncemisor TEXT,
                rnccomprador TEXT,
                ncfelectronico TEXT,
                fechaemision TEXT,
                montototal TEXT,
                fechafirma TEXT,
                codigoseguridad TEXT,
                estado TEXT,
                url_validacion TEXT,
                razon_social_emisor TEXT,
                estado_envio TEXT DEFAULT 'NO ENVIADO',
                mensaje_error TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_mensajes_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_recibidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remitente TEXT,
                asunto TEXT
            )
        ''')
        self.conn.commit()

    def create_parametros_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS parametros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                descripcion TEXT,
                ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def get_param(self, clave):
        cur = self.conn.execute('SELECT valor FROM parametros WHERE clave = ?', (clave,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_param(self, clave, valor, descripcion=None):
        self.conn.execute('''
            INSERT INTO parametros (clave, valor, descripcion, ultima_actualizacion)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor, descripcion=excluded.descripcion, ultima_actualizacion=CURRENT_TIMESTAMP
        ''', (clave, valor, descripcion))
        self.conn.commit()

    def get_all_params(self):
        cur = self.conn.execute('SELECT clave, valor, descripcion, ultima_actualizacion FROM parametros')
        return cur.fetchall()
