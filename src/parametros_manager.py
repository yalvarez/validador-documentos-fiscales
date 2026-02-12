class ParametrosManager:
    def __init__(self, db_wrapper):
        self.db = db_wrapper

    def get(self, clave, default=None):
        valor = self.db.get_param(clave)
        return valor if valor is not None else default

    def set(self, clave, valor, descripcion=None):
        self.db.set_param(clave, valor, descripcion)

    def all(self):
        return self.db.get_all_params()
