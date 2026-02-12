import pyodbc
from .base_db_wrapper import BaseDBWrapper

class SQLServerDBWrapper(BaseDBWrapper):
    def is_message_processed(self, message_id):
        cur = self.conn.cursor()
        cur.execute('SELECT 1 FROM mensajes_recibidos WHERE message_id = ?', (message_id,))
        return cur.fetchone() is not None
    def __init__(self, config):
        self.conn = pyodbc.connect(**config)
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            VALUES (?, ?, ?)
        ''', (message_id, remitente, asunto))
        self.conn.commit()

    def update_factura_estado(self, message_id, nuevo_estado):
        self.conn.cursor().execute('''
            UPDATE facturas SET estado = ?, fecha = CURRENT_TIMESTAMP WHERE message_id = ?
        ''', (nuevo_estado, message_id))
        self.conn.commit()

    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        self.conn.cursor().execute('''
            UPDATE facturas SET estado_envio = ?, mensaje_error = ?, fecha = CURRENT_TIMESTAMP WHERE message_id = ?
        ''', (estado_envio, mensaje_error, message_id))
        self.conn.commit()

    def create_facturas_table(self):
        self.conn.cursor().execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='facturas' AND xtype='U')
            CREATE TABLE facturas (
                id INT IDENTITY(1,1) PRIMARY KEY,
                message_id NVARCHAR(255),
                rncemisor NVARCHAR(255),
                rnccomprador NVARCHAR(255),
                ncfelectronico NVARCHAR(255),
                fechaemision NVARCHAR(255),
                montototal NVARCHAR(255),
                fechafirma NVARCHAR(255),
                codigoseguridad NVARCHAR(255),
                estado NVARCHAR(255),
                url_validacion NVARCHAR(255),
                estado_envio NVARCHAR(32) DEFAULT 'NO ENVIADO',
                mensaje_error NVARCHAR(MAX),
                fecha DATETIME DEFAULT GETDATE()
            )
        ''')
        self.conn.commit()

    def create_mensajes_table(self):
        self.conn.cursor().execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='mensajes_recibidos' AND xtype='U')
            CREATE TABLE mensajes_recibidos (
                id INT IDENTITY(1,1) PRIMARY KEY,
                message_id NVARCHAR(255),
                fecha DATETIME DEFAULT GETDATE(),
                remitente NVARCHAR(255),
                asunto NVARCHAR(255)
            )
        ''')
        self.conn.commit()

    def create_parametros_table(self):
        self.conn.cursor().execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='parametros' AND xtype='U')
            CREATE TABLE parametros (
                id INT IDENTITY(1,1) PRIMARY KEY,
                clave NVARCHAR(255) UNIQUE NOT NULL,
                valor NVARCHAR(MAX) NOT NULL,
                descripcion NVARCHAR(MAX),
                ultima_actualizacion DATETIME DEFAULT GETDATE()
            )
        ''')
        self.conn.commit()

    def get_param(self, clave):
        cur = self.conn.cursor()
        cur.execute('SELECT valor FROM parametros WHERE clave = ?', (clave,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_param(self, clave, valor, descripcion=None):
        cur = self.conn.cursor()
        # UPSERT para SQL Server
        cur.execute('''
            MERGE parametros AS target
            USING (SELECT ? AS clave) AS source
            ON (target.clave = source.clave)
            WHEN MATCHED THEN
                UPDATE SET valor = ?, descripcion = ?, ultima_actualizacion = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (clave, valor, descripcion, ultima_actualizacion)
                VALUES (?, ?, ?, GETDATE());
        ''', (clave, valor, descripcion, clave, valor, descripcion))
        self.conn.commit()

    def get_all_params(self):
        cur = self.conn.cursor()
        cur.execute('SELECT clave, valor, descripcion, ultima_actualizacion FROM parametros')
        return cur.fetchall()
