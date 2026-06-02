import re
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from pgvector.django import CosineDistance

from audit.models import RetrievalLog
from documents.models import Chunk, Document, DocumentWorkspaceAssignment, DocumentVersion, ExtractedFact
from providers import answer_with_context, embed_texts, rewrite_question
from control.pii import redact_pii
from support.shipping import ShippingManagerClient, ShippingManagerError, ShippingManagerNotConfigured


SHIPPING_QUERY_HINTS = [
    'tracking', 'shipment', 'package', 'packages', 'fedex', 'delivery status', 'where is my package',
    'where is the package', 'where is my shipment', 'latest status', 'tracking number', 'find package', 'find packages',
    'recent delivered packages', 'recent packages', 'show packages', 'show shipments'
]

SHIPPING_NEGATIVE_HINTS = [
    'parking', 'permit', 'permits', 'fee', 'fees', 'policy', 'handbook', 'benefits', 'paystub', 'hr', 'faculty', 'staff',
    'employee', 'employees', 'tuition', 'vacation', 'leave', 'holiday'
]


TERM_EQUIVALENTS = {
    'staff': {'employee', 'employees', 'faculty', 'worker', 'workers', 'personnel'},
    'employee': {'staff', 'employees', 'worker', 'workers', 'personnel'},
    'employees': {'employee', 'staff', 'worker', 'workers', 'personnel'},
    'worker': {'employee', 'employees', 'staff', 'personnel'},
    'workers': {'employee', 'employees', 'staff', 'personnel'},
    'parking': {'permit', 'permits', 'garage', 'lot'},
    'fee': {'cost', 'price', 'charge', 'rate'},
    'cost': {'fee', 'price', 'charge', 'rate'},
}


def tokenize_query(text):
    return [token for token in re.findall(r"[a-z0-9']+", (text or '').lower()) if len(token) >= 3]


def expand_query_tokens(query):
    tokens = tokenize_query(query)
    expanded = []
    seen = set()
    for token in tokens:
        if token not in seen:
            expanded.append(token)
            seen.add(token)
        for synonym in TERM_EQUIVALENTS.get(token, set()):
            if synonym not in seen:
                expanded.append(synonym)
                seen.add(synonym)
    return expanded


def keyword_score(query, text):
    query_tokens = expand_query_tokens(query)
    if not query_tokens:
        return 0.0
    haystack = (text or '').lower()
    score = 0.0
    for token in query_tokens:
        if token in haystack:
            score += 1.0
    joined_query = ' '.join(tokenize_query(query))
    if joined_query and joined_query in haystack:
        score += 2.0
    return score / max(1.0, len(query_tokens))


def chunk_relevance_score(query, candidate):
    text_relevance = 1.0 - float(getattr(candidate, 'distance', 1.0) or 1.0)
    metadata_relevance = 1.0 - float(getattr(candidate, 'metadata_distance', 1.0) or 1.0)
    question_relevance = 1.0 - float(getattr(candidate, 'question_distance', 1.0) or 1.0)
    lexical = keyword_score(query, ' '.join(filter(None, [getattr(candidate, 'text', ''), getattr(candidate, 'metadata_text', ''), getattr(candidate, 'question_text', '')])))
    lexical_rank = float(getattr(candidate, 'lexical_rank', 0.0) or 0.0)
    blended_score = (0.35 * text_relevance) + (0.2 * metadata_relevance) + (0.2 * question_relevance) + (0.1 * lexical) + (0.15 * lexical_rank)
    return blended_score, text_relevance, metadata_relevance, question_relevance, lexical


def retrieve_chunks(*, tenant, workspace, query, top_k=5, document_id=None):
    standalone_query = rewrite_question(query)
    query_vector = embed_texts([standalone_query])[0]
    qs = Chunk.objects.filter(
        tenant=tenant,
        embedding__isnull=False,
        document__status=Document.STATUS_READY,
        document__workspace_assignments__workspace=workspace,
    ).select_related('document').distinct()
    if document_id:
        qs = qs.filter(document_id=document_id)

    candidate_count = max(top_k * 6, 24)
    vector_candidates = list(qs.annotate(distance=CosineDistance('embedding', query_vector)).order_by('distance')[:candidate_count])
    metadata_candidates = list(
        qs.filter(metadata_embedding__isnull=False)
        .annotate(metadata_distance=CosineDistance('metadata_embedding', query_vector))
        .order_by('metadata_distance')[:candidate_count]
    )
    question_candidates = list(
        qs.filter(question_embedding__isnull=False)
        .annotate(question_distance=CosineDistance('question_embedding', query_vector))
        .order_by('question_distance')[:candidate_count]
    )

    search_query = SearchQuery(standalone_query, search_type='plain')
    lexical_candidates = list(
        qs.annotate(
            search_vector=SearchVector('text'),
            lexical_rank=SearchRank(SearchVector('text'), search_query),
        )
        .filter(search_vector=search_query)
        .order_by('-lexical_rank')[:candidate_count]
    )

    broad_candidate_map = {}
    for candidate in vector_candidates:
        broad_candidate_map[(candidate.document_id, candidate.chunk_index)] = candidate
    for candidate in metadata_candidates:
        key = (candidate.document_id, candidate.chunk_index)
        if key in broad_candidate_map:
            existing = broad_candidate_map[key]
            existing.metadata_distance = min(
                float(getattr(existing, 'metadata_distance', 1.0) or 1.0),
                float(getattr(candidate, 'metadata_distance', 1.0) or 1.0),
            )
            if not getattr(existing, 'metadata_text', ''):
                existing.metadata_text = getattr(candidate, 'metadata_text', '')
        else:
            if not hasattr(candidate, 'distance'):
                candidate.distance = 1.0
            broad_candidate_map[key] = candidate
    for candidate in question_candidates:
        key = (candidate.document_id, candidate.chunk_index)
        if key in broad_candidate_map:
            existing = broad_candidate_map[key]
            existing.question_distance = min(
                float(getattr(existing, 'question_distance', 1.0) or 1.0),
                float(getattr(candidate, 'question_distance', 1.0) or 1.0),
            )
            if not getattr(existing, 'question_text', ''):
                existing.question_text = getattr(candidate, 'question_text', '')
        else:
            if not hasattr(candidate, 'distance'):
                candidate.distance = 1.0
            broad_candidate_map[key] = candidate
    for candidate in lexical_candidates:
        key = (candidate.document_id, candidate.chunk_index)
        if key in broad_candidate_map:
            existing = broad_candidate_map[key]
            existing.lexical_rank = max(float(getattr(existing, 'lexical_rank', 0.0) or 0.0), float(getattr(candidate, 'lexical_rank', 0.0) or 0.0))
        else:
            if not hasattr(candidate, 'distance'):
                candidate.distance = 1.0
            broad_candidate_map[key] = candidate

    broad_candidates = list(broad_candidate_map.values())

    scored_candidates = []
    doc_scores = defaultdict(float)
    for candidate in broad_candidates:
        blended_score, text_relevance, metadata_relevance, question_relevance, lexical = chunk_relevance_score(standalone_query, candidate)
        candidate.relevance_score = text_relevance
        candidate.metadata_relevance_score = metadata_relevance
        candidate.question_relevance_score = question_relevance
        candidate.lexical_score = lexical
        candidate.blended_score = blended_score
        scored_candidates.append(candidate)
        doc_scores[candidate.document_id] = max(doc_scores[candidate.document_id], blended_score)

    scored_candidates.sort(key=lambda candidate: candidate.blended_score, reverse=True)
    best_candidate = scored_candidates[0] if scored_candidates else None

    local_expansion = []
    local_window = 2
    if best_candidate and not document_id:
        neighbor_indexes = range(max(0, best_candidate.chunk_index - local_window), best_candidate.chunk_index + local_window + 1)
        local_expansion = list(
            Chunk.objects.filter(
                tenant=tenant,
                document_id=best_candidate.document_id,
                document__status=Document.STATUS_READY,
                document__workspace_assignments__workspace=workspace,
                chunk_index__in=neighbor_indexes,
            )
            .select_related('document')
            .distinct()
            .order_by('chunk_index')
        )
        for chunk in local_expansion:
            if not hasattr(chunk, 'distance'):
                chunk.distance = getattr(best_candidate, 'distance', None)
            if not hasattr(chunk, 'metadata_distance'):
                chunk.metadata_distance = getattr(best_candidate, 'metadata_distance', None)
            if not hasattr(chunk, 'question_distance'):
                chunk.question_distance = getattr(best_candidate, 'question_distance', None)
            if not hasattr(chunk, 'relevance_score'):
                blended_score, text_relevance, metadata_relevance, question_relevance, lexical = chunk_relevance_score(standalone_query, chunk)
                chunk.relevance_score = text_relevance
                chunk.metadata_relevance_score = metadata_relevance
                chunk.question_relevance_score = question_relevance
                chunk.lexical_score = lexical
                chunk.blended_score = blended_score

    result_by_key = {}
    ordered_results = []
    for candidate in scored_candidates:
        key = (candidate.document_id, candidate.chunk_index)
        if key in result_by_key:
            continue
        result_by_key[key] = candidate
        ordered_results.append(candidate)

    if local_expansion:
        insertion_index = 1 if ordered_results else 0
        local_sorted = sorted(local_expansion, key=lambda chunk: (chunk.chunk_index != best_candidate.chunk_index, chunk.chunk_index))
        for chunk in local_sorted:
            key = (chunk.document_id, chunk.chunk_index)
            if key in result_by_key:
                continue
            result_by_key[key] = chunk
            ordered_results.insert(insertion_index, chunk)
            insertion_index += 1

    doc_diverse_results = []
    seen_docs = set()
    for candidate in ordered_results:
        if candidate.document_id in seen_docs and len(doc_diverse_results) >= top_k:
            continue
        doc_diverse_results.append(candidate)
        seen_docs.add(candidate.document_id)

    results = doc_diverse_results[:top_k]

    redacted_query = redact_pii(query)
    RetrievalLog.objects.create(
        tenant=tenant,
        workspace=workspace,
        query_text=redacted_query['text'],
        top_k=top_k,
        result_count=len(results),
        latency_ms=0,
        metadata_json={
            'mode': 'two_pass_hybrid_local_expansion',
            'document_id': document_id,
            'candidate_count': candidate_count,
            'vector_candidate_count': len(vector_candidates),
            'metadata_candidate_count': len(metadata_candidates),
            'question_candidate_count': len(question_candidates),
            'lexical_candidate_count': len(lexical_candidates),
            'merged_candidate_count': len(broad_candidates),
            'standalone_query': standalone_query,
            'best_document_id': getattr(best_candidate, 'document_id', None),
            'best_chunk_index': getattr(best_candidate, 'chunk_index', None),
            'local_window': local_window if best_candidate and not document_id else 0,
            'local_expansion_count': len(local_expansion),
            'document_scores': {str(doc_id): score for doc_id, score in doc_scores.items()},
            'contains_pii': redacted_query['contains_pii'],
            'pii_types': redacted_query['pii_types'],
        },
    )
    return results


def retrieve_facts(*, tenant, workspace, query, top_k=8, document_id=None):
    query_tokens = expand_query_tokens(query)
    facts = ExtractedFact.objects.filter(
        tenant=tenant,
        document__status=Document.STATUS_READY,
        document__workspace_assignments__workspace=workspace,
    ).select_related('document', 'chunk').distinct()
    if document_id:
        facts = facts.filter(document_id=document_id)

    scored = []
    heading_scores = defaultdict(float)
    for fact in facts.order_by('-confidence')[:800]:
        dominant_heading = ''
        if fact.chunk:
            dominant_heading = (fact.chunk.metadata_json or {}).get('dominant_heading', '')
        haystack = ' '.join(filter(None, [fact.label, dominant_heading, fact.value_text, fact.normalized_text]))
        lexical = keyword_score(query, haystack)
        exact_bonus = 0.0
        lowered = haystack.lower()
        for token in query_tokens:
            if token in lowered:
                exact_bonus += 0.1
        list_bonus = 0.15 if fact.fact_type == ExtractedFact.FACT_LIST_ITEM else 0.0
        heading_bonus = 0.2 if dominant_heading and any(token in dominant_heading.lower() for token in query_tokens) else 0.0
        score = (0.65 * lexical) + (0.15 * float(fact.confidence or 0.0)) + exact_bonus + list_bonus + heading_bonus
        if score > 0:
            fact.match_score = score
            fact.dominant_heading = dominant_heading
            scored.append(fact)
            if dominant_heading:
                heading_scores[dominant_heading] = max(heading_scores[dominant_heading], score)

    for fact in scored:
        if getattr(fact, 'dominant_heading', ''):
            fact.match_score += 0.15 * heading_scores.get(fact.dominant_heading, 0.0)

    scored.sort(key=lambda fact: fact.match_score, reverse=True)
    return scored[:top_k]


def _normalize_code_query(text: str) -> str:
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).split())


def extract_code_lookup_answer(query, results, document=None):
    query_text = (query or '').strip()
    normalized_query = _normalize_code_query(query_text)
    broad_request_markers = [
        'all codes', 'explain all', 'all of the codes', 'what are the codes', 'list the codes',
        'summarize the codes', 'code explanations', 'line 14 and 16', 'lines 14 and 16', 'series 1 and 2'
    ]
    if any(marker in normalized_query for marker in broad_request_markers):
        return None
    code_matches = re.findall(r'\b([12][A-K])\b', query_text.upper())
    if len(set(code_matches)) != 1:
        return None

    target_code = code_matches[0]
    code_pattern = re.compile(r'\b([12][A-K])\b')
    stop_phrases = [
        'code description',
        'line 16',
        'section 4980h',
        'qualified offer transition relief',
        'if used, leave line 15 blank',
        'not applicable to the shp',
    ]

    def clean_meaning(text):
        value = ' '.join((text or '').split()).strip(' .;:-')
        for phrase in stop_phrases:
            idx = value.lower().find(phrase)
            if idx > 0:
                value = value[:idx].strip(' .;:-')
        return value

    candidate_texts = []
    for result in results or []:
        text = (getattr(result, 'text', '') or '').strip()
        if text:
            candidate_texts.append(text)

    if document is not None:
        chunk_qs = Chunk.objects.filter(document=document).order_by('chunk_index')
        for chunk in chunk_qs:
            text = (chunk.text or '').strip()
            if text and target_code in text.upper():
                candidate_texts.append(text)
        latest_version = DocumentVersion.objects.filter(document=document).order_by('-version_number', '-id').first()
        if latest_version:
            raw_preview = ((latest_version.extraction_metadata_json or {}).get('raw_text_preview') or '').strip()
            if raw_preview and target_code in raw_preview.upper():
                candidate_texts.append(raw_preview)

    seen = set()
    deduped_candidate_texts = []
    for text in candidate_texts:
        key = text[:1000]
        if key in seen:
            continue
        seen.add(key)
        deduped_candidate_texts.append(text)

    for text in deduped_candidate_texts:
        if not text or target_code not in text.upper():
            continue

        normalized = ' '.join(text.split())

        direct_match = re.search(rf'\b{re.escape(target_code)}\b\s*[:\-–—]\s*(.+)', normalized, re.IGNORECASE)
        if direct_match:
            meaning = clean_meaning(direct_match.group(1))
            if meaning and len(meaning) >= 8 and not meaning.upper().startswith(target_code):
                return f'On Form 1095-C, code {target_code} means {meaning}.'

        matches = list(code_pattern.finditer(normalized))
        for idx, match in enumerate(matches):
            code = match.group(1).upper()
            if code != target_code:
                continue
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(normalized), start + 280)
            segment = normalized[start:end]
            meaning = clean_meaning(segment)
            if meaning and len(meaning) >= 8 and not meaning.upper().startswith(target_code):
                return f'On Form 1095-C, code {target_code} means {meaning}.'

        around = re.search(rf'(.{{0,80}}\b{re.escape(target_code)}\b.{{0,220}})', normalized, re.IGNORECASE)
        if around:
            snippet = clean_meaning(around.group(1))
            if snippet and len(snippet) > len(target_code) + 12:
                return f'Here is the matching Form 1095-C code text for {target_code}: {snippet}.'

    return None


def _extract_tracking_number(query: str) -> str:
    compact = re.sub(r'[^0-9]', '', query or '')
    return compact if len(compact) >= 10 else ''



def _carrier_tracking_url(carrier: str, tracking_number: str) -> str:
    carrier_key = (carrier or '').strip().lower()
    if carrier_key == 'fedex':
        return f'https://www.fedex.com/fedextrack/?trknbr={tracking_number}'
    return ''



def _format_shipping_datetime(value: str) -> str:
    raw = (value or '').strip()
    if not raw:
        return ''
    try:
        normalized = raw.replace('Z', '+00:00')
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo('UTC'))
        local_dt = dt.astimezone(ZoneInfo('America/New_York'))
        pretty = local_dt.strftime('%b %d, %Y at %I:%M %p %Z')
        return pretty.replace(' 0', ' ')
    except Exception:
        return raw



def _build_shipping_detail_answer(row: dict, *, include_intro: bool = False) -> str:
    tracking = row.get('tracking_number') or 'unknown'
    carrier = (row.get('carrier') or 'carrier').upper()
    status = row.get('status') or 'Unknown'
    location = row.get('latest_location') or ''
    estimated_delivery = _format_shipping_datetime(row.get('estimated_delivery') or '')
    delivered_at = _format_shipping_datetime(row.get('delivered_at') or '')
    tracking_url = _carrier_tracking_url(row.get('carrier') or '', tracking)

    sections = []
    if include_intro:
        sections.append('I found a matching shipment for your request.')

    status_line = f'{carrier} tracking {tracking} is currently marked {status.lower()}.'
    if location:
        status_line += f' Latest location: {location}.'
    sections.append(status_line)

    if delivered_at:
        sections.append(f'Delivered on {delivered_at}.')
    elif estimated_delivery:
        sections.append(f'Current delivery timing: {estimated_delivery}.')

    if tracking_url:
        sections.append(f'Track it here: {tracking_url}')
    return '\n\n'.join(section.strip() for section in sections if section).strip()



def shipping_answer_payload(*, tenant, query: str, limit: int = 3):
    normalized = (query or '').strip().lower()
    tracking_number = _extract_tracking_number(query)
    has_shipping_hint = any(hint in normalized for hint in SHIPPING_QUERY_HINTS)
    has_negative_hint = any(hint in normalized for hint in SHIPPING_NEGATIVE_HINTS)
    if not tracking_number and (not has_shipping_hint or has_negative_hint):
        return None

    try:
        client = ShippingManagerClient.for_tenant(tenant)
    except ShippingManagerNotConfigured:
        return None

    source = {
        'document': 'Shipping Manager',
        'source_url': '',
        'source_url_kind': 'shipping_manager',
        'shipping_manager': True,
    }

    try:
        if tracking_number:
            payload = client.get_latest_status(tracking_number)
            package = payload.get('package') or {}
            latest_event = payload.get('latest_event') or {}
            details = latest_event.get('details') or ''
            answer_text = _build_shipping_detail_answer(package)
            if details:
                answer_text = f'{answer_text} {details}'.strip()
            tracking_url = _carrier_tracking_url(package.get('carrier') or '', tracking_number)
            source.update({
                'tracking_number': tracking_number,
                'status': package.get('status') or latest_event.get('status') or 'Unknown',
                'location': latest_event.get('location') or package.get('latest_location') or '',
                'source_url': tracking_url,
            })
            return {
                'answer': answer_text,
                'sources': [source],
                'shipping_lookup': True,
                'tracking_number': tracking_number,
            }

        payload = client.search_packages(query.strip(), limit=limit)
        results = payload.get('results') or []
        if not results:
            return {
                'answer': 'I could not find a matching package in the tenant shipping manager.',
                'sources': [source],
                'shipping_lookup': True,
            }
        top_match = results[0]
        tracking_url = _carrier_tracking_url(top_match.get('carrier') or '', top_match.get('tracking_number') or '')
        source.update({
            'tracking_number': top_match.get('tracking_number') or '',
            'status': top_match.get('status') or 'Unknown',
            'location': top_match.get('latest_location') or '',
            'source_url': tracking_url,
        })
        answer_text = _build_shipping_detail_answer(top_match, include_intro=True)
        if len(results) > 1:
            extras = []
            for row in results[1:limit]:
                extras.append(_build_shipping_detail_answer(row))
            if extras:
                answer_text = f"{answer_text}\n\nOther matches:\n- " + '\n- '.join(extras)
        return {
            'answer': answer_text,
            'sources': [{**source, 'tracking_number': row.get('tracking_number') or '', 'source_url': _carrier_tracking_url(row.get('carrier') or '', row.get('tracking_number') or '')} for row in results[:limit]],
            'shipping_lookup': True,
            'tracking_number': top_match.get('tracking_number') or '',
        }
    except ShippingManagerError:
        return {
            'answer': 'I had trouble reaching the tenant shipping manager just now.',
            'sources': [source],
            'shipping_lookup': True,
        }



def maybe_answer_shipping_question(*, tenant, workspace, query: str):
    payload = shipping_answer_payload(tenant=tenant, query=query, limit=3)
    if payload is None:
        return None
    return payload['answer'], []



def build_context_blocks(results, facts=None):
    blocks = []
    for idx, fact in enumerate(facts or [], start=1):
        blocks.append(
            'UNTRUSTED DOCUMENT FACT\n'
            f'[Fact {idx}] {fact.document.filename} · {fact.fact_type} · score={float(getattr(fact, "match_score", 0.0)):.4f}\n'
            f'{fact.label + ": " if fact.label else ""}{fact.value_text}'
        )
    source_offset = len(facts or [])
    for idx, row in enumerate(results, start=1):
        blocks.append(
            'UNTRUSTED DOCUMENT EXCERPT\n'
            f'[Source {idx + source_offset}] {row.document.filename} · chunk {row.chunk_index} · distance={float(getattr(row, "distance", 0.0)):.4f}\n{row.text}'
        )
    return blocks


def answer_question(*, tenant, workspace, query, top_k=5, document_id=None, temperature=None):
    shipping_payload = shipping_answer_payload(tenant=tenant, query=query, limit=3)
    if shipping_payload is not None:
        return shipping_payload, []

    facts = retrieve_facts(
        tenant=tenant,
        workspace=workspace,
        query=query,
        top_k=min(6, max(3, top_k)),
        document_id=document_id,
    )
    results = retrieve_chunks(
        tenant=tenant,
        workspace=workspace,
        query=query,
        top_k=top_k,
        document_id=document_id,
    )
    context_blocks = build_context_blocks(results, facts=facts)
    exact_code_answer = extract_code_lookup_answer(query, results, document=results[0].document if results else None)
    if exact_code_answer:
        return exact_code_answer, results
    answer = answer_with_context(query, context_blocks, temperature=temperature) if context_blocks else 'I could not find relevant document context for that question yet.'
    return answer, results
