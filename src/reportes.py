import requests
from bs4 import BeautifulSoup
import json

def extraer_estado_ncf(html):
    soup = BeautifulSoup(html, 'html.parser')
    for row in soup.find_all('tr'):
        th = row.find('th')
        if th and 'Estado' in th.text:
            td = row.find('td')
            if td:
                return td.text.strip()
    return None

def validar_ncf_por_url(url):
    response = requests.get(url)
    estado = extraer_estado_ncf(response.text)
    resultado = {
        'url': url,
        'estado': estado
    }
    return json.dumps(resultado, ensure_ascii=False, indent=2)

# Ejemplo de uso:
# url = 'https://ecf.dgii.gov.do/eCF/ConsultaTimbre?RncEmisor=101616202&RncComprador=101107146&ENCF=E310000002882&FechaEmision=10-02-2026&MontoTotal=1250.00&FechaFirma=10-02-2026%2009:22:21&CodigoSeguridad=BuLkvC'
# print(validar_ncf_por_url(url))
from logger.reportes import Reportes

if __name__ == "__main__":
    r = Reportes()
    print("\n--- Resumen de validaciones ---")
    r.resumen_validaciones()
    print("\n--- Últimos 20 comprobantes procesados ---")
    r.listado_validaciones()
    folio = input("\nBuscar por folio o parte de URL (dejar vacío para omitir): ")
    if folio:
        print(f"\n--- Resultados para '{folio}' ---")
        r.buscar_por_folio(folio)
