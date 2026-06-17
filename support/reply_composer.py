from .reply_result import SupportReplyResult


def compose_support_reply(*, result: SupportReplyResult, channel: str, subject: str = '') -> str:
    body = (result.reply_text or '').strip()
    if not body:
        return ''

    if result.mode == 'shipping':
        if channel == 'email':
            return f"Thanks for reaching out.\n\n{body}"
        return body

    if result.mode == 'knowledge':
        if channel == 'email':
            return f"Thanks for your email.\n\n{body}"
        return body

    return body


def compose_acknowledgement(*, channel: str, subject: str = '') -> str:
    if channel == 'email':
        label = subject or 'your support request'
        return (
            f"Thanks for your email.\n\n"
            f"I received your message about '{label}' and opened it in support. "
            f"We’ll follow up shortly."
        )

    if channel == 'sms':
        return 'Got it — we received your message and will follow up shortly.'

    if channel == 'chatbot':
        return 'I’m not confident I can answer that from the current knowledge yet, so someone can follow up if needed.'

    if channel == 'voice':
        return 'We received your request and will follow up shortly.'

    if channel == 'api_chat':
        return 'I could not find a confident answer in the current document context.'

    if channel == 'dashboard_chat':
        return 'I could not find a confident answer in the current workspace documents yet.'

    return 'We received your request and will follow up shortly.'
