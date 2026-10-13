import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from reportlab.pdfgen import canvas
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import institutional_indexer as I

ASO_LIST='''<html><body><table><tr><th>Referencia</th></tr>
<tr><td>LP-005-2026</td><td>Proceso Adjudicado y Celebrado</td><td><a href="/proceso/view?id=d6062d1347c211f188ebfa163e75d6de">Ver</a></td></tr>
<tr><td>LP-999-2026</td><td><a href="https://bad.example/proceso/view?id=bad">Ver</a></td></tr>
</table></body></html>'''.encode()
ASO_DETAIL='''<html><body><h2>Número del Proceso LP-005-2026</h2>
<table><tr><td>20. INFORME FINAL.pdf</td><td><a href="/documents/dl?file=informe-final.pdf">Descargar</a></td></tr>
<tr><td>22. AUDIENCIA ADJUDICACION.pdf</td><td><a href="https://bad.example/secret.pdf">Descargar</a></td></tr>
<tr><td>21. CONTRATO 003 DE 2026.pdf</td><td><a href="/documents/dl?file=contrato.pdf">Descargar</a></td></tr>
</table></body></html>'''.encode()
FINDETER='''<table><tbody><tr><td><a href="/convocatorias/paf-obra-2026">PAF-ATMINDEPORTE-O-052-2026</a></td><td>Celebrado</td><td>Obra</td></tr></tbody></table>'''.encode()


def pdf():
    content=io.BytesIO()
    c=canvas.Canvas(content)
    c.drawString(60,760,'CONSORCIO RIO NIT 901.885.583-8 Participante PRUEBA')
    c.drawString(60,740,'NIT 800.143.586-1 Representante en acta')
    c.save()
    return content.getvalue()


class IndexerTest(unittest.TestCase):
    def test_allowed(self):
        self.assertTrue(I.allowed('https://www.findeter.gov.co/convocatorias','findeter'))
        self.assertTrue(I.allowed('https://contratacion.asosupro.gov.co/proceso/view?id=a','asosupro'))
        self.assertFalse(I.allowed('http://www.findeter.gov.co/convocatorias','findeter'))
        self.assertFalse(I.allowed('https://findeter.gov.co.evil.test/process','findeter'))
        self.assertFalse(I.allowed('https://127.0.0.1:8000/','findeter'))
        self.assertFalse(I.allowed('https://contratacion.asosupro.gov.co@evil.test/','asosupro'))

    def test_listings(self):
        results=I.listing('asosupro',ASO_LIST,I.SOURCE_URLS['asosupro'])
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['reference'],'LP-005-2026')
        self.assertEqual(len(I.listing('findeter',FINDETER,I.SOURCE_URLS['findeter'])),1)

    def test_document_selection(self):
        found=I.documents('asosupro',ASO_DETAIL,'https://contratacion.asosupro.gov.co/proceso/view?id=abcdef1234567',4)
        self.assertEqual(len(found),2)
        self.assertTrue(all('asosupro.gov.co' in x['url'] for x in found))

    def test_pdf_extracts_evidence_but_not_membership(self):
        findings=I.pdf_identifiers(pdf())
        self.assertEqual({x['nit'] for x in findings},{'901885583','800143586'})
        self.assertTrue(all(x['association']=='INDICIO SIN VERIFICAR' for x in findings))

    def test_independent_crawl_and_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=I.connect_db(str(Path(tmp)/'evidence.db'))
            calls=[]
            def fetch(url,source):
                calls.append(url)
                if url.endswith('page=0'):
                    return ASO_LIST,'text/html'
                if '/proceso/view?' in url:
                    return ASO_DETAIL,'text/html'
                if '/documents/dl?' in url:
                    return pdf(),'application/pdf'
                raise ValueError('unexpected URL')
            stats=I.crawl(db,'asosupro',1,2,fetcher=fetch,pause=0)
            self.assertEqual(stats['errors'],0)
            self.assertEqual(stats['processes_indexed'],1)
            self.assertEqual(stats['documents_extracted'],2)
            self.assertEqual(stats['evidence_indicators'],4)
            entries=I.lookup(db,'901885583-8')
            self.assertEqual(len(entries),2)
            self.assertTrue(all('view?id=' in e['process_url'] for e in entries))
            self.assertTrue(all(e['association']=='INDICIO SIN VERIFICAR' for e in entries))
            # Crawling again within one day reuses documents: no new PDF downloads.
            count_before=len([x for x in calls if '/documents/dl?' in x])
            again=I.crawl(db,'asosupro',1,2,fetcher=fetch,pause=0)
            self.assertEqual(again['documents_extracted'],0)
            self.assertEqual(len([x for x in calls if '/documents/dl?' in x]),count_before)
            db.close()

if __name__=='__main__': unittest.main()
