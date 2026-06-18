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
        parser.add_argument(
            '--format',
            default='text',
            choices=['text', 'json'],
            help='Output format for results.',
        )
        parser.add_argument(
            '--save',
            default='',
            help='Optional path to save the report JSON relative to repo root.',
        )

    def handle(self, *args, **options):
        repo_root = Path(__file__).resolve().parents[3]
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
        report_rows = []

        for row in rows:
            workspace_slug = options['workspace'] or row.get('workspace_slug') or ''
            workspace = Workspace.objects.filter(slug=workspace_slug).select_related('tenant').first()
            if workspace is None:
                skip_row = {
                    'id': row.get('id'),
                    'workspace_slug': workspace_slug,
                    'status': 'skipped',
                    'reason': 'workspace_not_found',
                }
                report_rows.append(skip_row)
                if options['format'] == 'text':
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

            report_row = {
                'id': row.get('id'),
                'workspace_slug': workspace_slug,
                'question': row['question'],
                'expected_mode': expected_mode,
                'result_mode': result.mode,
                'should_handoff': bool(result.should_handoff),
                'handoff_reason': result.handoff_reason,
                'mode_match': mode_ok,
                'handoff_match': handoff_ok,
                'answer': result.reply_text,
                'source_count': len(result.sources or []),
                'status': 'ok' if mode_ok else 'miss',
            }
            report_rows.append(report_row)

            if options['format'] == 'text':
                self.stdout.write(
                    f"[{ 'OK' if mode_ok else 'MISS' }] {row.get('id')} "
                    f"expected={expected_mode} got_mode={result.mode} handoff={result.should_handoff}"
                )
                self.stdout.write(f"  Q: {row['question']}")
                self.stdout.write(f"  A: {result.reply_text}")
                if result.sources:
                    self.stdout.write(f"  Sources: {len(result.sources)}")
                self.stdout.write('')

        summary = {
            'eval_file': str(eval_path.relative_to(repo_root)),
            'total_ran': total,
            'mode_matches': mode_matches,
            'handoff_matches': handoff_matches,
            'rows': report_rows,
        }

        if options['save']:
            save_path = repo_root / options['save']
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')

        if options['format'] == 'json':
            self.stdout.write(json.dumps(summary, indent=2))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Evals complete. Ran {total}. Mode matches: {mode_matches}/{total}. '
                f'Handoff matches: {handoff_matches}/{total}.'
            ))
            if options['save']:
                self.stdout.write(self.style.SUCCESS(f"Saved report to {options['save']}"))
