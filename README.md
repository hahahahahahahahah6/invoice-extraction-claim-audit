# Documentation claim auditor

An offline audit tool comparing documentation about the checked capability with listed calls in Python source. Syntax is parsed without executing the inspected code. Requires Python 3.9 or newer and has no runtime dependencies.

```sh
python3 -m pip install .
invoice-extraction-claim-audit --version
invoice-extraction-claim-audit audit .
python3 -m invoice_extraction_claim_audit audit . --json
```

The directory defaults to the current directory. Options:

```text
--json                 Emit JSON
--verbose              Show evidence paths
--ignore PREFIX        Skip a relative path prefix; repeat for more prefixes
--fail-on high|medium  Failure threshold, default high
--version              Print 0.1.0
```

The scanner reads root README.md and Markdown files with a docs directory component. Backtick and tilde fences with up to three leading spaces are excluded; inline code counts. Paragraphs are normalized for case, contractions, hyphens, and whitespace. Exact phrases match at word boundaries, longest first with alphabetical ties. Denial spans are removed before affirmative matching.

Source files are checked within a single module. Symlinks are skipped. Files beneath fixtures, docs, and examples provide no evidence. Files beneath tests or with a test prefix or suffix provide only test evidence. Invalid syntax provides none. Import aliases, assignments, annotations, and context manager bindings are tracked. Local function, method, and class definitions shadow matching names.

The JSON object contains verdict, findings, evidence, and test_evidence. Each finding contains id, severity, message, and paths. There is at most one finding per family:

```text
documented-invoice-extraction-claim-false     HIGH, or MEDIUM for test-only evidence
documented-no-invoice-extraction-claim-false HIGH
```

Exit status is 0 for a pass or findings below the threshold, 2 for findings meeting it, and 1 for usage or input errors. An affirmative claim without source receives high severity; a denial without source passes.

Recognized routes include a listed call from the first library, paired client construction and operation for the next three providers, expense calls for the last provider, and the 24 generic names defined in the phrase module:

```text
invoice2data: extract_data
mindee: Client + parse(InvoiceV4 / TypeInvoiceV4)
veryfi: Client + process_document / process_document_url
azure.ai.formrecognizer / azure.ai.documentintelligence:
  DocumentAnalysisClient / DocumentIntelligenceClient
  + begin_analyze_document / begin_analyze_document_from_url("prebuilt-invoice")
boto3: analyze_expense / start_expense_analysis
```

Limitations: this is static pattern matching, not semantic judgment. Dead code counts; complex alias chains may be missed. Only listed phrases match, denial handling depends on the denial list, and each route must reside in one module. Wording about payment, approval routing, file-format decoding such as EDIFACT or UBL XML, or OCR output read manually can produce false positives. Generic names may describe payment workflows or wrappers around external binaries; recognized generic calls still count.

Receipt extraction claims are outside the phrase lists. Mindee ReceiptV5 and Azure's prebuilt-receipt model do not count. Textract analyze_document is generic analysis and does not count; get_expense_analysis only retrieves results and does not count. Hand-rolled regex extraction using re.search or re.findall with manually assembled fields is missed without a listed call. Subprocess CLIs, including invoice2data and veryfi, do not count.

The template-based library works only when layouts match known templates; recognized calls do not establish support for arbitrary unseen layouts. Mindee, Veryfi, Azure Document Intelligence, and Textract use cloud APIs: source evidence does not verify credentials or successful calls. Imports alone, plain text access, OCR, table access, and spreadsheet reads provide no evidence.

```sh
python3 -m unittest discover
python3 -m build
```

MIT licensed.
