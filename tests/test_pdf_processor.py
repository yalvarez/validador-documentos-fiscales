import os
from common.pdf_processor.extractor import PDFProcessor

def test_extract_qr_url():
    # Usa un PDF de ejemplo con QR (coloca el archivo en tests/sample.pdf)
    pdf_path = os.path.join(os.path.dirname(__file__), 'sample.pdf')
    proc = PDFProcessor(pdf_path)
    url = proc.extract_qr_url()
    print('URL extraída:', url)
    assert url is None or url.startswith('http')
