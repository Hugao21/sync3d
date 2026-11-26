from rest_framework import generics

from impressao import sistema
from impressao.models import Agendamento, Filamento, Impressora

from .serializers import (AgendamentoSerializer, FilamentoSerializer,
                          ImpressoraSerializer)


class ImpressoraList(generics.ListCreateAPIView):
    serializer_class = ImpressoraSerializer

    def get_queryset(self):
        # Antes de responder, o Sistema atualiza as filas (UC10/UC11).
        sistema.processar_impressoes()
        return Impressora.objects.exclude(status=Impressora.INATIVA)


class ImpressoraDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Impressora.objects.all()
    serializer_class = ImpressoraSerializer


class FilamentoList(generics.ListCreateAPIView):
    queryset = Filamento.objects.all()
    serializer_class = FilamentoSerializer


class FilamentoDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Filamento.objects.all()
    serializer_class = FilamentoSerializer


class AgendamentoList(generics.ListAPIView):
    """Somente leitura: agendamentos são criados pela tela do Projetista."""
    serializer_class = AgendamentoSerializer

    def get_queryset(self):
        fila = Agendamento.objects.filter(
            status__in=[Agendamento.NA_FILA, Agendamento.IMPRIMINDO,
                        Agendamento.BLOQUEADO]
        ).select_related('peca__projeto__projetista', 'impressora')
        return fila.order_by('impressora', 'posicao_fila')


class AgendamentoDetail(generics.RetrieveAPIView):
    queryset = Agendamento.objects.all()
    serializer_class = AgendamentoSerializer
