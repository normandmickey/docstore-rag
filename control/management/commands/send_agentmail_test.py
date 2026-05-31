from django.core.management.base import BaseCommand, CommandError

from control.agentmail import AgentMailClient, AgentMailError


class Command(BaseCommand):
    help = 'Send a test email using the configured AgentMail inbox.'

    def add_arguments(self, parser):
        parser.add_argument('to_email')
        parser.add_argument('--subject', default='Docstore AgentMail test')
        parser.add_argument('--text', default='This is a test email sent from Docstore via AgentMail.')

    def handle(self, *args, **options):
        try:
            client = AgentMailClient()
            result = client.send_message(
                to=options['to_email'],
                subject=options['subject'],
                text=options['text'],
                html=f'<p>{options["text"]}</p>',
            )
        except AgentMailError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f'AgentMail test sent: {result}'))
