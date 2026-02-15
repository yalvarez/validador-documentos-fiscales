from common.validator.web_validator import WebValidator

def test_web_validator():
    # Usa una URL de ejemplo (ajusta según el sitio real)
    url = 'https://www.ejemplo.com/consulta?folio=1234'
    validator = WebValidator(url)
    resultado = validator.validate()
    print('Resultado:', resultado)
    assert resultado in ['Válido', 'No válido', 'Resultado desconocido', 'No válido (error de conexión)']
