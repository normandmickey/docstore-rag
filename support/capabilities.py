from retrieval.service import answer_question, shipping_answer_payload

from .reply_result import SupportReplyResult


SHIPPING_HINTS = [
    'package',
    'tracking',
    'shipment',
    'fedex',
    'ups',
    'usps',
    'where is my order',
    'delivery',
    'delivered',
    'in transit',
    'tracking number',
]

NO_ANSWER_HINTS = [
    'i do not know based on the provided documents',
    'i do not know based on the documents provided',
    'i do not know based on the documents you provided',
    'i do not know based on the documents you shared',
    'i could not find relevant document context',
    'the answer is not found in the context',
    'the documents you provided do not contain',
    'the documents you shared do not contain',
    'i do not have enough information in the documents',
    'i do not have enough information in the documents you provided',
    'i am not sure based on the documents',
    'i’m not sure based on the documents',
    'i am not sure from the documents',
    'i’m not sure from the documents',
    'i am not aware of any',
    'i’m not aware of any',
    'none of the excerpts mention',
    'none of the excerpts or facts mention',
    'none of the provided excerpts discuss',
    'none of the provided documents address',
    'does not address',
    'no specific mention of',
    'sources: none',
    'i do not know',
]


def decide_support_capability(*, tenant, channel: str, user_text: str, subject: str = '') -> str:
    text = f'{subject}\n{user_text}'.strip().lower()
    if any(token in text for token in SHIPPING_HINTS):
        return 'shipping'
    return 'knowledge'


def try_shipping_capability(*, tenant, query: str, limit: int = 3) -> SupportReplyResult:
    payload = shipping_answer_payload(
        tenant=tenant,
        query=query,
        limit=limit,
    )

    if payload is None:
        return SupportReplyResult(
            mode='shipping',
            handled=False,
            should_reply=False,
            reply_text='',
            confidence=0.0,
            capability_metadata={'capability': 'shipping', 'matched': False},
        )

    answer_text = (payload.get('answer') or '').strip()
    sources = payload.get('sources') or []

    return SupportReplyResult(
        mode='shipping',
        handled=bool(answer_text),
        should_reply=bool(answer_text),
        reply_text=answer_text,
        confidence=0.9 if answer_text else 0.0,
        sources=sources,
        capability_metadata={
            'capability': 'shipping',
            'matched': True,
            'shipping_lookup': bool(payload.get('shipping_lookup')),
            'raw_payload': payload,
        },
    )


def try_knowledge_capability(*, tenant, workspace, query: str, top_k: int = 5, document_id=None) -> SupportReplyResult:
    if workspace is None:
        return SupportReplyResult(
            mode='knowledge',
            handled=False,
            should_reply=False,
            reply_text='',
            confidence=0.0,
            capability_metadata={
                'capability': 'knowledge',
                'reason': 'missing_workspace',
            },
        )

    answer, results = answer_question(
        tenant=tenant,
        workspace=workspace,
        query=query,
        top_k=top_k,
        document_id=document_id,
    )

    if isinstance(answer, dict):
        answer_text = (answer.get('answer') or '').strip()
        sources = answer.get('sources') or []
        retrieval_metadata = {
            'answer_payload': answer,
            'result_count': len(results or []),
            'results': results or [],
        }
    else:
        answer_text = (answer or '').strip()
        sources = []
        retrieval_metadata = {
            'result_count': len(results or []),
            'results': results or [],
        }

    lowered = answer_text.lower()
    no_answer = not answer_text or any(hint in lowered for hint in NO_ANSWER_HINTS)
    if no_answer:
        return SupportReplyResult(
            mode='knowledge',
            handled=False,
            should_reply=False,
            reply_text='',
            confidence=0.0,
            sources=sources,
            retrieval_metadata=retrieval_metadata,
            capability_metadata={'capability': 'knowledge', 'no_answer_detected': True},
        )

    return SupportReplyResult(
        mode='knowledge',
        handled=True,
        should_reply=True,
        reply_text=answer_text,
        confidence=0.75,
        sources=sources,
        retrieval_metadata=retrieval_metadata,
        capability_metadata={'capability': 'knowledge'},
    )
