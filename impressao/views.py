from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from . import sistema
from .forms import (AgendamentoForm, DashboardFiltroForm, FilamentoForm,
                    HistoricoFiltroForm, ImpressoraForm, PecaForm, ProjetoForm,
                    ReposicaoForm)
from .models import (Agendamento, ConsolidacaoPeriodica, ConsumoFilamento,
                     Filamento, Impressora, Notificacao, Peca, Projeto,
                     ReposicaoEstoque)

PERM_PROJETISTA = 'impressao.add_agendamento'
PERM_ADMIN = 'impressao.change_impressora'


def avisar_bloqueados(request, bloqueados):
    """UC09, fluxo alternativo: avisa o Administrador sobre estoque insuficiente."""
    for item in bloqueados:
        messages.warning(
            request,
            f'Agendamento #{item.id} ({item.peca.nome}) foi bloqueado: '
            f'estoque insuficiente de filamento.')


# ---------------------------------------------------------------- Públicas

def home(request):
    impressoras = Impressora.objects.annotate(
        tamanho_fila=Count('agendamentos', filter=Q(
            agendamentos__status__in=[Agendamento.NA_FILA,
                                      Agendamento.IMPRIMINDO]))).order_by('modelo')
    destaque = (impressoras.filter(status=Impressora.IMPRIMINDO).first()
                or impressoras.first())
    fila = []
    if destaque:
        fila = destaque.fila().select_related(
            'peca__projeto__projetista').prefetch_related(
            'consumos__filamento')[:3]
    context = {
        'impressoras': impressoras,
        'impressora_destaque': destaque,
        'fila_destaque': fila,
    }
    return render(request, 'impressao/home.html', context)


@login_required
def painel(request):
    """Destino após o login: cada perfil vai para a sua tela principal."""
    if request.user.has_perm(PERM_ADMIN):
        return HttpResponseRedirect(reverse('impressao:filas'))
    return HttpResponseRedirect(reverse('impressao:minhas_impressoes'))


# ---------------------------------------------------------------- Projetista: projetos e peças

class ProjetistaMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = PERM_PROJETISTA


class ProjetoListView(ProjetistaMixin, generic.ListView):
    template_name = 'impressao/projetos.html'
    context_object_name = 'projeto_list'

    def get_queryset(self):
        return Projeto.objects.filter(projetista=self.request.user).annotate(
            num_pecas=Count('pecas', distinct=True)).order_by('-data_criacao')


class ProjetoDetailView(ProjetistaMixin, generic.DetailView):
    template_name = 'impressao/projeto_detail.html'

    def get_queryset(self):
        return Projeto.objects.filter(projetista=self.request.user)


class ProjetoCreateView(ProjetistaMixin, generic.CreateView):
    model = Projeto
    form_class = ProjetoForm
    template_name = 'impressao/form.html'
    extra_context = {'titulo': 'Novo projeto', 'eyebrow': 'Projetos'}

    def form_valid(self, form):
        form.instance.projetista = self.request.user
        messages.success(self.request, 'Projeto criado.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('impressao:projeto', args=(self.object.id, ))


class ProjetoUpdateView(ProjetistaMixin, generic.UpdateView):
    form_class = ProjetoForm
    template_name = 'impressao/form.html'
    extra_context = {'titulo': 'Editar projeto', 'eyebrow': 'Projetos'}

    def get_queryset(self):
        return Projeto.objects.filter(projetista=self.request.user)

    def get_success_url(self):
        return reverse('impressao:projeto', args=(self.object.id, ))


class ProjetoDeleteView(ProjetistaMixin, generic.DeleteView):
    template_name = 'impressao/confirmar_remocao.html'
    success_url = reverse_lazy('impressao:projetos')

    def get_queryset(self):
        return Projeto.objects.filter(projetista=self.request.user)


class PecaCreateView(ProjetistaMixin, generic.CreateView):
    model = Peca
    form_class = PecaForm
    template_name = 'impressao/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.projeto = get_object_or_404(Projeto, pk=kwargs['projeto_id'],
                                         projetista=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova peça'
        context['eyebrow'] = self.projeto.nome
        return context

    def form_valid(self, form):
        form.instance.projeto = self.projeto
        messages.success(self.request, 'Peça cadastrada.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('impressao:projeto', args=(self.projeto.id, ))


class PecaUpdateView(ProjetistaMixin, generic.UpdateView):
    form_class = PecaForm
    template_name = 'impressao/form.html'
    extra_context = {'titulo': 'Editar peça', 'eyebrow': 'Peças'}

    def get_queryset(self):
        return Peca.objects.filter(projeto__projetista=self.request.user)

    def get_success_url(self):
        return reverse('impressao:projeto', args=(self.object.projeto.id, ))


class PecaDeleteView(ProjetistaMixin, generic.DeleteView):
    template_name = 'impressao/confirmar_remocao.html'

    def get_queryset(self):
        return Peca.objects.filter(projeto__projetista=self.request.user)

    def get_success_url(self):
        return reverse('impressao:projeto', args=(self.object.projeto.id, ))


# ---------------------------------------------------------------- Projetista: agendamentos

@login_required
@permission_required(PERM_PROJETISTA)
def agendar(request):
    """UC01 — Agendamento de impressão."""
    if request.method == 'POST':
        if 'cancelar' in request.POST:
            # Fluxo alternativo a: cancelar volta à tela principal.
            return HttpResponseRedirect(reverse('impressao:minhas_impressoes'))
        form = AgendamentoForm(request.user, request.POST)
        if form.is_valid():
            impressora = form.cleaned_data['impressora']
            ultima = impressora.agendamentos.aggregate(
                maior=Max('posicao_fila'))['maior'] or 0
            agendamento = Agendamento.objects.create(
                peca=form.cleaned_data['peca'],
                impressora=impressora,
                status=Agendamento.NA_FILA,
                posicao_fila=ultima + 1,
            )
            for filamento, quantidade in form.insumos():
                ConsumoFilamento.objects.create(agendamento=agendamento,
                                                filamento=filamento,
                                                quantidade_consumida=quantidade)
            sistema.renumerar_fila(impressora)
            sistema.recalcular_previsoes(impressora)
            messages.success(
                request,
                f'Agendamento enviado para a fila da {impressora.modelo}. '
                f'Aguarde a aprovação do Administrador.')
            return HttpResponseRedirect(reverse('impressao:minhas_impressoes'))
    else:
        form = AgendamentoForm(request.user, initial={
            'peca': request.GET.get('peca')})
    tem_pecas = Peca.objects.filter(projeto__projetista=request.user).exists()
    context = {'form': form, 'tem_pecas': tem_pecas}
    return render(request, 'impressao/agendar.html', context)


@login_required
@permission_required(PERM_PROJETISTA)
def minhas_impressoes(request):
    """UC05 — Acompanhamento de status em tempo real."""
    sistema.processar_impressoes()
    ativos = Agendamento.objects.filter(
        peca__projeto__projetista=request.user,
        status__in=[Agendamento.NA_FILA, Agendamento.IMPRIMINDO,
                    Agendamento.BLOQUEADO],
    ).select_related('peca__projeto', 'impressora').order_by(
        'impressora', 'posicao_fila')
    for item in ativos:
        item.progresso = sistema.progresso(item)
    recentes = Agendamento.objects.filter(
        peca__projeto__projetista=request.user,
        status__in=[Agendamento.CONCLUIDO, Agendamento.FALHA,
                    Agendamento.CANCELADO],
    ).select_related('peca', 'impressora').order_by('-data_solicitacao')[:5]
    context = {'ativos': ativos, 'recentes': recentes}
    return render(request, 'impressao/minhas_impressoes.html', context)


@login_required
@permission_required(PERM_PROJETISTA)
def detalhe_agendamento(request, agendamento_id):
    """UC05 — Detalhes e progresso estimado de um agendamento."""
    sistema.processar_impressoes()
    agendamento = get_object_or_404(
        Agendamento.objects.select_related('peca__projeto', 'impressora'),
        pk=agendamento_id, peca__projeto__projetista=request.user)
    atraso = None
    impressora = agendamento.impressora
    if impressora and impressora.status == Impressora.MANUTENCAO:
        # Fluxo alternativo: impressora em manutenção -> estimativa de atraso.
        atraso = sistema.minutos_inativa(impressora) - impressora.inatividade_min
    fim_previsto = None
    if agendamento.data_inicio_previsto:
        fim_previsto = agendamento.data_inicio_previsto + timedelta(
            minutes=agendamento.peca.tempo_estimado_min)
    context = {
        'agendamento': agendamento,
        'progresso': sistema.progresso(agendamento),
        'fim_previsto': fim_previsto,
        'atraso': atraso,
        'consumos': agendamento.consumos.select_related('filamento'),
        'notificacoes': agendamento.notificacoes.all(),
    }
    return render(request, 'impressao/agendamento_detail.html', context)


@login_required
@permission_required(PERM_PROJETISTA)
def cancelar_agendamento(request, agendamento_id):
    """UC04 — Cancelamento de agendamento."""
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id,
                                    peca__projeto__projetista=request.user)
    if agendamento.status == Agendamento.IMPRIMINDO:
        # Fluxo alternativo a: já em impressão.
        messages.error(request, 'Este agendamento já está sendo impresso e não '
                                'pode ser cancelado. Contate o Administrador.')
        return HttpResponseRedirect(
            reverse('impressao:agendamento', args=(agendamento.id, )))
    if agendamento.status not in (Agendamento.NA_FILA, Agendamento.BLOQUEADO):
        messages.error(request, 'Só é possível cancelar agendamentos na fila.')
        return HttpResponseRedirect(reverse('impressao:minhas_impressoes'))
    if request.method == 'POST':
        agendamento.status = Agendamento.CANCELADO
        agendamento.save(update_fields=['status'])
        if agendamento.impressora:
            sistema.avancar_fila(agendamento.impressora)
        messages.success(request, 'Agendamento cancelado e posição liberada na fila.')
        return HttpResponseRedirect(reverse('impressao:minhas_impressoes'))
    context = {'agendamento': agendamento}
    return render(request, 'impressao/cancelar.html', context)


@login_required
@permission_required(PERM_PROJETISTA)
def historico(request):
    """UC06 — Consulta ao histórico de impressões concluídas."""
    form = HistoricoFiltroForm(request.user, request.GET or None)
    concluidos = Agendamento.objects.filter(
        peca__projeto__projetista=request.user,
        status=Agendamento.CONCLUIDO,
    ).select_related('peca__projeto', 'impressora').prefetch_related(
        'consumos__filamento').order_by('-data_conclusao')
    if form.is_valid():
        if form.cleaned_data['inicio']:
            concluidos = concluidos.filter(
                data_conclusao__date__gte=form.cleaned_data['inicio'])
        if form.cleaned_data['fim']:
            concluidos = concluidos.filter(
                data_conclusao__date__lte=form.cleaned_data['fim'])
        if form.cleaned_data['projeto']:
            concluidos = concluidos.filter(
                peca__projeto=form.cleaned_data['projeto'])
    total = ConsumoFilamento.objects.filter(agendamento__in=concluidos).aggregate(
        total=Sum('quantidade_consumida'))['total'] or 0
    context = {'form': form, 'concluidos': concluidos, 'consumo_total': total}
    return render(request, 'impressao/historico.html', context)


@login_required
def notificacoes(request):
    """Alertas na plataforma gerados pelo UC11."""
    lista = Notificacao.objects.filter(
        agendamento__peca__projeto__projetista=request.user
    ).select_related('agendamento__peca')
    if request.method == 'POST':
        lista.filter(lida=False).update(lida=True)
        return HttpResponseRedirect(reverse('impressao:notificacoes'))
    return render(request, 'impressao/notificacoes.html', {'notificacoes': lista})


# ---------------------------------------------------------------- Administrador: filas

@login_required
@permission_required(PERM_ADMIN)
def gestao_filas(request):
    """UC02 — Gerenciamento de fila e parque de impressoras."""
    sistema.processar_impressoes()
    impressoras = Impressora.objects.exclude(status=Impressora.INATIVA)
    paineis = []
    for impressora in impressoras:
        fila = list(impressora.fila().select_related(
            'peca__projeto__projetista').prefetch_related('consumos__filamento'))
        for item in fila:
            item.progresso = sistema.progresso(item)
        paineis.append({
            'impressora': impressora,
            'fila': fila,
            'inativa_min': sistema.minutos_inativa(impressora),
        })
    pendentes = Agendamento.objects.filter(status=Agendamento.NA_FILA,
                                           aprovado=False).count()
    context = {'paineis': paineis, 'pendentes': pendentes}
    return render(request, 'impressao/filas.html', context)


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def aprovar(request, agendamento_id):
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id,
                                    status=Agendamento.NA_FILA)
    agendamento.aprovado = True
    agendamento.save(update_fields=['aprovado'])
    messages.success(request, f'Agendamento #{agendamento.id} aprovado.')
    avisar_bloqueados(request, sistema.avancar_fila(agendamento.impressora))
    return HttpResponseRedirect(reverse('impressao:filas'))


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def mover(request, agendamento_id, direcao):
    """Reorganiza a prioridade trocando o item com o vizinho da fila."""
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id,
                                    status=Agendamento.NA_FILA)
    impressora = agendamento.impressora
    fila = list(impressora.fila().filter(status=Agendamento.NA_FILA))
    indice = fila.index(agendamento)
    vizinho = indice - 1 if direcao == 'cima' else indice + 1
    if 0 <= vizinho < len(fila):
        outro = fila[vizinho]
        agendamento.posicao_fila, outro.posicao_fila = (outro.posicao_fila,
                                                        agendamento.posicao_fila)
        agendamento.save(update_fields=['posicao_fila'])
        outro.save(update_fields=['posicao_fila'])
        sistema.renumerar_fila(impressora)
        sistema.recalcular_previsoes(impressora)
    return HttpResponseRedirect(reverse('impressao:filas'))


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def finalizar(request, agendamento_id, resultado):
    """Registra conclusão ou falha de uma impressão (dispara UC11)."""
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id,
                                    status=Agendamento.IMPRIMINDO)
    sucesso = resultado == 'concluido'
    bloqueados = sistema.concluir(agendamento, sucesso=sucesso)
    if sucesso:
        messages.success(request, f'Impressão #{agendamento.id} concluída. '
                                  f'Projetista notificado.')
    else:
        messages.warning(request, f'Falha registrada na impressão #{agendamento.id}. '
                                  f'Projetista notificado.')
    avisar_bloqueados(request, bloqueados)
    return HttpResponseRedirect(reverse('impressao:filas'))


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def desbloquear(request, agendamento_id):
    """Devolve um agendamento bloqueado à fila depois da reposição de estoque."""
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id,
                                    status=Agendamento.BLOQUEADO)
    agendamento.status = Agendamento.NA_FILA
    agendamento.save(update_fields=['status'])
    avisar_bloqueados(request, sistema.avancar_fila(agendamento.impressora))
    return HttpResponseRedirect(reverse('impressao:filas'))


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def paralisar(request, impressora_id):
    """UC02, fluxo alternativo: registro de paralisação corretiva."""
    impressora = get_object_or_404(Impressora, pk=impressora_id)
    if impressora.status != Impressora.MANUTENCAO:
        impressora.status = Impressora.MANUTENCAO
        impressora.paralisada_desde = timezone.now()
        impressora.save(update_fields=['status', 'paralisada_desde'])
        messages.warning(request, f'{impressora.modelo} em manutenção: avanço '
                                  f'automático da fila suspenso.')
    return HttpResponseRedirect(reverse('impressao:filas'))


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def liberar(request, impressora_id):
    """Encerra a paralisação e acumula o tempo de inatividade."""
    impressora = get_object_or_404(Impressora, pk=impressora_id,
                                   status=Impressora.MANUTENCAO)
    impressora.inatividade_min = sistema.minutos_inativa(impressora)
    impressora.paralisada_desde = None
    em_andamento = impressora.agendamentos.filter(
        status=Agendamento.IMPRIMINDO).exists()
    impressora.status = (Impressora.IMPRIMINDO if em_andamento
                         else Impressora.DISPONIVEL)
    impressora.save(update_fields=['inatividade_min', 'paralisada_desde', 'status'])
    messages.success(request, f'{impressora.modelo} liberada.')
    avisar_bloqueados(request, sistema.avancar_fila(impressora))
    return HttpResponseRedirect(reverse('impressao:filas'))


# ---------------------------------------------------------------- Administrador: parque

class AdminMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = PERM_ADMIN


class ImpressoraListView(AdminMixin, generic.ListView):
    template_name = 'impressao/impressoras.html'

    def get_queryset(self):
        return Impressora.objects.annotate(
            total_impressoes=Count('agendamentos', filter=Q(
                agendamentos__status=Agendamento.CONCLUIDO)),
            na_fila=Count('agendamentos', filter=Q(
                agendamentos__status=Agendamento.NA_FILA))).order_by('modelo')


class ImpressoraCreateView(AdminMixin, generic.CreateView):
    """UC08 — Cadastro de impressora no parque."""
    model = Impressora
    form_class = ImpressoraForm
    template_name = 'impressao/form.html'
    extra_context = {'titulo': 'Nova impressora', 'eyebrow': 'Parque de impressoras'}
    success_url = reverse_lazy('impressao:impressoras')

    def form_valid(self, form):
        form.instance.status = Impressora.DISPONIVEL
        messages.success(self.request, 'Impressora cadastrada com status "Disponível".')
        return super().form_valid(form)


class ImpressoraUpdateView(AdminMixin, generic.UpdateView):
    model = Impressora
    form_class = ImpressoraForm
    template_name = 'impressao/form.html'
    extra_context = {'titulo': 'Editar impressora', 'eyebrow': 'Parque de impressoras'}
    success_url = reverse_lazy('impressao:impressoras')


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def alternar_atividade(request, impressora_id):
    """UC08, fluxo alternativo: inativação / reativação."""
    impressora = get_object_or_404(Impressora, pk=impressora_id)
    if impressora.status == Impressora.INATIVA:
        impressora.status = Impressora.DISPONIVEL
        impressora.save(update_fields=['status'])
        messages.success(request, f'{impressora.modelo} reativada.')
        avisar_bloqueados(request, sistema.avancar_fila(impressora))
    elif impressora.agendamentos.filter(status=Agendamento.IMPRIMINDO).exists():
        messages.error(request, 'Não é possível inativar uma impressora que '
                                'está imprimindo.')
    else:
        impressora.status = Impressora.INATIVA
        impressora.save(update_fields=['status'])
        messages.warning(request, f'{impressora.modelo} inativada: novos '
                                  f'agendamentos estão bloqueados.')
    return HttpResponseRedirect(reverse('impressao:impressoras'))


# ---------------------------------------------------------------- Administrador: estoque

@login_required
@permission_required(PERM_ADMIN)
def estoque(request):
    """UC07 — Reposição de estoque de filamento."""
    if request.method == 'POST':
        form = ReposicaoForm(request.POST)
        if form.is_valid():
            filamento = form.cleaned_data['filamento']
            quantidade = form.quantidade_em_gramas()
            filamento.quantidade_estoque += quantidade
            filamento.save(update_fields=['quantidade_estoque'])
            ReposicaoEstoque.objects.create(filamento=filamento,
                                            administrador=request.user,
                                            quantidade_adicionada=quantidade)
            messages.success(request, f'Reposição registrada: +{quantidade:g} g '
                                      f'de {filamento}.')
            return HttpResponseRedirect(reverse('impressao:estoque'))
    else:
        form = ReposicaoForm(initial={'filamento': request.GET.get('filamento')})
    filamentos = Filamento.objects.annotate(
        consumo_total=Sum('consumos__quantidade_consumida', filter=Q(
            consumos__agendamento__status__in=[Agendamento.IMPRIMINDO,
                                               Agendamento.CONCLUIDO]))).order_by('tipo', 'cor')
    for f in filamentos:
        referencia = max(f.quantidade_minima * 3, f.quantidade_estoque, 1)
        f.percentual = int(100 * f.quantidade_estoque / referencia)
    context = {
        'form': form,
        'filamentos': filamentos,
        'reposicoes': ReposicaoEstoque.objects.select_related(
            'filamento', 'administrador')[:10],
    }
    return render(request, 'impressao/estoque.html', context)


class FilamentoCreateView(AdminMixin, generic.CreateView):
    """UC07, fluxo alternativo: cadastro de novo material ou cor."""
    model = Filamento
    form_class = FilamentoForm
    template_name = 'impressao/form.html'
    extra_context = {'titulo': 'Novo filamento', 'eyebrow': 'Estoque'}
    success_url = reverse_lazy('impressao:estoque')

    def form_valid(self, form):
        resposta = super().form_valid(form)
        if self.object.quantidade_estoque > 0:
            ReposicaoEstoque.objects.create(
                filamento=self.object, administrador=self.request.user,
                quantidade_adicionada=self.object.quantidade_estoque)
        messages.success(self.request, f'Filamento {self.object} cadastrado.')
        return resposta


# ---------------------------------------------------------------- Administrador: dashboard

def _barras(linhas, rotulo, valor):
    """Prepara os dados para os gráficos de barras em CSS."""
    linhas = [(l[rotulo], l[valor] or 0) for l in linhas]
    maior = max([v for _, v in linhas], default=0) or 1
    return [{'rotulo': r, 'valor': v, 'largura': int(100 * v / maior)}
            for r, v in linhas]


@login_required
@permission_required(PERM_ADMIN)
def dashboard(request):
    """UC03 — Visualização de dashboard de totalização."""
    sistema.processar_impressoes()
    form = DashboardFiltroForm(request.GET or None)

    hoje = timezone.localdate()
    inicio = hoje - timedelta(days=29)
    fim = hoje
    concluidos = Agendamento.objects.filter(status=Agendamento.CONCLUIDO)
    consumos = ConsumoFilamento.objects.filter(
        agendamento__status=Agendamento.CONCLUIDO)
    impressoras = Impressora.objects.exclude(status=Impressora.INATIVA)

    if form.is_valid():
        dados = form.cleaned_data
        inicio = dados['inicio'] or inicio
        fim = dados['fim'] or fim
        if dados['impressora']:
            concluidos = concluidos.filter(impressora=dados['impressora'])
            consumos = consumos.filter(agendamento__impressora=dados['impressora'])
            impressoras = impressoras.filter(pk=dados['impressora'].pk)
        if dados['projetista']:
            concluidos = concluidos.filter(peca__projeto__projetista=dados['projetista'])
            consumos = consumos.filter(
                agendamento__peca__projeto__projetista=dados['projetista'])
        if dados['projeto']:
            concluidos = concluidos.filter(peca__projeto=dados['projeto'])
            consumos = consumos.filter(agendamento__peca__projeto=dados['projeto'])
        if dados['material']:
            concluidos = concluidos.filter(pk__in=ConsumoFilamento.objects.filter(
                filamento__tipo=dados['material']).values('agendamento'))
            consumos = consumos.filter(filamento__tipo=dados['material'])

    tz = timezone.get_current_timezone()
    periodo_inicio = datetime.combine(inicio, time.min, tzinfo=tz)
    periodo_fim = datetime.combine(fim + timedelta(days=1), time.min, tzinfo=tz)
    concluidos = concluidos.filter(data_conclusao__gte=periodo_inicio,
                                   data_conclusao__lt=periodo_fim)
    consumos = consumos.filter(agendamento__data_conclusao__gte=periodo_inicio,
                               agendamento__data_conclusao__lt=periodo_fim)

    minutos_impressao = concluidos.aggregate(
        total=Sum('peca__tempo_estimado_min'))['total'] or 0
    consumo_total = consumos.aggregate(
        total=Sum('quantidade_consumida'))['total'] or 0
    inatividade = sum(sistema.minutos_inativa(i) for i in impressoras)
    capacidade = impressoras.count() * (periodo_fim - periodo_inicio).total_seconds() / 60
    ociosidade = 100 - 100 * minutos_impressao / capacidade if capacidade else 0

    por_impressora = concluidos.values('impressora__modelo').annotate(
        minutos=Sum('peca__tempo_estimado_min')).order_by('-minutos')
    por_material = consumos.values('filamento__tipo').annotate(
        gramas=Sum('quantidade_consumida')).order_by('-gramas')
    por_projeto = consumos.values('agendamento__peca__projeto__nome').annotate(
        gramas=Sum('quantidade_consumida')).order_by('-gramas')[:8]
    por_dia = concluidos.values('data_conclusao__date').annotate(
        total=Count('id', distinct=True)).order_by('data_conclusao__date')

    for linha in por_impressora:
        linha['horas'] = round((linha['minutos'] or 0) / 60, 1)
    for linha in por_dia:
        linha['dia'] = linha['data_conclusao__date'].strftime('%d/%m')

    context = {
        'form': form,
        'inicio': inicio,
        'fim': fim,
        'horas_impressao': round(minutos_impressao / 60, 1),
        'consumo_total': consumo_total,
        'ociosidade': round(max(ociosidade, 0), 1),
        'inatividade_horas': round(inatividade / 60, 1),
        'total_impressoes': concluidos.count(),
        'graf_impressora': _barras(por_impressora, 'impressora__modelo', 'horas'),
        'graf_material': _barras(por_material, 'filamento__tipo', 'gramas'),
        'graf_projeto': _barras(por_projeto, 'agendamento__peca__projeto__nome', 'gramas'),
        'graf_dia': _barras(por_dia, 'dia', 'total'),
        'consolidacoes': ConsolidacaoPeriodica.objects.select_related('administrador')[:6],
    }
    return render(request, 'impressao/dashboard.html', context)


@require_POST
@login_required
@permission_required(PERM_ADMIN)
def consolidar(request):
    """UC12 — Consolidação periódica do fato Consumo e Eficiência."""
    hoje = timezone.localdate()
    tz = timezone.get_current_timezone()
    fim = datetime.combine(hoje + timedelta(days=1), time.min, tzinfo=tz)
    inicio = fim - timedelta(days=30)
    registro = sistema.consolidar(inicio, fim, request.user)
    messages.success(request, f'Consolidação gerada: {registro.total_impressoes} '
                              f'impressões nos últimos 30 dias.')
    return HttpResponseRedirect(reverse('impressao:dashboard'))
