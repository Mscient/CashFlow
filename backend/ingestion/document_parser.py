"""
document_parser.py - Parse PDF invoices and receipt images using pdfplumber + pytesseract.

Extracts: amount, date, party name, invoice_no, suggested_type.
Returns a list of candidate transaction dicts (same shape as whatsapp_parser).
"""

import re
import os
from datetime import datetime
from typing import Optional

# ── Regex (shared with whatsapp_parser) ──────────────────────────────────────
_AMT_RE = re.compile(
    r"(?:[\u20b9]|Rs\.?\s*|INR\s*|Total[\s:]*|Amount[\s:]*|Grand Total[\s:]*)"
    r"([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_BARE_AMT_RE = re.compile(r"(?<!\d)([\d,]{3,}(?:\.\d{1,2})?)(?!\d)")
_DATE_RE = re.compile(
    r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})|(\d{4}-\d{2}-\d{2})"
    r"|(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})",
    re.IGNORECASE,
)
_INV_NO_RE   = re.compile(r"(?:inv(?:oice)?[\s#\-]*(?:no\.?\s*)?|#)([A-Z0-9\-]+)", re.IGNORECASE)
_PARTY_RE    = re.compile(r"(?:bill(?:ed)?\s+to|customer|client|buyer|from|vendor|supplier)\s*[:\-]?\s*([A-Za-z][^\n,]{2,40})", re.IGNORECASE)
_INVOICE_KW  = re.compile(r"\b(invoice|tax invoice|proforma|bill)\b", re.IGNORECASE)
_RECEIPT_KW  = re.compile(r"\b(receipt|payment receipt|acknowledgement)\b", re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_amount(text):
    for m in _AMT_RE.finditer(text):
        raw = m.group(1)
        if raw:
            try:
                v = float(raw.replace(",", ""))
                if v > 0:
                    return v
            except ValueError:
                pass
    # Fallback: take the largest bare number (likely total)
    candidates = []
    for m in _BARE_AMT_RE.finditer(text):
        try:
            candidates.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return max(candidates) if candidates else None


def _extract_date(text):
    for m in _DATE_RE.finditer(text):
        raw = m.group(0)
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return datetime.today().strftime("%Y-%m-%d")


def _extract_party(text):
    m = _PARTY_RE.search(text)
    if m:
        return m.group(1).strip().rstrip(".,;")
    # Fallback: first non-empty line that looks like a name
    for line in text.splitlines():
        line = line.strip()
        if 3 < len(line) < 50 and re.match(r"^[A-Za-z]", line) and not re.search(r"[:/\\]", line):
            return line
    return "Unknown"


def _extract_invoice_no(text):
    m = _INV_NO_RE.search(text)
    return m.group(1).upper() if m else None


def _classify_type(text):
    if _RECEIPT_KW.search(text):
        return "receipt"
    if _INVOICE_KW.search(text):
        return "invoice"
    return "invoice"


def _extract_text_from_pdf(path):
    """Extract text from PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is not installed. Run: pip install pdfplumber")
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _extract_text_from_image(path):
    """Extract text from image using pytesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError("pytesseract and Pillow are required. Run: pip install pytesseract Pillow")
    img = Image.open(path)
    return pytesseract.image_to_string(img)


def parse_document(path: str, source_filename: str = None) -> list[dict]:
    """
    Parse a PDF or image file and return a list of candidate transaction dicts.

    Returns a list with a single entry (one document = one transaction).
    Each dict: source, filename, party, date, amount, suggested_type,
               invoice_no, raw_text, confidence
    """
    filename = source_filename or os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        text = _extract_text_from_pdf(path)
        source = "pdf"
    elif ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"):
        text = _extract_text_from_image(path)
        source = "image"
    else:
        return []

    if not text or not text.strip():
        return []

    amount    = _extract_amount(text)
    date      = _extract_date(text)
    party     = _extract_party(text)
    inv_no    = _extract_invoice_no(text)
    stype     = _classify_type(text)
    confidence = "high" if (amount is not None and inv_no is not None) else \
                 "medium" if amount is not None else "low"

    return [{
        "source":         source,
        "filename":       filename,
        "sender":         party,
        "party":          party,
        "date":           date,
        "amount":         amount,
        "suggested_type": stype,
        "invoice_no":     inv_no,
        "raw_text":       text[:500],   # truncate for UI display
        "confidence":     confidence,
    }]
