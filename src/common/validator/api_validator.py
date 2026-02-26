import requests

class APIValidator:
    def __init__(self, api_url, params):
        self.api_url = api_url
        self.params = params

    def validate(self) -> str:
        resp = requests.get(self.api_url, params=self.params)
        if resp.status_code != 200:
            return 'No válido (error de API)'
        data = resp.json()
        # Ajustar según respuesta de la API
        if data.get('valido'):
            return 'Válido'
        return 'No válido'
