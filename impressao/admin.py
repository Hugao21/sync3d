from django.contrib import admin

from .models import (Agendamento, ConsolidacaoPeriodica, ConsumoFilamento,
                     Filamento, Impressora, Notificacao, Peca, Projeto,
                     ReposicaoEstoque)

admin.site.register(Projeto)
admin.site.register(Peca)
admin.site.register(Impressora)
admin.site.register(Filamento)
admin.site.register(Agendamento)
admin.site.register(ConsumoFilamento)
admin.site.register(ReposicaoEstoque)
admin.site.register(Notificacao)
admin.site.register(ConsolidacaoPeriodica)
