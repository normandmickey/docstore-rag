from openai import OpenAI
from django.conf import settings


def get_openai_client():
    kwargs = {'api_key': settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        kwargs['base_url'] = settings.OPENAI_BASE_URL
    return OpenAI(**kwargs)


def embed_texts(texts, model=None):
    client = get_openai_client()
    response = client.embeddings.create(
        model=model or settings.DEFAULT_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


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
                            'Answer the user using only the provided document context when possible. '
                            'Be concise and practical. If the answer is not fully supported by the context, '
                            'say what is missing. End with a short Sources section that references the provided labels.'
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
