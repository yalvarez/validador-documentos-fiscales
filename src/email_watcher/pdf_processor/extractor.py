import pdfplumber
from PIL import Image
from pyzbar.pyzbar import decode
import io
import re

import urllib.parse

class PDFProcessor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
    def extract_qr_params(self) -> dict:
        """
        Extrae los parámetros de la URL del QR (usualmente contiene rncemisor, ncfelectronico, rnccomprador, codigoseguridad).
        """
        url = self.extract_qr_url()
        if not url:
            return {}
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        # Convertir valores de lista a string
        return {k: v[0] for k, v in params.items()}


    def extract_qr_url(self, save_qr_image=False, qr_image_path=None, logger=None):
        """Extrae la URL del QR en el PDF (si existe). Si save_qr_image=True, guarda la imagen del QR extraído."""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                im = page.to_image(resolution=300)
                pil_img = im.original
                decoded_objs = decode(pil_img)
                if logger:
                    logger.info(f"Página {page_num+1}: {len(decoded_objs)} códigos QR detectados.")
                for idx, obj in enumerate(decoded_objs):
                    data = obj.data.decode('utf-8')
                    if logger:
                        logger.info(f"QR #{idx+1} longitud de datos extraídos: {len(data)}")
                    if save_qr_image and qr_image_path:
                        # Guardar la imagen del QR extraído
                        qr_img = obj.rect
                        qr_crop = pil_img.crop((qr_img.left, qr_img.top, qr_img.left+qr_img.width, qr_img.top+qr_img.height))
                        qr_crop.save(qr_image_path)
                        if logger:
                            logger.info(f"Imagen del QR guardada en: {qr_image_path}")
                    if data.startswith('http'):
                        return data
        return None

    def _extract_url(self, text: str) -> str:
        match = re.search(r'https?://[\w\-\.\?&=/%]+', text)
        def extract_qr_url(self, save_qr_image=False, qr_image_path=None, logger=None):
            """Extrae la URL del QR en el PDF (si existe). Si save_qr_image=True, guarda la imagen del QR extraído."""
            for page_num, page in enumerate(self.pdf.pages):
                im = page.to_image(resolution=300)
                pil_img = im.original
                decoded_objs = decode(pil_img)
                if logger:
                    logger.info(f"Página {page_num+1}: {len(decoded_objs)} códigos QR detectados.")
                for idx, obj in enumerate(decoded_objs):
                    data = obj.data.decode('utf-8')
                    if logger:
                        logger.info(f"QR #{idx+1} longitud de datos extraídos: {len(data)}")
                    if save_qr_image and qr_image_path:
                        # Guardar la imagen del QR extraído
                        qr_img = obj.rect
                        qr_crop = pil_img.crop((qr_img.left, qr_img.top, qr_img.left+qr_img.width, qr_img.top+qr_img.height))
                        qr_crop.save(qr_image_path)
                        if logger:
                            logger.info(f"Imagen del QR guardada en: {qr_image_path}")
                    if data.startswith('http'):
                        return data
            return None
