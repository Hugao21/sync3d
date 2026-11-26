from django import forms
from django.contrib.auth.models import User

from .models import Filamento, Impressora, Peca, Projeto


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ['nome', 'descricao']
        labels = {
            'nome': 'Nome do projeto',
            'descricao': 'Descrição',
        }


class PecaForm(forms.ModelForm):
    class Meta:
        model = Peca
        fields = ['nome', 'arquivo_modelo', 'tempo_estimado_min']
        labels = {
            'nome': 'Nome da peça',
            'arquivo_modelo': 'Arquivo do modelo 3D',
            'tempo_estimado_min': 'Tempo estimado de impressão (min)',
        }

    def clean_arquivo_modelo(self):
        arquivo = self.cleaned_data['arquivo_modelo'].strip()
        extensoes = ('.stl', '.obj', '.3mf', '.gcode')
        if not arquivo.lower().endswith(extensoes):
            raise forms.ValidationError(
                'Informe um arquivo .stl, .obj, .3mf ou .gcode.')
        return arquivo


class AgendamentoForm(forms.Form):
    """UC01 — Agendamento de impressão com seleção de insumos."""
    peca = forms.ModelChoiceField(queryset=Peca.objects.none(), label='Peça',
                                  empty_label='Selecione a peça')
    impressora = forms.ModelChoiceField(
        queryset=Impressora.objects.exclude(status=Impressora.INATIVA),
        label='Impressora', empty_label='Selecione a impressora')
    filamento_1 = forms.ModelChoiceField(queryset=Filamento.objects.all(),
                                         label='Filamento principal',
                                         empty_label='Selecione o filamento')
    quantidade_1 = forms.FloatField(min_value=1, label='Quantidade (g)')
    filamento_2 = forms.ModelChoiceField(queryset=Filamento.objects.all(),
                                         required=False,
                                         label='Segundo filamento (opcional)',
                                         empty_label='Nenhum')
    quantidade_2 = forms.FloatField(min_value=1, required=False,
                                    label='Quantidade (g)')

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['peca'].queryset = Peca.objects.filter(
            projeto__projetista=user).select_related('projeto')
        self.fields['peca'].label_from_instance = (
            lambda p: f'{p.projeto.nome} · {p.nome} ({p.arquivo_modelo})')
        for campo in ('filamento_1', 'filamento_2'):
            self.fields[campo].label_from_instance = (
                lambda f: f'{f.tipo} {f.cor} — {f.quantidade_estoque:g} '
                          f'{f.unidade_medida} em estoque')

    def insumos(self):
        """Lista de pares (filamento, quantidade) informados."""
        dados = self.cleaned_data
        pares = [(dados['filamento_1'], dados['quantidade_1'])]
        if dados.get('filamento_2'):
            pares.append((dados['filamento_2'], dados['quantidade_2']))
        return pares

    def clean(self):
        dados = super().clean()
        if self.errors:
            return dados

        if dados.get('filamento_2') and not dados.get('quantidade_2'):
            self.add_error('quantidade_2', 'Informe a quantidade do segundo filamento.')
            return dados
        if dados.get('filamento_2') == dados.get('filamento_1'):
            self.add_error('filamento_2', 'Escolha um filamento diferente do principal.')
            return dados

        impressora = dados['impressora']
        compativeis = [m.strip().lower()
                       for m in impressora.materiais_compativeis.split(',')]
        for filamento, quantidade in self.insumos():
            if filamento.tipo.lower() not in compativeis:
                raise forms.ValidationError(
                    f'A impressora {impressora.modelo} não é compatível com '
                    f'{filamento.tipo}. Materiais aceitos: '
                    f'{impressora.materiais_compativeis}.')
            # UC01, fluxo alternativo b: ruptura de estoque.
            if filamento.quantidade_estoque < quantidade:
                raise forms.ValidationError(
                    f'Estoque insuficiente de {filamento}: há apenas '
                    f'{filamento.quantidade_estoque:g} {filamento.unidade_medida}. '
                    f'Escolha um insumo alternativo.')
        return dados


class HistoricoFiltroForm(forms.Form):
    """UC06 — filtro do histórico por período e projeto."""
    inicio = forms.DateField(required=False, label='De',
                             widget=forms.DateInput(attrs={'type': 'date'}))
    fim = forms.DateField(required=False, label='Até',
                          widget=forms.DateInput(attrs={'type': 'date'}))
    projeto = forms.ModelChoiceField(queryset=Projeto.objects.none(),
                                     required=False, label='Projeto',
                                     empty_label='Todos')

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['projeto'].queryset = Projeto.objects.filter(projetista=user)


class ImpressoraForm(forms.ModelForm):
    class Meta:
        model = Impressora
        fields = ['modelo', 'localizacao', 'materiais_compativeis']
        labels = {
            'modelo': 'Modelo',
            'localizacao': 'Localização',
            'materiais_compativeis': 'Materiais compatíveis',
        }


class FilamentoForm(forms.ModelForm):
    class Meta:
        model = Filamento
        fields = ['tipo', 'cor', 'quantidade_estoque', 'quantidade_minima',
                  'unidade_medida']
        labels = {
            'tipo': 'Material',
            'cor': 'Cor',
            'quantidade_estoque': 'Quantidade inicial em estoque',
            'quantidade_minima': 'Estoque mínimo',
            'unidade_medida': 'Unidade',
        }


class ReposicaoForm(forms.Form):
    """UC07 — Reposição de estoque de filamento."""
    filamento = forms.ModelChoiceField(queryset=Filamento.objects.all(),
                                       label='Filamento',
                                       empty_label='Selecione o filamento')
    quantidade = forms.FloatField(min_value=1, label='Quantidade recebida')
    unidade = forms.ChoiceField(choices=[('g', 'gramas'),
                                         ('rolo', 'rolos de 1 kg')],
                                label='Unidade')

    def quantidade_em_gramas(self):
        quantidade = self.cleaned_data['quantidade']
        if self.cleaned_data['unidade'] == 'rolo':
            return quantidade * 1000
        return quantidade


class DashboardFiltroForm(forms.Form):
    """UC03 — filtros pelas dimensões Tempo, Impressora, Usuário/Projeto e Material."""
    inicio = forms.DateField(required=False, label='De',
                             widget=forms.DateInput(attrs={'type': 'date'}))
    fim = forms.DateField(required=False, label='Até',
                          widget=forms.DateInput(attrs={'type': 'date'}))
    impressora = forms.ModelChoiceField(queryset=Impressora.objects.all(),
                                        required=False, empty_label='Todas')
    projetista = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Projetistas').order_by('first_name'),
        required=False, empty_label='Todos', label='Usuário')
    projeto = forms.ModelChoiceField(queryset=Projeto.objects.all(),
                                     required=False, empty_label='Todos')
    material = forms.ChoiceField(required=False, label='Material')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tipos = Filamento.objects.values_list('tipo', flat=True).distinct().order_by('tipo')
        self.fields['material'].choices = [('', 'Todos')] + [(t, t) for t in tipos]
        self.fields['projetista'].label_from_instance = (
            lambda u: u.get_full_name() or u.username)
