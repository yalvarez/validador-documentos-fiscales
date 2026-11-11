class BaseDBWrapper:
    def connect(self):
        raise NotImplementedError
    def execute(self, query, params=None):
        raise NotImplementedError
    def fetchall(self, query, params=None):
        raise NotImplementedError
    def insert_factura(self, factura_dict):
        raise NotImplementedError
    def insert_mensaje(self, message_id, remitente, asunto):
        raise NotImplementedError
    def update_factura_estado(self, message_id, nuevo_estado):
        raise NotImplementedError
    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        raise NotImplementedError
    def create_facturas_table(self):
        raise NotImplementedError
    def create_mensajes_table(self):
        raise NotImplementedError
    def create_parametros_table(self):
        raise NotImplementedError
    def get_param(self, clave):
        raise NotImplementedError
    def set_param(self, clave, valor, descripcion=None):
        raise NotImplementedError
    def get_all_params(self):
        raise NotImplementedError
    def create_comprobantes_tables(self):
        raise NotImplementedError
    def get_comprobante(self, rnc_emisor, encf):
        raise NotImplementedError
    def get_comprobante_por_id(self, id, bloquear=False):
        raise NotImplementedError
    def insert_comprobante(self, campos):
        raise NotImplementedError
    def update_comprobante(self, id, campos):
        raise NotImplementedError
    def insert_historial(self, id, tipo, estado_anterior=None, estado_nuevo=None, estado_dgii_texto=None, detalle=None, fecha=None):
        raise NotImplementedError
    def get_historial(self, id):
        raise NotImplementedError
    def get_comprobantes_por_consultar(self, ahora, limite=100):
        raise NotImplementedError
    def transaccion(self):
        raise NotImplementedError
