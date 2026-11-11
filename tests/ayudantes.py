from datetime import datetime, timedelta, timezone
from pathlib import Path

# Se moverá a common.ecf.modelos en la Tarea 2.
ZONA_RD = timezone(timedelta(hours=-4))

RAIZ = Path(__file__).parents[1]
MUESTRA_XML = (RAIZ / 'tests/samples/101616202E310000002882.xml').read_bytes()
MUESTRA_PDF = RAIZ / 'tests/samples/101616202E310000002882.pdf'
T0 = datetime(2026, 11, 10, 10, 0, tzinfo=ZONA_RD)
