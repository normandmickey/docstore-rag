import logging

from django.conf import settings

from control.agentmail import AgentMailClient, AgentMailError

logger = logging.getLogger(__name__)


def _app_base_url():
    allowed = getattr(settings, 'ALLOWED_HOSTS', []) or []
    primary = next((host for host in allowed if host and host not in {'localhost', '127.0.0.1'}), '')
    if primary:
        return f'https://{primary}'
    return 'https://docstore.oddsmith.net'


def send_invite_email(*, to_email, signup_url, tenant_name='', workspace_name='', role='member', note='', invited_by=''):
    if not to_email:
        return None
    subject = f'You are invited to Docstore{f" · {tenant_name}" if tenant_name else ""}'
    text_lines = [
        'You have been invited to Docstore.',
        '',
    ]
    if tenant_name:
        text_lines.append(f'Tenant: {tenant_name}')
    if workspace_name:
        text_lines.append(f'Workspace: {workspace_name}')
    if role:
        text_lines.append(f'Role: {role}')
    if invited_by:
        text_lines.append(f'Invited by: {invited_by}')
    if note:
        text_lines.extend(['', f'Note: {note}'])
    text_lines.extend(['', f'Accept invite: {signup_url}', '', f'Docstore: {_app_base_url()}'])
    html = (
        '<p>You have been invited to <strong>Docstore</strong>.</p>'
        + (f'<p><strong>Tenant:</strong> {tenant_name}</p>' if tenant_name else '')
        + (f'<p><strong>Workspace:</strong> {workspace_name}</p>' if workspace_name else '')
        + (f'<p><strong>Role:</strong> {role}</p>' if role else '')
        + (f'<p><strong>Invited by:</strong> {invited_by}</p>' if invited_by else '')
        + (f'<p><strong>Note:</strong> {note}</p>' if note else '')
        + f'<p><a href="{signup_url}">Accept your invite</a></p>'
        + f'<p>Docstore: <a href="{_app_base_url()}">{_app_base_url()}</a></p>'
    )
    try:
        return AgentMailClient().send_message(
            to=to_email,
            subject=subject,
            text='\n'.join(text_lines),
            html=html,
        )
    except AgentMailError:
        raise
    except Exception as exc:
        raise AgentMailError(str(exc)) from exc


def send_support_ack_email(*, to_email, tenant_name='', subject_hint='', conversation_id=None):
    if not to_email:
        return None
    subject = f'We received your message{f" · {tenant_name}" if tenant_name else ""}'
    text_lines = [
        'Thanks — we received your support message.',
        'Someone will review it and follow up soon.',
    ]
    if subject_hint:
        text_lines.extend(['', f'Subject: {subject_hint}'])
    if conversation_id:
        text_lines.append(f'Reference: support-{conversation_id}')
    html = (
        '<p>Thanks — we received your support message.</p>'
        '<p>Someone will review it and follow up soon.</p>'
        + (f'<p><strong>Subject:</strong> {subject_hint}</p>' if subject_hint else '')
        + (f'<p><strong>Reference:</strong> support-{conversation_id}</p>' if conversation_id else '')
    )
    try:
        return AgentMailClient().send_message(
            to=to_email,
            subject=subject,
            text='\n'.join(text_lines),
            html=html,
        )
    except AgentMailError:
        raise
    except Exception as exc:
        raise AgentMailError(str(exc)) from exc
