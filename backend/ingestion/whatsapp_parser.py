"""
whatsapp_parser.py - Parse exported WhatsApp .txt chat files for financial data.
"""

import re
from datetime import datetime
from typing import Optional

_LINE_RE = re.compile(
    r"^(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]m)?)"
    r"\s*[-\u2013]\s*([^:]+):\s*(.+)$",
    re.IGNORECASE,
)

_AMT_RE = re.compile(
    r"(?:[\u20b9]|Rs\.?\s*|INR\s*)([\d,]+(?:\.\d{1,2})?)"
    r"|(?<!\w)([\d,]+(?:\.\d{1,2})?)(?:\s*/\-|\s+rupees?)",
    re.IGNORECASE,
)

_INV_NO_RE  = re.compile(r"(?:inv(?:oice)?[\s#\-]*(?:no\.?\s*)?|#)([A-Z0-9\-]+)", re.IGNORECASE)
_INVOICE_KW = re.compile(r"\b(invoice|bill|quotation|quote|billed|billing)\b", re.IGNORECASE)
_PAYMENT_KW = re.compile(r"\b(paid|payment|received|transferred|sent|credited|upi|neft|rtgs)\b", re.IGNORECASE)
_RECEIPT_KW = re.compile(r"\b(receipt|acknowledgement|voucher)\b", re.IGNORECASE)
_DUE_KW     = re.compile(r"\b(due|outstanding|pending|overdue|follow.?up)\b", re.IGNORECASE)

_DATE_IN_MSG_RE = re.compile(
    r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})|(\d{4}-\d{2}-\d{2})"
    r"|(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})",
    re.IGNORECASE,
)


def _parse_wa_date(date_str, time_str):
    ts = f"{date_str} {time_str}".strip()
    for fmt in (
        "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %I:%M %p", "%d/%m/%Y %I:%M:%S %p",
        "%m/%d/%y %H:%M", "%m/%d/%y %I:%M %p",
        "%d-%m-%Y %H:%M", "%d-%m-%Y %I:%M %p",
    ):
        try:
            return datetime.strptime(ts.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _extract_amount(text):
    for m in _AMT_RE.finditer(text):
        raw = m.group(1) or m.group(2)
        if raw:
            try:
                return float(raw.replace(",", ""))
            except ValueError:
                pass
    return None


def _classify_type(text):
    if _PAYMENT_KW.search(text):
        return "payment"
    if _RECEIPT_KW.search(text):
        return "receipt"
    return "invoice"


def _extract_invoice_no(text):
    m = _INV_NO_RE.search(text)
    return m.group(1).upper() if m else None


def _extract_date_in_msg(text):
    m = _DATE_IN_MSG_RE.search(text)
    if not m:
        return None
    raw = m.group(0)
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_whatsapp_txt(content, source_filename="whatsapp_chat.txt"):
    """
    Parse WhatsApp .txt export and return list of candidate transaction dicts.
    Each dict: source, filename, sender, party, date, amount,
               suggested_type, invoice_no, raw_text, confidence
    """
    results = []
    for line in content.splitlines():
        line = line.strip()
        m = _LINE_RE.match(line)
        if not m:
            continue
        date_part, time_part, sender, body = m.groups()
        body = body.strip()

        has_amount  = _AMT_RE.search(body) is not None
        has_keyword = any(p.search(body) for p in (_INVOICE_KW, _PAYMENT_KW, _RECEIPT_KW, _DUE_KW))
        if not (has_amount or has_keyword):
            continue

        amount     = _extract_amount(body)
        date       = _parse_wa_date(date_part, time_part)
        msg_date   = _extract_date_in_msg(body)

        results.append({
            "source":         "whatsapp",
            "filename":       source_filename,
            "sender":         sender.strip(),
            "party":          sender.strip(),
            "date":           msg_date or date,
            "amount":         amount,
            "suggested_type": _classify_type(body),
            "invoice_no":     _extract_invoice_no(body),
            "raw_text":       body,
            "confidence":     "high" if (has_amount and has_keyword) else "medium",
        })
    return results
