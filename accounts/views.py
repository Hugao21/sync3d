from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .forms import CadastroForm
from .grupos import PROJETISTAS, obter_grupo


def signup(request):
    """Cadastro de novos usuários. Toda conta nova é de Projetista."""
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.groups.add(obter_grupo(PROJETISTAS))
            login(request, user)
            messages.success(request, f'Bem-vindo(a), {user.first_name}! '
                                      f'Comece cadastrando um projeto.')
            return HttpResponseRedirect(reverse('impressao:projetos'))
    else:
        form = CadastroForm()
    return render(request, 'accounts/signup.html', {'form': form})
