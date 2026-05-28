import re

from pgvector.django import CosineDistance

from audit.models import RetrievalLog
from documents.models import Chunk, Document
from providers import answer_with_context, embed_texts


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


def retrieve_chunks(*, tenant, workspace, query, top_k=5, document_id=None):
    query_vector = embed_texts([query])[0]
    qs = Chunk.objects.filter(
        tenant=tenant,
        workspace=workspace,
        embedding__isnull=False,
        document__status=Document.STATUS_READY,
    ).select_related('document')
    if document_id:
        qs = qs.filter(document_id=document_id)

    candidate_count = max(top_k * 4, 12)
    candidates = list(qs.annotate(distance=CosineDistance('embedding', query_vector)).order_by('distance')[:candidate_count])
    scored = []
    for candidate in candidates:
        relevance = 1.0 - float(getattr(candidate, 'distance', 1.0) or 1.0)
        lexical = keyword_score(query, getattr(candidate, 'text', ''))
        blended_score = (0.8 * relevance) + (0.2 * lexical)
        scored.append((blended_score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = [candidate for _score, candidate in scored[:top_k]]

    RetrievalLog.objects.create(
        tenant=tenant,
        workspace=workspace,
        query_text=query,
        top_k=top_k,
        result_count=len(results),
        latency_ms=0,
        metadata_json={
            'mode': 'vector_search_keyword_boost',
            'document_id': document_id,
            'candidate_count': candidate_count,
        },
    )
    return results


def build_context_blocks(results):
    blocks = []
    for idx, row in enumerate(results, start=1):
        blocks.append(
            f'[Source {idx}] {row.document.filename} · chunk {row.chunk_index} · distance={float(getattr(row, "distance", 0.0)):.4f}\n{row.text}'
        )
    return blocks


def answer_question(*, tenant, workspace, query, top_k=5, document_id=None):
    results = retrieve_chunks(
        tenant=tenant,
        workspace=workspace,
        query=query,
        top_k=top_k,
        document_id=document_id,
    )
    context_blocks = build_context_blocks(results)
    answer = answer_with_context(query, context_blocks) if context_blocks else 'I could not find relevant document context for that question yet.'
    return answer, results
