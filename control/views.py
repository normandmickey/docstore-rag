from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import SignUpForm


class AppLoginView(LoginView):
    template_name = 'auth/login.html'
    redirect_authenticated_user = True


class AppLogoutView(LogoutView):
    next_page = reverse_lazy('login')


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('home')
    return render(request, 'auth/signup.html', {'form': form})
