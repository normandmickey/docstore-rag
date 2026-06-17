import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from control.models import Workspace
from support.orchestration import handle_support_request


class Command(BaseCommand):
    help = 'Run lightweight retrieval/support evals from a JSONL file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default='evals/support_knowledge_eval.jsonl',
            help='Path to JSONL eval file relative to repo root.',
        )
        parser.add_argument(
            '--workspace',
            default='',
            help='Optional workspace slug override for all evals.',
        )

    def handle(self, *args, **options):
        repo_root = Path(__file__).resolve().parents[4]
        eval_path = repo_root / options['file']
        if not eval_path.exists():
            raise CommandError(f'Eval file not found: {eval_path}')

        rows = []
        with eval_path.open('r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))

        if not rows:
            raise CommandError(f'No eval rows found in {eval_path}')

        total = 0
        mode_matches = 0
        handoff_matches = 0

        for row in rows:
            workspace_slug = options['workspace'] or row.get('workspace_slug') or ''
            workspace = Workspace.objects.filter(slug=workspace_slug).select_related('tenant').first()
            if workspace is None:
                self.stdout.write(self.style.WARNING(f"[SKIP] {row.get('id')} workspace not found: {workspace_slug}"))
                continue

            expected_mode = row.get('expected_mode') or 'knowledge'
            result = handle_support_request(
                tenant=workspace.tenant,
                workspace=workspace,
                channel='api_chat',
                conversation=None,
                contact=None,
                user_text=row['question'],
                subject='',
                metadata={
                    'surface': 'eval_runner',
                    'eval_id': row.get('id'),
                },
            )

            total += 1
            mode_ok = (
                (expected_mode == 'no_answer' and result.should_handoff)
                or (expected_mode != 'no_answer' and result.mode == expected_mode)
            )
            handoff_ok = ((expected_mode == 'no_answer') == bool(result.should_handoff))
            if mode_ok:
                mode_matches += 1
            if handoff_ok:
                handoff_matches += 1

            self.stdout.write(
                f"[{ 'OK' if mode_ok else 'MISS' }] {row.get('id')} "
                f"expected={expected_mode} got_mode={result.mode} handoff={result.should_handoff}"
            )
            self.stdout.write(f"  Q: {row['question']}")
            self.stdout.write(f"  A: {result.reply_text}")
            if result.sources:
                self.stdout.write(f"  Sources: {len(result.sources)}")
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS(
            f'Evals complete. Ran {total}. Mode matches: {mode_matches}/{total}. '
            f'Handoff matches: {handoff_matches}/{total}.'
        ))
