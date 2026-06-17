from .capabilities import decide_support_capability, try_knowledge_capability, try_shipping_capability
from .reply_composer import compose_acknowledgement, compose_support_reply
from .reply_result import SupportReplyResult


def handle_support_request(*, tenant, workspace, channel: str, conversation, contact, user_text: str, subject: str = '', metadata: dict | None = None) -> SupportReplyResult:
    metadata = metadata or {}
    query = (user_text or '').strip() or (subject or '').strip()

    if not query:
        ack = compose_acknowledgement(channel=channel, subject=subject)
        return SupportReplyResult(
            mode='ack',
            handled=False,
            should_reply=True,
            reply_text=ack,
            confidence=0.1,
            capability_metadata={
                'reason': 'empty_query',
                'channel': channel,
                'metadata': metadata,
            },
            should_handoff=True,
            handoff_reason='empty_query',
        )

    capability = decide_support_capability(
        tenant=tenant,
        channel=channel,
        user_text=user_text,
        subject=subject,
    )

    if capability == 'shipping':
        shipping_result = try_shipping_capability(
            tenant=tenant,
            query=query,
            limit=3,
        )
        if shipping_result.handled and shipping_result.should_reply:
            shipping_result.reply_text = compose_support_reply(
                result=shipping_result,
                channel=channel,
                subject=subject,
            )
            shipping_result.capability_metadata = {
                **(shipping_result.capability_metadata or {}),
                'channel': channel,
                'metadata': metadata,
            }
            return shipping_result

    knowledge_result = try_knowledge_capability(
        tenant=tenant,
        workspace=workspace,
        query=query,
        top_k=5,
    )
    if knowledge_result.handled and knowledge_result.should_reply:
        knowledge_result.reply_text = compose_support_reply(
            result=knowledge_result,
            channel=channel,
            subject=subject,
        )
        knowledge_result.capability_metadata = {
            **(knowledge_result.capability_metadata or {}),
            'channel': channel,
            'metadata': metadata,
        }
        return knowledge_result

    ack = compose_acknowledgement(channel=channel, subject=subject)
    return SupportReplyResult(
        mode='ack',
        handled=False,
        should_reply=True,
        reply_text=ack,
        confidence=0.2,
        sources=knowledge_result.sources,
        retrieval_metadata=knowledge_result.retrieval_metadata,
        capability_metadata={
            'capability_attempt': capability,
            'channel': channel,
            'fallback': 'acknowledgement',
            'metadata': metadata,
        },
        should_handoff=True,
        handoff_reason='no_confident_auto_answer',
    )
