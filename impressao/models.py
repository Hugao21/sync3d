from django.conf import settings
from django.db import models


class Projeto(models.Model):
    """Agrupa as peças de um projetista (Projetista 1:N Projeto)."""
    projetista = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.CASCADE,
                                   related_name='projetos')
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return self.nome


class Peca(models.Model):
    """Peça a imprimir, com o arquivo 3D e a estimativa de tempo (Projeto 1:N Peca)."""
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE,
                                related_name='pecas')
    nome = models.CharField(max_length=120)
    arquivo_modelo = models.CharField(max_length=200,
                                      help_text='Nome do arquivo 3D, ex: suporte_v2.stl')
    tempo_estimado_min = models.PositiveIntegerField()

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.arquivo_modelo})'


class Impressora(models.Model):
    """Máquina do parque que executa as impressões."""
    DISPONIVEL = 'disponivel'
    IMPRIMINDO = 'imprimindo'
    MANUTENCAO = 'manutencao'
    INATIVA = 'inativa'
    STATUS_CHOICES = [
        (DISPONIVEL, 'Disponível'),
        (IMPRIMINDO, 'Imprimindo'),
        (MANUTENCAO, 'Em manutenção'),
        (INATIVA, 'Inativa'),
    ]

    modelo = models.CharField(max_length=120)
    localizacao = models.CharField(max_length=120)
    materiais_compativeis = models.CharField(max_length=120, default='PLA, PETG',
                                             help_text='Separados por vírgula')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=DISPONIVEL)
    paralisada_desde = models.DateTimeField(null=True, blank=True)
    inatividade_min = models.PositiveIntegerField(
        default=0, help_text='Tempo total de inatividade por manutenção (min)')

    class Meta:
        ordering = ['modelo']

    def __str__(self):
        return f'{self.modelo} — {self.localizacao}'

    def fila(self):
        """Agendamentos pendentes ou em andamento, na ordem da fila."""
        return self.agendamentos.filter(
            status__in=[Agendamento.IMPRIMINDO, Agendamento.NA_FILA,
                        Agendamento.BLOQUEADO]
        ).order_by('posicao_fila')


class Filamento(models.Model):
    """Estoque de material consumível, por tipo e cor."""
    tipo = models.CharField(max_length=40)
    cor = models.CharField(max_length=40)
    quantidade_estoque = models.FloatField(default=0)
    quantidade_minima = models.FloatField(default=200)
    unidade_medida = models.CharField(max_length=10, default='g')

    class Meta:
        ordering = ['tipo', 'cor']

    def __str__(self):
        return f'{self.tipo} {self.cor}'

    def em_falta(self):
        return self.quantidade_estoque < self.quantidade_minima


class Agendamento(models.Model):
    """Entidade central: uma solicitação de impressão na fila de uma impressora."""
    NA_FILA = 'na_fila'
    IMPRIMINDO = 'imprimindo'
    CONCLUIDO = 'concluido'
    BLOQUEADO = 'bloqueado'
    CANCELADO = 'cancelado'
    FALHA = 'falha'
    STATUS_CHOICES = [
        (NA_FILA, 'Na fila'),
        (IMPRIMINDO, 'Imprimindo'),
        (CONCLUIDO, 'Concluído'),
        (BLOQUEADO, 'Bloqueado'),
        (CANCELADO, 'Cancelado'),
        (FALHA, 'Falha'),
    ]

    peca = models.ForeignKey(Peca, on_delete=models.CASCADE,
                             related_name='agendamentos')
    impressora = models.ForeignKey(Impressora, on_delete=models.SET_NULL,
                                   null=True, related_name='agendamentos')
    filamentos = models.ManyToManyField(Filamento, through='ConsumoFilamento',
                                        related_name='agendamentos')
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_inicio_previsto = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=NA_FILA)
    posicao_fila = models.PositiveIntegerField(default=0)
    aprovado = models.BooleanField(default=False)

    class Meta:
        ordering = ['posicao_fila', 'data_solicitacao']

    def __str__(self):
        return f'#{self.id} {self.peca.nome}'

    def projetista(self):
        # Cadeia de propriedade: Projetista -> Projeto -> Peca -> Agendamento
        return self.peca.projeto.projetista


class ConsumoFilamento(models.Model):
    """Tabela associativa (N:N) entre Agendamento e Filamento."""
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE,
                                    related_name='consumos')
    filamento = models.ForeignKey(Filamento, on_delete=models.PROTECT,
                                  related_name='consumos')
    quantidade_consumida = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['agendamento', 'filamento'],
                                    name='consumo_unico'),
        ]

    def __str__(self):
        return f'{self.filamento}: {self.quantidade_consumida:g} g'


class ReposicaoEstoque(models.Model):
    """Histórico de reposições feitas pelo administrador (UC07)."""
    filamento = models.ForeignKey(Filamento, on_delete=models.CASCADE,
                                  related_name='reposicoes')
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL, null=True,
                                      related_name='reposicoes')
    quantidade_adicionada = models.FloatField()
    data_reposicao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_reposicao']

    def __str__(self):
        return f'+{self.quantidade_adicionada:g} {self.filamento}'


class Notificacao(models.Model):
    """Aviso gerado pelo Sistema ao fim de uma impressão (UC11)."""
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE,
                                    related_name='notificacoes')
    mensagem = models.TextField()
    data_envio = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ['-data_envio']

    def __str__(self):
        return self.mensagem[:50]


class ConsolidacaoPeriodica(models.Model):
    """Totais por período gerados pelo Sistema para o dashboard (UC12)."""
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name='consolidacoes')
    periodo_inicio = models.DateTimeField()
    periodo_fim = models.DateTimeField()
    total_impressoes = models.PositiveIntegerField(default=0)
    consumo_total_filamento = models.FloatField(default=0)
    eficiencia_media = models.FloatField(default=0)
    data_geracao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_geracao']

    def __str__(self):
        return f'{self.periodo_inicio:%d/%m/%Y} a {self.periodo_fim:%d/%m/%Y}'
