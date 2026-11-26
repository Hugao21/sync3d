# Sync3D

Sistema Integrado de Gestão e Filas de Impressão 3D — trabalho da disciplina
PMR3304 Sistemas de Informação (Poli-USP, 2026).

Plataforma web para laboratórios de prototipagem: agendamento de impressões
com fila por máquina, controle de estoque de filamentos e dashboard
analítico de consumo e eficiência, com dois perfis de acesso (Projetista e
Administrador).

A interface segue a identidade visual da apresentação da proposta (azul-marinho
e laranja, títulos serifados e rótulos em caixa alta).

## Tecnologias

Somente o que foi visto nos laboratórios da disciplina:

| Parte | Tecnologia | Laboratório |
|---|---|---|
| Versionamento | Git com branches e merge | Aula 1 |
| Layout | HTML + CSS (Flexbox, Grid, media queries) | Aula 2 |
| Backend | Django: templates, URLs, views genéricas, ModelForm | Aulas 3 e 4 |
| Banco | SQLite via ORM (relações 1:N e N:N) | Aula 4 |
| Autenticação | `django.contrib.auth`, sessões, grupos e permissões | Aula 5 |
| API REST | Django REST Framework | Aula 5 |
| Frontend SPA | React com Vite, consumindo a API (CORS) | Aula 6 |
| Publicação | Render com Gunicorn e WhiteNoise | Aula 3 / EP02 |

## Estrutura

```
sync3dsite/     configurações do projeto Django
impressao/      modelos do DER, views, templates e o módulo sistema.py (ator Sistema)
accounts/       cadastro, login/logout e grupos de usuários
api/            API REST (serializadores e views genéricas do DRF)
templates/      template base
static/         CSS e logo
frontend/       painel de filas em tempo real (React + Vite)
```

## Como rodar

### Backend (Django)

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata dados
python manage.py runserver
```

Acesse http://127.0.0.1:8000/.

### Frontend (React)

Com o Django rodando em `127.0.0.1:8000`, em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Acesse http://localhost:5173/.

### Contas de demonstração

Todas com a senha `sync3d2026`:

| Usuário | Perfil |
|---|---|
| `admin` | Administrador (filas, impressoras, estoque, dashboard) |
| `ana`, `bruno`, `carla` | Projetistas |

Novas contas criadas em "Criar conta" entram no grupo **Projetistas**.

## Casos de uso implementados

| UC | Descrição | Onde |
|---|---|---|
| UC01 | Agendamento de impressão (com bloqueio por ruptura de estoque) | Agendar |
| UC02 | Gerenciamento de fila e parque (aprovar, reordenar, paralisação) | Filas |
| UC03 | Dashboard de totalização com filtros por dimensão | Dashboard |
| UC04 | Cancelamento de agendamento | Minhas impressões → Detalhes |
| UC05 | Acompanhamento de status (posição, início estimado, progresso) | Minhas impressões |
| UC06 | Histórico de impressões com filtro por período e projeto | Histórico |
| UC07 | Reposição de estoque e cadastro de novo material/cor | Estoque |
| UC08 | Cadastro, edição e inativação de impressoras | Impressoras |
| UC09 | Baixa automática de estoque ao iniciar a impressão | `impressao/sistema.py` |
| UC10 | Avanço automático da fila | `impressao/sistema.py` |
| UC11 | Notificação de conclusão ou falha | Notificações (sino) |
| UC12 | Consolidação periódica do fato Consumo e Eficiência | Dashboard → Consolidar |

O ator **Sistema** (UC09 a UC12) é implementado em `impressao/sistema.py`. Como
o projeto não usa tarefas agendadas, as rotinas rodam quando algo muda na fila
e sempre que as telas de acompanhamento ou a API são acessadas: impressões cujo
tempo estimado terminou são concluídas e a fila avança sozinha.

## Modelo de dados

Segue o Diagrama Entidade-Relacionamento do trabalho: `Projeto`, `Peca`,
`Impressora`, `Filamento`, `Agendamento`, `ConsumoFilamento` (tabela
associativa N:N), `ReposicaoEstoque`, `Notificacao` e `ConsolidacaoPeriodica`.
As tabelas `Projetista` e `Administrador` do DER correspondem ao `User` do
Django separado pelos grupos **Projetistas** e **Administradores** — assim o
`senha_hash` é gerenciado pelo próprio Django.

## API REST

Leitura liberada; escrita exige as permissões de modelo do usuário.

| Endpoint | Métodos |
|---|---|
| `/api/v1/impressoras/` e `/api/v1/impressoras/<id>/` | GET, POST, PUT, DELETE (com a fila de cada máquina) |
| `/api/v1/filamentos/` e `/api/v1/filamentos/<id>/` | GET, POST, PUT, DELETE |
| `/api/v1/agendamentos/` e `/api/v1/agendamentos/<id>/` | GET |

## Publicação no Render

- Build command: `./build.sh`
- Start command: `gunicorn sync3dsite.wsgi`
- Variáveis de ambiente: `SECRET_KEY`, `DEBUG=False` e, opcionalmente,
  `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD` e
  `DJANGO_SUPERUSER_EMAIL`.

## Equipe

- Gabriel Pontoni Silva — NUSP 15453751
- Giovanni Mendes Lima — NUSP 12553970
- Hugo Issao Matsumoto — NUSP 15637784
