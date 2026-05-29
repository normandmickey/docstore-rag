import re
from collections import defaultdict

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from pgvector.django import CosineDistance

from audit.models import RetrievalLog
from documents.models import Chunk, Document, ExtractedFact
from providers import answer_with_context, embed_texts, rewrite_question


def tokenize_query(text):
    return [token for token in re.findall(r"[a-z0-9']+", (text or '').lower()) if len(token) >= 3]


def keyword_score(query, text):
    query_tokens = tokenize_query(query)
    if not query_tokens:
        return 0.0
    haystack = (text or '').lower()
    score = 0.0
    for token in query_tokens:
        if token in haystack:
            score += 1.0
    joined_query = ' '.join(query_tokens)
    if joined_query and joined_query in haystack:
        score += 2.0
    return score / max(1.0, len(query_tokens))


def chunk_relevance_score(query, candidate):
    relevance = 1.0 - float(getattr(candidate, 'distance', 1.0) or 1.0)
    lexical = keyword_score(query, getattr(candidate, 'text', ''))
    lexical_rank = float(getattr(candidate, 'lexical_rank', 0.0) or 0.0)
    blended_score = (0.65 * relevance) + (0.2 * lexical) + (0.15 * lexical_rank)
    return blended_score, relevance, lexical


def retrieve_chunks(*, tenant, workspace, query, top_k=5, document_id=None):
    standalone_query = rewrite_question(query)
    query_vector = embed_texts([standalone_query])[0]
    qs = Chunk.objects.filter(
        tenant=tenant,
        workspace=workspace,
        embedding__isnull=False,
        document__status=Document.STATUS_READY,
    ).select_related('document')
    if document_id:
        qs = qs.filter(document_id=document_id)

    candidate_count = max(top_k * 6, 24)
    vector_candidates = list(qs.annotate(distance=CosineDistance('embedding', query_vector)).order_by('distance')[:candidate_count])

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
        blended_score, relevance, lexical = chunk_relevance_score(standalone_query, candidate)
        candidate.relevance_score = relevance
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
                workspace=workspace,
                document_id=best_candidate.document_id,
                document__status=Document.STATUS_READY,
                chunk_index__in=neighbor_indexes,
            )
            .select_related('document')
            .order_by('chunk_index')
        )
        for chunk in local_expansion:
            if not hasattr(chunk, 'distance'):
                chunk.distance = getattr(best_candidate, 'distance', None)
            if not hasattr(chunk, 'relevance_score'):
                blended_score, relevance, lexical = chunk_relevance_score(standalone_query, chunk)
                chunk.relevance_score = relevance
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

    RetrievalLog.objects.create(
        tenant=tenant,
        workspace=workspace,
        query_text=query,
        top_k=top_k,
        result_count=len(results),
        latency_ms=0,
        metadata_json={
            'mode': 'two_pass_hybrid_local_expansion',
            'document_id': document_id,
            'candidate_count': candidate_count,
            'vector_candidate_count': len(vector_candidates),
            'lexical_candidate_count': len(lexical_candidates),
            'merged_candidate_count': len(broad_candidates),
            'standalone_query': standalone_query,
            'best_document_id': getattr(best_candidate, 'document_id', None),
            'best_chunk_index': getattr(best_candidate, 'chunk_index', None),
            'local_window': local_window if best_candidate and not document_id else 0,
            'local_expansion_count': len(local_expansion),
            'document_scores': {str(doc_id): score for doc_id, score in doc_scores.items()},
        },
    )
    return results


def retrieve_facts(*, tenant, workspace, query, top_k=8, document_id=None):
    query_tokens = tokenize_query(query)
    facts = ExtractedFact.objects.filter(
        tenant=tenant,
        workspace=workspace,
        document__status=Document.STATUS_READY,
    ).select_related('document', 'chunk')
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


def build_context_blocks(results, facts=None):
    blocks = []
    for idx, fact in enumerate(facts or [], start=1):
        blocks.append(
            f'[Fact {idx}] {fact.document.filename} · {fact.fact_type} · score={float(getattr(fact, "match_score", 0.0)):.4f}\n'
            f'{fact.label + ": " if fact.label else ""}{fact.value_text}'
        )
    source_offset = len(facts or [])
    for idx, row in enumerate(results, start=1):
        blocks.append(
            f'[Source {idx + source_offset}] {row.document.filename} · chunk {row.chunk_index} · distance={float(getattr(row, "distance", 0.0)):.4f}\n{row.text}'
        )
    return blocks


def answer_question(*, tenant, workspace, query, top_k=5, document_id=None):
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
    answer = answer_with_context(query, context_blocks) if context_blocks else 'I could not find relevant document context for that question yet.'
    return answer, results
