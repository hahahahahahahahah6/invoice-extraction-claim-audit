"""Offline regression suite."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from invoice_extraction_claim_audit import phrases as p
from invoice_extraction_claim_audit.audit import audit, evidence, paragraphs
from invoice_extraction_claim_audit.__main__ import main

EXPECTED_POSITIVE = ('invoice extraction', 'extract invoices', 'extracts invoices', 'extracting invoices', 'extract invoice', 'extracts invoice', 'extracting invoice', 'invoice data extraction', 'extract invoice data', 'extracts invoice data', 'extracting invoice data', 'parse invoices', 'parses invoices', 'parsing invoices', 'parse invoice', 'parses invoice', 'parsing invoice', 'invoice parsing', 'invoice parser', 'invoice field extraction', 'extract invoice fields', 'extracts invoice fields', 'extracting invoice fields', 'invoice number extraction', 'extract invoice number', 'extracts invoice number', 'invoice total extraction', 'extract invoice total', 'extracts invoice total', 'invoice line item extraction', 'extract invoice line items', 'extracts invoice line items', 'extracting invoice line items', 'invoice ocr extraction', 'extract data from invoices', 'extracts data from invoices', 'extracting data from invoices', 'invoice document extraction', 'extract invoice pdf', 'extracts invoice pdf', 'invoice pdf extraction', 'process invoices', 'processes invoices', 'processing invoices', 'invoice processing', 'automated invoice processing', 'invoice automation', 'extract structured invoice data', 'extracts structured invoice data', 'invoice information extraction')
EXPECTED_NEGATIVE = ('no invoice extraction', 'does not extract invoices', 'does not extract invoice', 'does not support invoice extraction', 'without invoice extraction', 'no invoice parser', 'does not parse invoices', 'does not parse invoice', 'no invoice data extraction', 'does not extract invoice data', 'no invoice field extraction', 'does not extract invoice fields', 'invoice extraction not supported', 'no invoice processing', 'does not process invoices', 'without invoice processing', 'no invoice automation', 'does not automate invoice processing', 'does not extract invoice number', 'does not extract invoice total', 'no invoice line item extraction', 'does not extract invoice line items', 'no invoice information extraction', 'does not extract invoice information')
EXPECTED_GENERIC = ('extract_invoice', 'extract_invoices', 'parse_invoice', 'parse_invoices', 'extract_invoice_data', 'invoice_extraction', 'invoice_extractor', 'extract_invoice_fields', 'invoice_field_extraction', 'parse_invoice_data', 'invoice_parser', 'invoice_reader', 'read_invoice', 'read_invoices', 'invoice_data_extraction', 'extract_invoice_number', 'extract_invoice_total', 'invoice_number_extraction', 'invoice_total_extraction', 'extract_invoice_line_items', 'invoice_line_item_extraction', 'parse_invoice_pdf', 'extract_invoice_pdf', 'process_invoice')

POSITIVE_ROUTES = ['import invoice2data; invoice2data.extract_data(x)', 'from invoice2data import extract_data; extract_data(x)', 'from invoice2data import extract_data as e; e(x)', 'import invoice2data as i; i.extract_data(x)', 'import mindee; mindee.Client(); c.parse(InvoiceV4)', 'from mindee import Client as C; C(); c.parse(TypeInvoiceV4)', 'import mindee; mindee.Client(); c.parse(mindee.product.InvoiceV4)', 'import mindee; mindee.Client(); c.parse(product=documents.TypeInvoiceV4)', 'import veryfi; veryfi.Client(); c.process_document(x)', 'from veryfi import Client as C; C(); c.process_document_url(x)', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient(); c.begin_analyze_document("prebuilt-invoice",x)', 'from azure.ai.documentintelligence import DocumentIntelligenceClient as C; C(); c.begin_analyze_document_from_url("prebuilt-invoice",x)', 'import azure.ai.formrecognizer as a; a.DocumentAnalysisClient(); c.begin_analyze_document(model_id="prebuilt-invoice")', 'import boto3; c.analyze_expense(x)', 'from boto3 import client; c.start_expense_analysis(x)', 'from other import extract_invoice as e; f = e; f()', 'from invoice2data import extract_data; f: object = extract_data; f()']
NEGATIVE_ROUTES = ['import invoice2data', 'import mindee', 'import veryfi', 'import boto3', 'import azure.ai.formrecognizer', 'import azure.ai.documentintelligence', 'extract_data(x)', 'import mindee; mindee.Client()', 'import veryfi; veryfi.Client()', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient()', 'extract_invoice()', '"invoice extraction"', '# x.extract_invoice()', 'x.extract_invoice', 'def broken(:', 'import subprocess; subprocess.run(["invoice2data", "x"])', 'import subprocess; subprocess.run(["veryfi", "x"])', 'import re; text = page.extract_text(); fields = {"total": re.search("total", text)}', 'import mindee; mindee.Client(); c.parse(ReceiptV5)', 'import mindee; mindee.Client(); c.parse(BankCheckV1)', 'import mindee; mindee.Client(); c.parse(PassportV1)', 'import mindee; mindee.Client(); c.parse(FinancialDocumentV1)', 'import mindee; mindee.Client(); c.parse(CustomV1)', 'import mindee; mindee.Client(); c.parse(Other)', 'import veryfi; veryfi.Client(); c.process_bank_statement_document(x)', 'import veryfi; veryfi.Client(); c.classify_document(x)', 'import veryfi; veryfi.Client(); c.process_any_document(x)', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient(); c.begin_analyze_document("prebuilt-receipt")', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient(); c.begin_analyze_document("prebuilt-layout")', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient(); c.begin_analyze_document("prebuilt-read")', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient(); c.begin_analyze_document("prebuilt-idDocument")', 'import azure.ai.formrecognizer; azure.ai.formrecognizer.DocumentAnalysisClient(); c.begin_analyze_document("other")', 'import boto3; c.analyze_document(x)', 'import boto3; c.detect_document_text(x)', 'import boto3; c.get_expense_analysis(x)', 'import pdfplumber; x.extract_text(x)', 'import fitz; x.extract_text(x)', 'import pypdf; x.extract_text(x)', 'import PyPDF2; x.extract_text(x)', 'import pdfminer; x.extract_text(x)', 'import pytesseract; x.image_to_string(x)', 'import pandas; x.read_csv(x)', 'import pandas; x.read_excel(x)', 'import camelot; x.read_pdf(x)', 'import tabula; x.read_pdf(x)', 'import tabula; x.convert_into(x)', 'import pdfplumber; x.extract_table(x)', 'import pdfplumber; x.extract_tables(x)', 'import pdfplumber; x.find_table(x)', 'import pdfplumber; x.find_tables(x)', 'import fitz; x.find_tables(x)', 'import invoice2data\ndef extract_data(): pass\ninvoice2data.extract_data(x)', 'from invoice2data import extract_data as e\ndef e(): pass\ne(x)', 'class X:\n def extract_invoice(self): pass\nx.extract_invoice()', 'from other import extract_invoice as e\nclass extract_invoice: pass\ne()', 'import invoice2data\ninvoice2data = other\ninvoice2data.extract_data(x)', 'from other import extract_invoice\nwith thing() as extract_invoice: extract_invoice()', 'from other import extract_invoice\nasync def f():\n async with thing() as extract_invoice: extract_invoice()', 'from other import extract_invoice as e\ne: object = other\ne()', 'import invoice2data; a=b; b=a; a.extract_data(x)']

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = main(list(args))
            except SystemExit as error:
                code = error.code
        return code, out.getvalue()

    def test_phrase_oracle(self):
        tree = ast.parse(Path(p.__file__).read_text())
        literals = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n, ast.Assign)}
        for name, expected in [('INVOICEEXTRACTION', EXPECTED_POSITIVE),
                               ('NOINVOICEEXTRACTION', EXPECTED_NEGATIVE),
                               ('GENERIC_NAMES', EXPECTED_GENERIC)]:
            self.assertEqual(literals[name], expected)
            self.assertEqual(len(literals[name]), len(set(literals[name])))
        self.assertEqual(tuple(map(len, [EXPECTED_POSITIVE, EXPECTED_NEGATIVE, EXPECTED_GENERIC])), (50,24,24))

    def test_all_positive_phrases(self):
        for phrase in EXPECTED_POSITIVE:
            with self.subTest(phrase=phrase):
                self.write('README.md', phrase)
                self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_all_negative_phrases(self):
        self.write('app.py', 'x.extract_invoice()')
        for phrase in EXPECTED_NEGATIVE:
            with self.subTest(phrase=phrase):
                self.write('README.md', phrase)
                result = audit(self.root)
                self.assertEqual(len(result['findings']), 1)
                self.assertEqual(result['findings'][0]['id'], 'documented-no-invoice-extraction-claim-false')

    def test_routes(self):
        sources = ['from invoice2data import other; invoice2data.extract_data(x)',
                   'from mindee import product; mindee.Client(); c.parse(product.InvoiceV4)',
                   'from azure.ai import formrecognizer as a; a.DocumentAnalysisClient(); c.begin_analyze_document("prebuilt-invoice")'] + POSITIVE_ROUTES + ['x.' + name + '()' for name in EXPECTED_GENERIC]
        sources += ['from other import ' + name + '; ' + name + '()' for name in EXPECTED_GENERIC]
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(evidence(source))

    def test_non_evidence(self):
        for source in NEGATIVE_ROUTES:
            with self.subTest(source=source):
                self.assertFalse(evidence(source))

    def test_pair_scope(self):
        pairs = [('import mindee; mindee.Client()', 'x.parse(InvoiceV4)'),
                 ('import veryfi; veryfi.Client()', 'x.process_document(x)'),
                 ('from azure.ai.formrecognizer import DocumentAnalysisClient; DocumentAnalysisClient()',
                  'x.begin_analyze_document("prebuilt-invoice")')]
        self.write('README.md', 'invoice extraction')
        for first, second in pairs:
            self.write('a.py', first)
            self.write('b.py', second)
            self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_good(self):
        self.write('README.md', 'Extract invoices.')
        self.write('app.py', 'import invoice2data; invoice2data.extract_data("x")')
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_bad_json(self):
        self.write('README.md', 'Invoice extraction')
        code, output = self.cli('audit', str(self.root), '--json')
        self.assertEqual(code, 2)
        result = json.loads(output)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['findings'][0]['id'], 'documented-invoice-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])

    def test_test_only(self):
        self.write('README.md', 'Invoice extraction')
        for path in ['tests/app.py', 'test_app.py', 'app_test.py']:
            with self.subTest(path=path):
                file = self.write(path, 'x.extract_invoice()')
                self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
                self.assertEqual(self.cli('audit', str(self.root))[0], 0)
                self.assertEqual(self.cli('audit', str(self.root), '--fail-on', 'medium')[0], 2)
                file.unlink()

    def test_denial(self):
        self.write('README.md', "Doesn't extract invoices")
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.write('app.py', 'x.extract_invoice()')
        self.assertEqual(self.cli('audit', str(self.root))[0], 2)
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_no_claim(self):
        self.write('README.md', 'A useful utility.')
        self.write('app.py', 'x.extract_invoice()')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_fences_inline_normalization(self):
        for fence in ['```', '~~~', '   ````']:
            self.write('README.md', fence + '\nextract invoices\n' + fence + '\nSafe.')
            self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.write('README.md', '`EXTRACT-INVOICES`')
        self.assertEqual(audit(self.root)['verdict'], 'FAIL')
        self.assertEqual(paragraphs('invoice\n extraction\n\nSafe'), ['invoice extraction','safe'])
        self.write('README.md', 'extract invoicesauce')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_scope_exclusions(self):
        self.write('README.md', 'extract invoices')
        self.write('a.py', 'import mindee; mindee.Client()')
        self.write('b.py', 'x.parse(InvoiceV4)')
        for path in ['docs/a.py','fixtures/a.py','examples/a.py']:
            self.write(path, 'x.extract_invoice()')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')
        self.write('nested/docs/guide.md', 'does not extract invoices')
        self.write('ignored.md', 'extract invoices')
        self.assertEqual(len(audit(self.root)['findings']), 1)

    def test_symlinks(self):
        self.write('README.md', 'extract invoices')
        with tempfile.TemporaryDirectory() as other:
            path = Path(other)
            (path/'a.py').write_text('x.extract_invoice()')
            (self.root/'linked.py').symlink_to(path/'a.py')
            (self.root/'linked').symlink_to(path, target_is_directory=True)
            self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')

    def test_ignore_and_docs(self):
        self.write('docs/a.md', 'extract invoices')
        self.write('notes.md', 'extract invoices')
        self.assertEqual(self.cli('audit', str(self.root), '--ignore', 'docs', '--ignore', 'other')[0], 0)
        self.write('app.py', 'x.extract_invoice()')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.assertEqual(audit(self.root, ['app'])['verdict'], 'FAIL')

    def test_cli_errors_and_version(self):
        self.assertEqual(self.cli('--version'), (0, '0.1.0\n'))
        for args in [[], ['audit','/nonexistent-r187'], ['audit','--fail-on','HIGH'],
                     ['audit','--ignore'], ['audit','--unknown']]:
            self.assertEqual(self.cli(*args)[0], 1)
        result = subprocess.run([sys.executable, '-m', 'invoice_extraction_claim_audit', '--version'],
                                capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, '0.1.0\n'))

    def test_no_source_asymmetry(self):
        self.write('README.md', 'extract invoices')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')
        self.write('README.md', 'does not extract invoices')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_mixed_claims_and_longest_denial(self):
        self.write('README.md', 'does not extract invoice data')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.write('README.md', 'does not extract invoice data; extract invoices')
        self.assertEqual(len(audit(self.root)['findings']), 1)
        self.write('app.py', 'x.extract_invoice()')
        self.assertEqual(audit(self.root)['findings'][0]['id'],
                         'documented-no-invoice-extraction-claim-false')

    def test_io_errors(self):
        with patch('invoice_extraction_claim_audit.audit.os.walk', side_effect=PermissionError('unreadable')):
            self.assertEqual(self.cli('audit', str(self.root))[0], 1)
        self.write('README.md', 'safe')
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            self.assertEqual(self.cli('audit', str(self.root))[0], 1)
        (self.root/'README.md').write_bytes(bytes([255]))
        self.assertEqual(self.cli('audit', str(self.root))[0], 1)

    def test_docs_selection_and_symlink(self):
        self.write('README.md', 'safe')
        self.write('nested/docs/guide.md', 'extract invoices')
        self.assertEqual(audit(self.root)['findings'][0]['paths'], ['nested/docs/guide.md'])
        self.assertEqual(audit(self.root, ['nested'])['verdict'], 'PASS')
        (self.root/'nested/docs/guide.md').unlink()
        with tempfile.TemporaryDirectory() as other:
            path = Path(other)/'claims.md'
            path.write_text('extract invoices')
            (self.root/'nested/docs/link.md').symlink_to(path)
            self.assertEqual(audit(self.root)['verdict'], 'PASS')

if __name__ == '__main__':
    unittest.main()
