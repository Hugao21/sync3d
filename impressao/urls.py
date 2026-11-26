from django.urls import path

from . import views

app_name = 'impressao'
urlpatterns = [
    path('', views.home, name='home'),
    path('painel/', views.painel, name='painel'),

    # Projetista
    path('projetos/', views.ProjetoListView.as_view(), name='projetos'),
    path('projetos/novo/', views.ProjetoCreateView.as_view(), name='projeto_novo'),
    path('projetos/<int:pk>/', views.ProjetoDetailView.as_view(), name='projeto'),
    path('projetos/<int:pk>/editar/', views.ProjetoUpdateView.as_view(), name='projeto_editar'),
    path('projetos/<int:pk>/remover/', views.ProjetoDeleteView.as_view(), name='projeto_remover'),
    path('projetos/<int:projeto_id>/pecas/nova/', views.PecaCreateView.as_view(), name='peca_nova'),
    path('pecas/<int:pk>/editar/', views.PecaUpdateView.as_view(), name='peca_editar'),
    path('pecas/<int:pk>/remover/', views.PecaDeleteView.as_view(), name='peca_remover'),
    path('agendar/', views.agendar, name='agendar'),
    path('minhas-impressoes/', views.minhas_impressoes, name='minhas_impressoes'),
    path('minhas-impressoes/<int:agendamento_id>/', views.detalhe_agendamento, name='agendamento'),
    path('minhas-impressoes/<int:agendamento_id>/cancelar/', views.cancelar_agendamento, name='cancelar'),
    path('historico/', views.historico, name='historico'),
    path('notificacoes/', views.notificacoes, name='notificacoes'),

    # Administrador
    path('filas/', views.gestao_filas, name='filas'),
    path('filas/<int:agendamento_id>/aprovar/', views.aprovar, name='aprovar'),
    path('filas/<int:agendamento_id>/mover/<str:direcao>/', views.mover, name='mover'),
    path('filas/<int:agendamento_id>/finalizar/<str:resultado>/', views.finalizar, name='finalizar'),
    path('filas/<int:agendamento_id>/desbloquear/', views.desbloquear, name='desbloquear'),
    path('impressoras/', views.ImpressoraListView.as_view(), name='impressoras'),
    path('impressoras/nova/', views.ImpressoraCreateView.as_view(), name='impressora_nova'),
    path('impressoras/<int:pk>/editar/', views.ImpressoraUpdateView.as_view(), name='impressora_editar'),
    path('impressoras/<int:impressora_id>/atividade/', views.alternar_atividade, name='impressora_atividade'),
    path('impressoras/<int:impressora_id>/paralisar/', views.paralisar, name='paralisar'),
    path('impressoras/<int:impressora_id>/liberar/', views.liberar, name='liberar'),
    path('estoque/', views.estoque, name='estoque'),
    path('estoque/novo/', views.FilamentoCreateView.as_view(), name='filamento_novo'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/consolidar/', views.consolidar, name='consolidar'),
]
