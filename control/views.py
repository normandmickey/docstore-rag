from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.text import slugify

from .forms import SignUpForm
from .models import Tenant, TenantMembership, Workspace


class AppLoginView(LoginView):
    template_name = 'auth/login.html'
    redirect_authenticated_user = True


def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect('login')


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        base = slugify(user.username) or f'user-{user.id}'
        tenant_slug = base
        i = 2
        while Tenant.objects.filter(slug=tenant_slug).exists():
            tenant_slug = f'{base}-{i}'
            i += 1
        tenant = Tenant.objects.create(name=f"{user.username}'s Workspace", slug=tenant_slug)
        workspace = Workspace.objects.create(tenant=tenant, name='Default Workspace', slug='default')
        TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)
        login(request, user)
        request.session['current_tenant_id'] = tenant.id
        request.session['current_workspace_id'] = workspace.id
        return redirect('dashboard')
    return render(request, 'auth/signup.html', {'form': form})


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    memberships = TenantMembership.objects.select_related('tenant').filter(user=request.user)
    current_tenant_id = request.session.get('current_tenant_id')
    current_workspace_id = request.session.get('current_workspace_id')
    return render(
        request,
        'dashboard.html',
        {
            'memberships': memberships,
            'current_tenant_id': current_tenant_id,
            'current_workspace_id': current_workspace_id,
        },
    )
