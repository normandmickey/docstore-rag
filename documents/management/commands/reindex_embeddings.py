from django.core.management.base import BaseCommand
from documents.models import Chunk
from providers import embed_texts


class Command(BaseCommand):
    help = 'Reindex all chunk embeddings using the current embedding provider.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=50, help='Number of chunks per batch')
        parser.add_argument('--workspace', type=str, default='', help='Filter by workspace slug')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        qs = Chunk.objects.all()
        if options['workspace']:
            qs = qs.filter(workspace__slug=options['workspace'])

        total = qs.count()
        self.stdout.write(f'Reindexing {total} chunks (batch size: {batch_size})')

        done = 0
        qs = qs.order_by('id')
        while True:
            batch = list(qs[done:done + batch_size])
            if not batch:
                break

            texts = [c.text or '' for c in batch]
            metadata_texts = [c.metadata_text or '' for c in batch]
            question_texts = [c.question_text or '' for c in batch]

            vectors = embed_texts(texts) if any(texts) else []
            metadata_vectors = embed_texts(metadata_texts) if any(metadata_texts) else []
            question_vectors = embed_texts(question_texts) if any(question_texts) else []

            for idx, chunk in enumerate(batch):
                chunk.embedding = vectors[idx] if idx < len(vectors) else None
                chunk.metadata_embedding = metadata_vectors[idx] if idx < len(metadata_vectors) else None
                chunk.question_embedding = question_vectors[idx] if idx < len(question_vectors) else None

            Chunk.objects.bulk_update(
                batch, ['embedding', 'metadata_embedding', 'question_embedding']
            )
            done += len(batch)
            self.stdout.write(f'  {done}/{total} chunks reindexed')

        self.stdout.write(self.style.SUCCESS(f'Done. Reindexed {done} chunks.'))