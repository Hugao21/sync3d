from rest_framework import serializers

from impressao import sistema
from impressao.models import Agendamento, ConsumoFilamento, Filamento, Impressora


class ConsumoSerializer(serializers.ModelSerializer):
    filamento = serializers.StringRelatedField()

    class Meta:
        model = ConsumoFilamento
        fields = ['filamento', 'quantidade_consumida']


class AgendamentoSerializer(serializers.ModelSerializer):
    """Item da fila. Do projetista, mostra só o primeiro nome."""
    peca = serializers.CharField(source='peca.nome', read_only=True)
    arquivo = serializers.CharField(source='peca.arquivo_modelo', read_only=True)
    projeto = serializers.CharField(source='peca.projeto.nome', read_only=True)
    projetista = serializers.SerializerMethodField()
    impressora = serializers.StringRelatedField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tempo_estimado_min = serializers.IntegerField(source='peca.tempo_estimado_min',
                                                  read_only=True)
    progresso = serializers.SerializerMethodField()
    consumos = ConsumoSerializer(many=True, read_only=True)

    class Meta:
        model = Agendamento
        fields = ['id', 'peca', 'arquivo', 'projeto', 'projetista', 'impressora',
                  'status', 'status_display', 'aprovado', 'posicao_fila',
                  'data_solicitacao', 'data_inicio_previsto', 'data_conclusao',
                  'tempo_estimado_min', 'progresso', 'consumos']

    def get_projetista(self, obj):
        usuario = obj.projetista()
        return usuario.first_name or usuario.username

    def get_progresso(self, obj):
        return sistema.progresso(obj)


class ImpressoraSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    fila = AgendamentoSerializer(many=True, read_only=True)

    class Meta:
        model = Impressora
        fields = ['id', 'modelo', 'localizacao', 'materiais_compativeis',
                  'status', 'status_display', 'inatividade_min', 'fila']
        read_only_fields = ['inatividade_min']


class FilamentoSerializer(serializers.ModelSerializer):
    em_falta = serializers.BooleanField(read_only=True)

    class Meta:
        model = Filamento
        fields = ['id', 'tipo', 'cor', 'quantidade_estoque', 'quantidade_minima',
                  'unidade_medida', 'em_falta']
