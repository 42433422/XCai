"""Parse uploaded knowledge files into text chunks."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException


SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".pdf", ".docx", ".xlsx"}
MAX_UPLOAD_BYTES = int(os.environ.get("MODSTORE_KB_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))


def _chunk_size() -> int:
    return max(400, min(int(os.environ.get("MODSTORE_KB_CHUNK_SIZE", "1000")), 4000))


def _chunk_overlap() -> int:
    return max(0, min(int(os.environ.get("MODSTORE_KB_CHUNK_OVERLAP", "120")), 800))


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _normalize_text(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _parse_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise HTTPException(503, "服务器未安装 pypdf，暂不能解析 PDF") from e
    reader = PdfReader(io.BytesIO(raw))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)


def _parse_pdf_pages(raw: bytes) -> List[Tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise HTTPException(503, "服务器未安装 pypdf，暂不能解析 PDF") from e
    reader = PdfReader(io.BytesIO(raw))
    pages: List[Tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = _normalize_text((page.extract_text() or "").strip())
        if text:
            pages.append((idx, text))
    return pages


def _parse_docx(raw: bytes) -> str:
    try:
        import docx
    except ImportError as e:
        raise HTTPException(503, "服务器未安装 python-docx，暂不能解析 DOCX") from e
    doc = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _parse_xlsx(raw: bytes) -> str:
    try:
        import openpyxl
    except ImportError as e:
        raise HTTPException(503, "服务器未安装 openpyxl，暂不能解析 XLSX") from e
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    lines: List[str] = []
    for ws in wb.worksheets:
        lines.append(f"## Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if vals:
                lines.append(" | ".join(vals))
    return "\n".join(lines)


def parse_upload(filename: str, raw: bytes) -> str:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"文件过大（>{MAX_UPLOAD_BYTES // 1024 // 1024}MB）")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "仅支持 .txt/.md/.json/.csv/.pdf/.docx/.xlsx")

    if suffix in {".txt", ".md"}:
        text = _decode_text(raw)
    elif suffix == ".json":
        try:
            text = json.dumps(json.loads(_decode_text(raw)), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            text = _decode_text(raw)
    elif suffix == ".csv":
        rows = csv.reader(io.StringIO(_decode_text(raw)))
        text = "\n".join(" | ".join(cell.strip() for cell in row if cell.strip()) for row in rows)
    elif suffix == ".pdf":
        text = _parse_pdf(raw)
    elif suffix == ".docx":
        text = _parse_docx(raw)
    elif suffix == ".xlsx":
        text = _parse_xlsx(raw)
    else:
        text = ""

    normalized = _normalize_text(text)
    if len(normalized) < 10:
        raise HTTPException(400, "未能从文件中提取有效文本")
    return normalized


def chunk_text(text: str) -> List[str]:
    size = _chunk_size()
    overlap = min(_chunk_overlap(), max(0, size - 1))
    t = _normalize_text(text)
    chunks: List[str] = []
    pos = 0
    while pos < len(t):
        end = min(len(t), pos + size)
        chunk = t[pos:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(t):
            break
        pos = max(pos + 1, end - overlap)
    return chunks


def chunk_text_with_metadata(
    text: str,
    *,
    page_no: Optional[int] = None,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    chunks = chunk_text(text)
    metas: List[Dict[str, Any]] = []
    for i, _chunk in enumerate(chunks):
        meta: Dict[str, Any] = {"chunk_in_source": i}
        if page_no is not None:
            meta["page_no"] = int(page_no)
        metas.append(meta)
    return chunks, metas


def parse_and_chunk_with_metadata(filename: str, raw: bytes) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"文件过大（>{MAX_UPLOAD_BYTES // 1024 // 1024}MB）")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "仅支持 .txt/.md/.json/.csv/.pdf/.docx/.xlsx")

    if suffix == ".pdf":
        pages = _parse_pdf_pages(raw)
        if not pages:
            raise HTTPException(400, "未能从 PDF 中提取有效文本")
        all_text_parts: List[str] = []
        all_chunks: List[str] = []
        all_metas: List[Dict[str, Any]] = []
        for page_no, page_text in pages:
            all_text_parts.append(f"[第 {page_no} 页]\n{page_text}")
            chunks, metas = chunk_text_with_metadata(page_text, page_no=page_no)
            all_chunks.extend(chunks)
            all_metas.extend(metas)
        return "\n\n".join(all_text_parts), all_chunks, all_metas

    text = parse_upload(filename, raw)
    chunks, metas = chunk_text_with_metadata(text)
    if not chunks:
        raise HTTPException(400, "文本分块为空")
    return text, chunks, metas


def parse_and_chunk(filename: str, raw: bytes) -> Tuple[str, List[str]]:
    text, chunks, _metas = parse_and_chunk_with_metadata(filename, raw)
    if not chunks:
        raise HTTPException(400, "文本分块为空")
    return text, chunks
