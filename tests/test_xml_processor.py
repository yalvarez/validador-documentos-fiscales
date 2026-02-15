import os
from common.xml_processor.parser import XMLProcessor

def test_parse_xml():
    xml_path = os.path.join(os.path.dirname(__file__), 'sample.xml')
    proc = XMLProcessor(xml_path)
    data = proc.parse()
    print('Datos XML:', data)
    assert isinstance(data, dict)
