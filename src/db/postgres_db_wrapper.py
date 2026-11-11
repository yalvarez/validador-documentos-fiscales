import psycopg
from .base_db_wrapper import BaseDBWrapper


class PostgresDBWrapper(BaseDBWrapper):
    def __init__(self, conn_str):
        self.conn = psycopg.connect(conn_str, autocommit=True)
        # La API y el worker pueden arrancar a la vez: CREATE TABLE IF NOT EXISTS
        # concurrente puede lanzar UniqueViolation; se reintenta.
        for intento in range(3):
            try:
                self.create_facturas_table()
                self.create_mensajes_table()
                self.create_parametros_table()
                break
            except psycopg.errors.UniqueViolation:
                if intento == 2:
                    raise

    def close(self):
        self.conn.close()

    def execute(self, query, params=None):
        cur = self.conn.cursor()
        cur.execute(query, params or None)
        return cur

    def fetchall(self, query, params=None):
        cur = self.conn.cursor()
        cur.execute(query, params or None)
        return cur.fetchall()

    def is_message_processed(self, message_id):
        cur = self.conn.execute('SELECT 1 FROM mensajes_recibidos WHERE message_id = %s', (message_id,))
        return cur.fetchone() is not None

    def insert_factura(self, factura_dict):
        self.conn.execute('''
            INSERT INTO facturas (
                rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion, razon_social_emisor
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            factura_dict.get('rncemisor'),
            factura_dict.get('rnccomprador'),
            factura_dict.get('ncfelectronico'),
            factura_dict.get('fechaemision'),
            factura_dict.get('montototal'),
            factura_dict.get('fechafirma'),
            factura_dict.get('codigoseguridad'),
            factura_dict.get('estado'),
            factura_dict.get('url_validacion'),
            factura_dict.get('razon_social_emisor'),
        ))

    def insert_mensaje(self, message_id, remitente, asunto):
        self.conn.execute('''
            INSERT INTO mensajes_recibidos (message_id, remitente, asunto)
            VALUES (%s, %s, %s)
        ''', (message_id, remitente, asunto))

    def update_factura_estado(self, message_id, nuevo_estado):
        self.conn.execute('''
            UPDATE facturas SET estado = %s, fecha = CURRENT_TIMESTAMP WHERE message_id = %s
        ''', (nuevo_estado, message_id))

    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        self.conn.execute('''
            UPDATE facturas SET estado_envio = %s, mensaje_error = %s, fecha = CURRENT_TIMESTAMP WHERE message_id = %s
        ''', (estado_envio, mensaje_error, message_id))

    def create_facturas_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id BIGSERIAL PRIMARY KEY,
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
                fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def create_mensajes_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_recibidos (
                id BIGSERIAL PRIMARY KEY,
                message_id TEXT,
                fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                remitente TEXT,
                asunto TEXT
            )
        ''')

    def create_parametros_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS parametros (
                id BIGSERIAL PRIMARY KEY,
                clave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                descripcion TEXT,
                ultima_actualizacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def get_param(self, clave):
        cur = self.conn.execute('SELECT valor FROM parametros WHERE clave = %s', (clave,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_param(self, clave, valor, descripcion=None):
        self.conn.execute('''
            INSERT INTO parametros (clave, valor, descripcion, ultima_actualizacion)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, descripcion = EXCLUDED.descripcion, ultima_actualizacion = CURRENT_TIMESTAMP
        ''', (clave, valor, descripcion))

    def get_all_params(self):
        cur = self.conn.execute('SELECT clave, valor, descripcion, ultima_actualizacion FROM parametros')
        return cur.fetchall()
