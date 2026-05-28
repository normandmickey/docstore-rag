from openai import OpenAI
from django.conf import settings


def get_openai_client():
    kwargs = {'api_key': settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        kwargs['base_url'] = settings.OPENAI_BASE_URL
    return OpenAI(**kwargs)


EMBED_BATCH_SIZE = 128


def embed_texts(texts, model=None):
    texts = [text for text in (texts or []) if text]
    if not texts:
        return []

    client = get_openai_client()
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        response = client.embeddings.create(
            model=model or settings.DEFAULT_EMBEDDING_MODEL,
            input=batch,
        )
        vectors.extend(item.embedding for item in response.data)
    return vectors


def rewrite_question(question, chat_history=None, model=None):
    client = get_openai_client()
    history_text = ''
    if chat_history:
        history_lines = []
        for item in chat_history:
            role = item.get('role', 'user')
            text = (item.get('content') or '').strip()
            if text:
                history_lines.append(f'{role}: {text}')
        if history_lines:
            history_text = '\n'.join(history_lines)

    response = client.responses.create(
        model=model or getattr(settings, 'DEFAULT_CHAT_MODEL', 'gpt-4.1-mini'),
        input=[
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'Given a chat history and a follow-up question, rewrite the follow-up question into a standalone question. '
                            'Do not answer the question. If no rewrite is needed, return the original question.'
                        ),
                    }
                ],
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': f'Chat history:\n{history_text or "(none)"}\n\nQuestion:\n{question}',
                    }
                ],
            },
        ],
    )
    return (response.output_text or question).strip()


def answer_with_context(question, context_blocks, model=None):
    client = get_openai_client()
    joined_context = "\n\n".join(context_blocks)
    response = client.responses.create(
        model=model or getattr(settings, 'DEFAULT_CHAT_MODEL', 'gpt-4.1-mini'),
        input=[
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'You are answering questions using only the provided document context. '
                            'Do not make up facts and do not extend beyond the context. '
                            'If the answer is not found in the context, say you do not know based on the provided documents. '
                            'If the context clearly contains a list or enumerated answer, reproduce it as a concise bullet list. '
                            'End with a short Sources section that references the provided source labels.'
                        ),
                    }
                ],
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': f'Question:\n{question}\n\nContext:\n{joined_context}',
                    }
                ],
            },
        ],
    )
    return response.output_text
