import re
from io import BytesIO

import fitz
from celery import shared_task
from django.utils import timezone
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markdownify import markdownify as html_to_markdown

from documents.models import Chunk, Document
from providers import embed_texts
from .models import IngestionJob


def normalize_extracted_text(text):
    text = (text or '').replace('\x00', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    cleaned_lines = []
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            cleaned_lines.append('')
            continue
        if len(line) <= 3 and any(ch.isdigit() for ch in line):
            continue
        if re.fullmatch(r'[\d\s\|.,:%$\-()]+', line) and sum(ch.isdigit() for ch in line) >= max(4, len(line) // 2):
            continue
        cleaned_lines.append(line)

    paragraphs = []
    current = []
    for line in cleaned_lines:
        if not line:
            if current:
                paragraphs.append(' '.join(current).strip())
                current = []
            continue
        if current and not re.search(r'[.!?:]$|:$', current[-1]) and line[:1].islower():
            current.append(line)
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current).strip())

    normalized = '\n\n'.join(p for p in paragraphs if p)
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    return normalized.strip()


EMBEDDING_MAX_INPUT_CHARS = 2000


def build_chunks(text, chunk_size=1000, overlap=None):
    text = normalize_extracted_text(text)
    if not text:
        return []

    if overlap is None:
        overlap = max(80, int(chunk_size * 0.3))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=['\n\n', '\n', ' ', ''],
        length_function=len,
        is_separator_regex=False,
    )
    chunks = [chunk.strip() for chunk in splitter.split_text(text) if chunk and chunk.strip()]

    deduped = []
    last = None
    for chunk in chunks:
        if chunk != last:
            deduped.append(chunk)
            last = chunk
    return deduped


def enforce_embedding_limit(chunks, max_chars=EMBEDDING_MAX_INPUT_CHARS):
    safe_chunks = []
    for chunk in chunks:
        chunk = (chunk or '').strip()
        if not chunk:
            continue
        if len(chunk) <= max_chars:
            safe_chunks.append(chunk)
            continue

        start = 0
        while start < len(chunk):
            end = min(start + max_chars, len(chunk))
            if end < len(chunk):
                split_at = chunk.rfind(' ', start, end)
                if split_at > start + 100:
                    end = split_at
            piece = chunk[start:end].strip()
            if piece:
                safe_chunks.append(piece)
            if end >= len(chunk):
                break
            start = end
    return safe_chunks


def extract_pdf_text(raw):
    pdf = fitz.open(stream=raw, filetype='pdf')
    try:
        pages = [page.get_text('text') for page in pdf]
    finally:
        pdf.close()
    return '\n\n'.join(page.strip() for page in pages if page and page.strip())


def extract_docx_text(raw):
    doc = DocxDocument(BytesIO(raw))
    parts = []
    for paragraph in doc.paragraphs:
        text = (paragraph.text or '').strip()
        if text:
            parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            values = [(cell.text or '').strip() for cell in row.cells]
            values = [value for value in values if value]
            if values:
                parts.append(' | '.join(values))
    return '\n\n'.join(parts)


def extract_text_document(raw):
    return raw.decode('utf-8', errors='ignore')


def extract_html_text(raw):
    html = raw.decode('utf-8', errors='ignore')
    return html_to_markdown(html)


def extract_document_text(document, version):
    if not document.file:
        return (version.extraction_metadata_json or {}).get('raw_text', '')

    with document.file.open('rb') as fh:
        raw = fh.read()

    filename = (document.filename or '').lower()
    mime_type = (document.mime_type or '').lower()

    if filename.endswith('.pdf') or mime_type == 'application/pdf':
        return extract_pdf_text(raw)
    if filename.endswith('.docx') or mime_type in {
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
    }:
        return extract_docx_text(raw)
    if filename.endswith('.md') or mime_type in {'text/markdown', 'text/x-markdown'}:
        return extract_text_document(raw)
    if filename.endswith('.txt') or mime_type.startswith('text/plain'):
        return extract_text_document(raw)
    if filename.endswith('.html') or filename.endswith('.htm') or mime_type == 'text/html':
        return extract_html_text(raw)

    return extract_text_document(raw)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 1})
def ingest_document_task(self, ingestion_job_id):
    job = IngestionJob.objects.select_related('document', 'document_version', 'tenant', 'workspace').get(id=ingestion_job_id)
    document = job.document
    version = job.document_version

    job.status = IngestionJob.STATUS_RUNNING
    job.stage = 'extracting'
    job.started_at = timezone.now()
    job.error_text = ''
    job.save(update_fields=['status', 'stage', 'started_at', 'error_text'])

    document.status = Document.STATUS_PROCESSING
    document.save(update_fields=['status', 'updated_at'])

    try:
        extracted_text = extract_document_text(document, version)
        cleaned_text = normalize_extracted_text(extracted_text)

        job.stage = 'embedding'
        job.save(update_fields=['stage'])

        chunk_size = job.workspace.default_chunk_size or 1000
        chunks = build_chunks(cleaned_text, chunk_size=chunk_size, overlap=max(80, int(chunk_size * 0.3)))
        chunks = enforce_embedding_limit(chunks)
        vectors = embed_texts(chunks) if chunks else []
        Chunk.objects.filter(document_version=version).delete()
        for idx, chunk_text in enumerate(chunks):
            Chunk.objects.create(
                tenant=job.tenant,
                workspace=job.workspace,
                document=document,
                document_version=version,
                chunk_index=idx,
                text=chunk_text,
                token_count=max(1, len(chunk_text) // 4),
                metadata_json={'stub': False},
                embedding=vectors[idx] if idx < len(vectors) else None,
            )

        version.parse_status = 'ready'
        version.extraction_metadata_json = {
            **(version.extraction_metadata_json or {}),
            'raw_text_preview': cleaned_text[:500],
            'chunk_count': len(chunks),
        }
        version.save(update_fields=['parse_status', 'extraction_metadata_json'])

        document.status = Document.STATUS_READY
        document.save(update_fields=['status', 'updated_at'])

        job.status = IngestionJob.STATUS_SUCCEEDED
        job.stage = 'done'
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'stage', 'finished_at'])
        return {'chunk_count': len(chunks)}
    except Exception as exc:
        job.status = IngestionJob.STATUS_FAILED
        job.stage = 'failed'
        job.error_text = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'stage', 'error_text', 'finished_at'])
        document.status = Document.STATUS_FAILED
        document.save(update_fields=['status', 'updated_at'])
        raise
