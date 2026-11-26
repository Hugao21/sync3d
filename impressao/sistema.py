"""Automações do ator "Sistema" (casos de uso UC09 a UC12).

Como o projeto não usa tarefas agendadas, estas funções são chamadas pelas
views sempre que algo muda na fila (aprovação, conclusão, cancelamento,
paralisação) e também ao abrir as telas de acompanhamento, o que simula o
monitoramento contínuo das impressoras.
"""
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import (Agendamento, ConsolidacaoPeriodica, ConsumoFilamento,
                     Impressora, Notificacao)


def renumerar_fila(impressora):
    """Mantém posicao_fila sequencial (1, 2, 3...) para os itens pendentes."""
    for posicao, item in enumerate(impressora.fila(), start=1):
        if item.posicao_fila != posicao:
            item.posicao_fila = posicao
            item.save(update_fields=['posicao_fila'])


def recalcular_previsoes(impressora):
    """Estima o horário de início de cada item da fila (UC05)."""
    agora = timezone.now()
    inicio = agora
    for item in impressora.fila():
        duracao = timedelta(minutes=item.peca.tempo_estimado_min)
        if item.status == Agendamento.IMPRIMINDO:
            fim = item.data_inicio_previsto + duracao
            inicio = max(fim, agora)
            continue
        if item.status == Agendamento.BLOQUEADO:
            continue
        item.data_inicio_previsto = inicio
        item.save(update_fields=['data_inicio_previsto'])
        inicio = inicio + duracao


def baixar_estoque(agendamento):
    """UC09 — debita o filamento reservado quando a impressão começa.

    Retorna True se a baixa foi feita. Se faltar material, marca o
    agendamento como "Bloqueado" e retorna False.
    """
    consumos = agendamento.consumos.select_related('filamento')
    for consumo in consumos:
        if consumo.filamento.quantidade_estoque < consumo.quantidade_consumida:
            agendamento.status = Agendamento.BLOQUEADO
            agendamento.save(update_fields=['status'])
            return False
    for consumo in consumos:
        filamento = consumo.filamento
        filamento.quantidade_estoque -= consumo.quantidade_consumida
        filamento.save(update_fields=['quantidade_estoque'])
    agendamento.status = Agendamento.IMPRIMINDO
    agendamento.data_inicio_previsto = timezone.now()
    agendamento.save(update_fields=['status', 'data_inicio_previsto'])
    return True


def avancar_fila(impressora):
    """UC10 — promove o próximo agendamento aprovado quando a máquina fica livre.

    Retorna a lista de agendamentos que ficaram bloqueados por falta de
    estoque, para que a view avise o Administrador.
    """
    bloqueados = []
    if impressora.status in (Impressora.MANUTENCAO, Impressora.INATIVA):
        # Fluxo alternativo: impressora paralisada suspende o avanço.
        recalcular_previsoes(impressora)
        return bloqueados

    em_andamento = impressora.agendamentos.filter(
        status=Agendamento.IMPRIMINDO).exists()
    if not em_andamento:
        candidatos = impressora.agendamentos.filter(
            status=Agendamento.NA_FILA, aprovado=True).order_by('posicao_fila')
        iniciou = False
        for candidato in candidatos:
            if baixar_estoque(candidato):
                iniciou = True
                break
            bloqueados.append(candidato)
        novo_status = Impressora.IMPRIMINDO if iniciou else Impressora.DISPONIVEL
        if impressora.status != novo_status:
            impressora.status = novo_status
            impressora.save(update_fields=['status'])

    renumerar_fila(impressora)
    recalcular_previsoes(impressora)
    return bloqueados


def concluir(agendamento, sucesso=True):
    """UC11 — encerra a impressão e notifica o Projetista responsável."""
    agendamento.status = Agendamento.CONCLUIDO if sucesso else Agendamento.FALHA
    agendamento.data_conclusao = timezone.now()
    agendamento.save(update_fields=['status', 'data_conclusao'])

    peca = agendamento.peca
    if sucesso:
        mensagem = (f'Sua impressão "{peca.nome}" ({peca.arquivo_modelo}) foi '
                    f'concluída e já pode ser retirada.')
    else:
        mensagem = (f'A impressão "{peca.nome}" ({peca.arquivo_modelo}) falhou. '
                    f'Procure o Administrador do laboratório.')
    Notificacao.objects.create(agendamento=agendamento, mensagem=mensagem)

    impressora = agendamento.impressora
    if impressora and impressora.status == Impressora.IMPRIMINDO:
        impressora.status = Impressora.DISPONIVEL
        impressora.save(update_fields=['status'])
    if impressora:
        return avancar_fila(impressora)
    return []


def processar_impressoes():
    """Conclui automaticamente as impressões cujo tempo estimado já passou."""
    agora = timezone.now()
    imprimindo = Agendamento.objects.filter(
        status=Agendamento.IMPRIMINDO).select_related('peca')
    for item in imprimindo:
        fim = item.data_inicio_previsto + timedelta(
            minutes=item.peca.tempo_estimado_min)
        if fim <= agora:
            concluir(item, sucesso=True)


def progresso(agendamento):
    """Percentual estimado de uma impressão em andamento (0 a 100)."""
    if agendamento.status == Agendamento.CONCLUIDO:
        return 100
    if agendamento.status != Agendamento.IMPRIMINDO:
        return 0
    decorrido = (timezone.now() - agendamento.data_inicio_previsto).total_seconds()
    total = agendamento.peca.tempo_estimado_min * 60
    return max(0, min(100, int(100 * decorrido / total))) if total else 100


def minutos_inativa(impressora, agora=None):
    """Inatividade acumulada, incluindo a paralisação em curso."""
    agora = agora or timezone.now()
    total = impressora.inatividade_min
    if impressora.paralisada_desde:
        total += int((agora - impressora.paralisada_desde).total_seconds() // 60)
    return total


def consolidar(periodo_inicio, periodo_fim, administrador=None):
    """UC12 — pré-calcula o fato Consumo e Eficiência de um período."""
    concluidos = Agendamento.objects.filter(
        status=Agendamento.CONCLUIDO,
        data_conclusao__gte=periodo_inicio,
        data_conclusao__lt=periodo_fim,
    )
    total_impressoes = concluidos.count()
    consumo = ConsumoFilamento.objects.filter(
        agendamento__in=concluidos
    ).aggregate(total=Sum('quantidade_consumida'))['total'] or 0
    minutos_impressao = concluidos.aggregate(
        total=Sum('peca__tempo_estimado_min'))['total'] or 0

    ativas = Impressora.objects.exclude(status=Impressora.INATIVA).count()
    minutos_periodo = (periodo_fim - periodo_inicio).total_seconds() / 60
    capacidade = ativas * minutos_periodo
    eficiencia = 100 * minutos_impressao / capacidade if capacidade else 0

    return ConsolidacaoPeriodica.objects.create(
        administrador=administrador,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        total_impressoes=total_impressoes,
        consumo_total_filamento=consumo,
        eficiencia_media=round(eficiencia, 2),
    )
