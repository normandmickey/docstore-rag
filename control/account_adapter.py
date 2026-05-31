from allauth.account.adapter import DefaultAccountAdapter
from django.template.loader import render_to_string

from control.agentmail import AgentMailClient


class DocstoreAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        to = [email] if isinstance(email, str) else list(email)
        subject = render_to_string(f'{template_prefix}_subject.txt', context)
        subject = ' '.join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)

        bodies = {}
        html_ext = 'html'
        for ext in [html_ext, 'txt']:
            try:
                template_name = f'{template_prefix}_message.{ext}'
                bodies[ext] = render_to_string(template_name, context).strip()
            except Exception:
                continue

        text = bodies.get('txt', '')
        html = bodies.get(html_ext, '')
        AgentMailClient().send_message(
            to=to,
            subject=subject,
            text=text,
            html=html,
        )
