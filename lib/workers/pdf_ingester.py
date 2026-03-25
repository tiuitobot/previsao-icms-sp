# SMOKE-EXEMPT: library worker, runs inside pipeline runner
"""PDF Ingester — OCR with Azure Document Intelligence + size-based chunking.

Standard worker: extract text from PDFs (digital via PyMuPDF, scanned via
Azure OCR). Truncates output for LLM consumption.

Args (from pipeline step):
    data_dir: directory with PDF files (default: "data")
    output_dir: run output directory
    max_llm_chars: max chars for LLM consumption (default: 40000)
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

MAX_CHUNK_BYTES = 3 * 1024 * 1024  # 3MB Azure limit


def _ocr_chunk(client, pdf_bytes: bytes) -> str:
    """OCR a single PDF chunk via Azure Document Intelligence (base64 format)."""
    b64 = base64.b64encode(pdf_bytes).decode()
    poller = client.begin_analyze_document("prebuilt-read", body={"base64Source": b64})
    result = poller.result()
    text = ""
    for page in result.pages:
        text += f"\n--- Página {page.page_number} ---\n"
        text += "\n".join(line.content for line in (page.lines or [])) + "\n"
    return text


def _ocr_parallel(client, pdf_path: Path) -> str:
    """OCR with size-based chunking and parallel dispatch."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    size = pdf_path.stat().st_size
    if size <= MAX_CHUNK_BYTES:
        try:
            return _ocr_chunk(client, pdf_path.read_bytes())
        except Exception as e:
            print(f"  OCR error: {e}")
            return ""

    if fitz is None:
        return ""

    doc = fitz.open(str(pdf_path))
    bpp = size / max(len(doc), 1)
    ppc = max(1, int(MAX_CHUNK_BYTES / bpp * 0.7))

    # Build chunks
    chunks: list[tuple[bytes, int, int]] = []
    for start in range(0, len(doc), ppc):
        end = min(start + ppc, len(doc))
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        chunk_doc.save(tmp.name)
        chunk_doc.close()
        chunk_bytes = Path(tmp.name).read_bytes()
        Path(tmp.name).unlink(missing_ok=True)
        chunks.append((chunk_bytes, start + 1, end))
        print(f"    Chunk: pages {start + 1}-{end} ({len(chunk_bytes) / 1024 / 1024:.1f} MB)")
    doc.close()

    # Parallel OCR
    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}
        for chunk_bytes, first, last in chunks:
            fut = pool.submit(_ocr_chunk, client, chunk_bytes)
            futures[fut] = (first, last)

        for fut in as_completed(futures):
            first, last = futures[fut]
            try:
                ct = fut.result()
                # Renumber pages
                def renum(m, off=first - 1):
                    return f"--- Página {int(m.group(1)) + off} ---"
                ct = re.sub(r"--- Página (\d+) ---", renum, ct)
                results[first] = ct
                print(f"    OCR pages {first}-{last} done")
            except Exception as e:
                print(f"    OCR pages {first}-{last} failed: {e}")

    # Reassemble in order
    return "".join(results[k] for k in sorted(results))


def main(data_dir: str = "data", output_dir: str = "", max_llm_chars: int = 40000) -> dict:
    """Main entry point for pipeline execution."""
    pdfs = sorted(Path(data_dir).glob("*.pdf"))
    if not pdfs:
        return {"status": "error", "message": "No PDF in data/"}

    pdf = pdfs[0]
    print(f"  Processing: {pdf.name} ({pdf.stat().st_size / 1024 / 1024:.1f} MB)")

    # Digital extraction
    text = ""
    if fitz:
        doc = fitz.open(str(pdf))
        for i, page in enumerate(doc):
            text += f"\n--- Página {i + 1} ---\n{page.get_text('text')}\n"
        doc.close()

    # Check if scanned
    if sum(1 for c in text if c.isalnum()) < 500:
        ep = os.environ.get("AZURE_DOC_INTELLIGENCE_ENDPOINT", "")
        key = os.environ.get("AZURE_DOC_INTELLIGENCE_KEY", "")
        if ep and key:
            print(f"  Scanned PDF. Running parallel Azure OCR...")
            try:
                from azure.ai.documentintelligence import DocumentIntelligenceClient
                from azure.core.credentials import AzureKeyCredential
                client = DocumentIntelligenceClient(ep, AzureKeyCredential(key))
                ocr = _ocr_parallel(client, pdf)
                if ocr:
                    text = ocr
                    print(f"  OCR done: {len(ocr)} chars")
            except ImportError:
                print("  azure-ai-documentintelligence not installed")
        else:
            print("  No Azure OCR credentials — text will be limited")

    # Truncate for LLM consumption
    total_chars = len(text)
    llm_text = text[:max_llm_chars]
    if total_chars > max_llm_chars:
        llm_text += f"\n\n[Truncado: {total_chars} chars total, primeiros {max_llm_chars} mostrados]"

    return {
        "status": "ok",
        "pdf_file": pdf.name,
        "total_pages": text.count("--- Página "),
        "total_chars": total_chars,
        "text": llm_text,
    }
