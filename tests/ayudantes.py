from datetime import datetime
from pathlib import Path

from lxml import etree

from common.ecf.modelos import ZONA_RD

RAIZ = Path(__file__).parents[1]
MUESTRA_XML = (RAIZ / 'tests/samples/101616202E310000002882.xml').read_bytes()
MUESTRA_PDF = RAIZ / 'tests/samples/101616202E310000002882.pdf'
T0 = datetime(2026, 11, 10, 10, 0, tzinfo=ZONA_RD)


def _sin_firma() -> bytes:
    raiz = etree.fromstring(MUESTRA_XML)
    for nodo in raiz.xpath("//*[local-name()='Signature']"):
        nodo.getparent().remove(nodo)
    return etree.tostring(raiz)


XML_SIN_FIRMA = _sin_firma()


def muestra_en(encoding: str) -> bytes:
    """La muestra realmente codificada en `encoding`, con su declaración XML."""
    texto = MUESTRA_XML.decode('utf-8')
    return (f'<?xml version="1.0" encoding="{encoding}"?>' + texto).encode(encoding)
