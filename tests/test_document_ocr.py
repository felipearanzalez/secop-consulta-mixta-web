"""Lectura OCR real de una pagina de prueba; no contiene documentos institucionales."""
import io
import shutil
import subprocess
import unittest
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from index28.evidence import inspect_pdf


class OCRTests(unittest.TestCase):
    def test_scanned_spanish_page_retains_nit_and_ocr_method(self):
        if not shutil.which("tesseract") or not shutil.which("pdftoppm"):
            self.skipTest("Faltan herramientas OCR")
        langs=subprocess.run(["tesseract","--list-langs"],capture_output=True,text=True,timeout=5)
        if "spa" not in langs.stdout.splitlines():
            self.skipTest("Falta modelo OCR espanol")
        image=Image.new("RGB",(1700,900),"white")
        draw=ImageDraw.Draw(image)
        font=ImageFont.truetype("DejaVuSans.ttf",42)
        for n,line in enumerate(["CONSORCIO PRUEBA","Integrantes y participacion",
                                "EMPRESA UNO NIT 900.317.964-1 40 %"]):
            draw.text((80,80+90*n),line,fill="black",font=font)
        blob=io.BytesIO();c=Canvas(blob,pagesize=(850,450))
        c.drawImage(ImageReader(image),0,0,850,450);c.showPage();c.save()
        parsed=inspect_pdf(blob.getvalue(),source="ps88-5e3v",process_ref="26-11-14749233",
            process_url="https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia=26-11-14749233",
            document_url="https://www.contratos.gov.co/archivos/PROCESO_26-11-14749233_123.pdf",use_ocr=True)
        self.assertEqual(parsed["ocr_pages"],[1])
        self.assertEqual(parsed["unreadable_pages"],[])
        self.assertTrue(any(h["nit"]=="900317964" and h["method"]=="ocr" for h in parsed["indicators"]))
        self.assertFalse(parsed["contract_verified"])
        self.assertFalse(parsed["binary_persisted"])


if __name__=="__main__":unittest.main()
