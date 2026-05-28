from pgvector.django import CosineDistance

from audit.models import RetrievalLog
from documents.models import Chunk, Document
from providers import answer_with_context, embed_texts


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
    results = list(qs.annotate(distance=CosineDistance('embedding', query_vector)).order_by('distance')[:top_k])

    RetrievalLog.objects.create(
        tenant=tenant,
        workspace=workspace,
        query_text=query,
        top_k=top_k,
        result_count=len(results),
        latency_ms=0,
        metadata_json={
            'mode': 'vector_search',
            'document_id': document_id,
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
