"""Grupos de usuários do Sync3D e as permissões de cada perfil."""
from django.contrib.auth.models import Group, Permission

PROJETISTAS = 'Projetistas'
ADMINISTRADORES = 'Administradores'

PERMISSOES_PROJETISTA = [
    'add_projeto', 'change_projeto', 'delete_projeto', 'view_projeto',
    'add_peca', 'change_peca', 'delete_peca', 'view_peca',
    'add_agendamento', 'view_agendamento',
    'view_notificacao', 'change_notificacao',
    'view_filamento', 'view_impressora',
]

# O Administrador gerencia tudo, mas não agenda impressões em nome de projetistas.
PERMISSOES_ADMIN_EXCLUIDAS = ['add_projeto', 'add_peca', 'add_agendamento']


def obter_grupo(nome):
    """Retorna o grupo; se ele não existir, cria com as permissões do perfil."""
    grupo, criado = Group.objects.get_or_create(name=nome)
    if criado:
        permissoes = Permission.objects.filter(content_type__app_label='impressao')
        if nome == PROJETISTAS:
            permissoes = permissoes.filter(codename__in=PERMISSOES_PROJETISTA)
        else:
            permissoes = permissoes.exclude(codename__in=PERMISSOES_ADMIN_EXCLUIDAS)
        grupo.permissions.set(permissoes)
    return grupo
