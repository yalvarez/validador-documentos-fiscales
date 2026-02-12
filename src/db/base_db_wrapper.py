class BaseDBWrapper:
    def connect(self):
        raise NotImplementedError
    def execute(self, query, params=None):
        raise NotImplementedError
    def fetchall(self, query, params=None):
        raise NotImplementedError
    def insert_factura(self, factura_dict, estado):
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
