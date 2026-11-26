from .models import Notificacao


def notificacoes(request):
    """Quantidade de notificações não lidas, exibida no cabeçalho."""
    if not request.user.is_authenticated:
        return {}
    nao_lidas = Notificacao.objects.filter(
        agendamento__peca__projeto__projetista=request.user, lida=False).count()
    return {'notificacoes_nao_lidas': nao_lidas}
