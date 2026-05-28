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
