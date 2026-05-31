import json

from django.core.management.base import BaseCommand

from chatbots.forms import PLATFORM_DEFINITION_PRESETS
from chatbots.models import ChatbotDefinition


class Command(BaseCommand):
    help = 'Backfill blank chatbot definition fields from platform presets.'

    def add_arguments(self, parser):
        parser.add_argument('--definition-id', type=int, default=0)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        definition_id = int(options.get('definition_id') or 0)
        apply_changes = bool(options.get('apply'))

        qs = ChatbotDefinition.objects.select_related('integration').order_by('id')
        if definition_id:
            qs = qs.filter(id=definition_id)

        updated = 0
        for definition in qs:
            preset = PLATFORM_DEFINITION_PRESETS.get(getattr(definition.integration, 'platform', None)) or {}
            if not preset:
                continue
            changed_fields = []
            for field_name, preset_value in preset.items():
                current_value = getattr(definition, field_name)
                if current_value not in (None, '', {}):
                    continue
                if apply_changes:
                    if isinstance(preset_value, dict):
                        setattr(definition, field_name, json.loads(json.dumps(preset_value)))
                    else:
                        setattr(definition, field_name, preset_value)
                changed_fields.append(field_name)
            if not changed_fields:
                continue
            self.stdout.write(f"{'APPLY' if apply_changes else 'DRY'} definition #{definition.id} ({definition.name}) -> {', '.join(changed_fields)}")
            if apply_changes:
                definition.save(update_fields=changed_fields + ['updated_at'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Updated: {updated}" if apply_changes else 'Dry run complete.'))
