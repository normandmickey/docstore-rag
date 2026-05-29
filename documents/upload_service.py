import hashlib
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.db import transaction
from markdownify import markdownify as html_to_markdown

from ingestion.models import IngestionJob
from ingestion.tasks import ingest_document_task

from .models import Document, DocumentVersion


def _file_sha256(uploaded_file):
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def create_or_reuse_document(*, tenant, workspace, uploaded_file, filename, mime_type='', size_bytes=0, collection='', uploaded_by=None, raw_text='', source_type=Document.SOURCE_UPLOAD, source_url='', extractor=IngestionJob.EXTRACTOR_STANDARD):
    content_hash = _file_sha256(uploaded_file) if uploaded_file else ''

    exact_duplicate = Document.objects.filter(
        tenant=tenant,
        workspace=workspace,
        content_hash=content_hash,
    ).exclude(status=Document.STATUS_DELETED).order_by('-created_at').first() if content_hash else None
    if exact_duplicate:
        latest_version = exact_duplicate.versions.order_by('-version_number', '-id').first()
        latest_job = exact_duplicate.ingestion_jobs.order_by('-created_at').first()
        return {
            'mode': 'duplicate',
            'document': exact_duplicate,
            'version': latest_version,
            'job': latest_job,
            'content_hash': content_hash,
        }

    existing_same_name = Document.objects.filter(
        tenant=tenant,
        workspace=workspace,
        filename=filename,
    ).exclude(status=Document.STATUS_DELETED).order_by('-created_at').first()

    with transaction.atomic():
        if existing_same_name:
            document = existing_same_name
            next_version = (document.versions.order_by('-version_number').first().version_number + 1) if document.versions.exists() else 1
            document.collection = collection
            document.mime_type = mime_type or document.mime_type
            document.size_bytes = size_bytes or document.size_bytes
            document.content_hash = content_hash
            document.status = Document.STATUS_PENDING
            if uploaded_file:
                document.file.save(filename, uploaded_file, save=False)
                document.object_key = document.file.name
            document.save(update_fields=['collection', 'mime_type', 'size_bytes', 'content_hash', 'file', 'object_key', 'status', 'updated_at'])
            version = DocumentVersion.objects.create(
                document=document,
                version_number=next_version,
                object_key=document.object_key,
                content_hash=content_hash,
                extraction_metadata_json={'raw_text': raw_text},
            )
            mode = 'versioned'
        else:
            document = Document(
                tenant=tenant,
                workspace=workspace,
                collection=collection,
                filename=filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                object_key=f'{tenant.slug}/{workspace.slug}/{filename}',
                content_hash=content_hash,
                source_type=source_type,
                source_url=source_url,
                uploaded_by=uploaded_by,
            )
            if uploaded_file:
                document.file.save(filename, uploaded_file, save=False)
                document.object_key = document.file.name
            document.save()
            version = DocumentVersion.objects.create(
                document=document,
                version_number=1,
                object_key=document.object_key,
                content_hash=content_hash,
                extraction_metadata_json={'raw_text': raw_text},
            )
            mode = 'created'

        job = IngestionJob.objects.create(
            tenant=tenant,
            workspace=workspace,
            document=document,
            document_version=version,
            extractor=extractor,
            status=IngestionJob.STATUS_QUEUED,
            stage='queued',
        )
        transaction.on_commit(lambda: ingest_document_task.delay(job.id))

    return {
        'mode': mode,
        'document': document,
        'version': version,
        'job': job,
        'content_hash': content_hash,
    }


def normalize_url(url):
    parsed = urlparse((url or '').strip())
    scheme = (parsed.scheme or 'https').lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or '/'
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    return urlunparse((scheme, netloc, path, '', parsed.query, ''))


def _filename_from_url(url, content_type='text/html'):
    parsed = urlparse(url)
    tail = (parsed.path or '').rstrip('/').split('/')[-1]
    if tail:
        return tail
    if 'html' in (content_type or '').lower():
        return f'{parsed.netloc or "page"}.html'
    return f'{parsed.netloc or "page"}.txt'


def _extract_links_from_html(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for tag in soup.find_all('a', href=True):
        href = (tag.get('href') or '').strip()
        if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if absolute.startswith('http://') or absolute.startswith('https://'):
            links.append(absolute)
    return links


def _html_to_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'header', 'footer', 'nav', 'aside', 'form']):
        tag.decompose()
    main = soup.find('main') or soup.find('article') or soup.find(attrs={'role': 'main'}) or soup.body or soup
    return html_to_markdown(str(main))


def create_or_reuse_url_document(*, tenant, workspace, url, collection='', uploaded_by=None):
    normalized_url = normalize_url(url)

    existing_by_url = Document.objects.filter(
        tenant=tenant,
        workspace=workspace,
        source_type=Document.SOURCE_URL,
        source_url=normalized_url,
    ).order_by('-created_at').first()

    response = requests.get(normalized_url, timeout=45, headers={'User-Agent': 'docstore-rag/1.0'})
    response.raise_for_status()

    content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
    if content_type == 'text/html' or normalized_url.lower().endswith(('.html', '.htm', '/')):
        raw_text = _html_to_text(response.text)
        mime_type = 'text/html'
        filename = _filename_from_url(normalized_url, content_type='text/html')
    else:
        raw_text = response.text
        mime_type = content_type or 'text/plain'
        filename = _filename_from_url(normalized_url, content_type=mime_type)

    uploaded_file = ContentFile(raw_text.encode('utf-8'), name=filename)
    result = create_or_reuse_document(
        tenant=tenant,
        workspace=workspace,
        uploaded_file=uploaded_file,
        filename=(existing_by_url.filename if existing_by_url else filename),
        mime_type=mime_type,
        size_bytes=len(raw_text.encode('utf-8')),
        collection=collection,
        uploaded_by=uploaded_by,
        raw_text=raw_text,
        source_type=Document.SOURCE_URL,
        source_url=normalized_url,
    )
    result['normalized_url'] = normalized_url
    result['discovered_links'] = _extract_links_from_html(response.text, normalized_url) if mime_type == 'text/html' else []
    return result


def collect_urls_for_ingest(seed_urls, crawl_mode='single', max_pages=10):
    normalized = []
    seen_seed = set()
    for url in seed_urls:
        if not url:
            continue
        candidate = normalize_url(url)
        if candidate in seen_seed:
            continue
        seen_seed.add(candidate)
        normalized.append(candidate)
    if crawl_mode != 'same_domain':
        return normalized

    seen = set()
    queue = deque(normalized)
    results = []
    root_domains = {urlparse(url).netloc for url in normalized}

    while queue and len(results) < max_pages:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        results.append(current)
        try:
            response = requests.get(current, timeout=30, headers={'User-Agent': 'docstore-rag/1.0'})
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
            if content_type != 'text/html':
                continue
            for link in _extract_links_from_html(response.text, current):
                if urlparse(link).netloc in root_domains and link not in seen and link not in queue and len(results) + len(queue) < max_pages:
                    queue.append(link)
        except Exception:
            continue

    return results
