import React from 'react'

const API_URL = 'http://127.0.0.1:8000/api/v1/impressoras/'
const INTERVALO_MS = 15000

function Button(props) {
  const { onClick, className = '', children } = props
  return (
    <button onClick={onClick} className={className} type="button">
      {children}
    </button>
  )
}

function Search(props) {
  const { searchTerm, handleInputChange, children } = props
  return (
    <form className="busca" onSubmit={e => e.preventDefault()}>
      <label htmlFor="searchTerm">{children}</label>
      <input
        id="searchTerm"
        name="searchTerm"
        type="text"
        value={searchTerm}
        placeholder="impressora, arquivo ou projetista"
        onChange={handleInputChange}
      />
    </form>
  )
}

function Status(props) {
  const { status, children } = props
  return <span className={`status ${status}`}>{children}</span>
}

function formatarHora(iso) {
  if (!iso) return '—'
  const data = new Date(iso)
  return data.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function ItemFila(props) {
  const { item } = props
  const insumos = item.consumos
    .map(c => `${c.filamento} ${Math.round(c.quantidade_consumida)} g`)
    .join(', ')
  const pendente = item.status === 'na_fila' && !item.aprovado
  return (
    <li className={`item ${item.status}`}>
      <div className="item-topo">
        <div>
          <span className="posicao">{item.posicao_fila}º</span>
          <strong>{item.arquivo}</strong>
          <small>{item.projetista} · {insumos}</small>
        </div>
        <Status status={item.status}>
          {pendente ? 'Pendente' : item.status_display}
        </Status>
      </div>
      {item.status === 'imprimindo'
        ? (
          <div className="progresso" title={`${item.progresso}%`}>
            <div style={{ width: `${item.progresso}%` }} />
          </div>
        )
        : <small>Início estimado: {formatarHora(item.data_inicio_previsto)}</small>}
    </li>
  )
}

function PainelImpressora(props) {
  const { impressora, onDismiss } = props
  return (
    <section className="cartao">
      <div className="cartao-topo">
        <div>
          <span className="eyebrow">Fila — {impressora.localizacao}</span>
          <h2>{impressora.modelo}</h2>
          <small>{impressora.materiais_compativeis}</small>
        </div>
        <Status status={impressora.status}>{impressora.status_display}</Status>
      </div>
      {impressora.fila.length
        ? <ul className="fila">{impressora.fila.map(item => <ItemFila key={item.id} item={item} />)}</ul>
        : <p className="vazio">Fila vazia — impressora livre.</p>}
      <Button className="secundario" onClick={() => onDismiss(impressora.id)}>
        Ocultar
      </Button>
    </section>
  )
}

const contemTermo = searchTerm => impressora => {
  const termo = searchTerm.toLowerCase()
  if (impressora.modelo.toLowerCase().includes(termo)) return true
  return impressora.fila.some(item =>
    item.arquivo.toLowerCase().includes(termo) ||
    item.projetista.toLowerCase().includes(termo))
}

class App extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      list: null,
      searchTerm: '',
      ocultas: [],
      erro: null,
      atualizadoEm: null,
    }
    this.buscarFilas = this.buscarFilas.bind(this)
    this.onDismiss = this.onDismiss.bind(this)
    this.mostrarTodas = this.mostrarTodas.bind(this)
    this.handleInputChange = this.handleInputChange.bind(this)
  }

  componentDidMount() {
    this.buscarFilas()
    this.timer = setInterval(this.buscarFilas, INTERVALO_MS)
  }

  componentWillUnmount() {
    clearInterval(this.timer)
  }

  buscarFilas() {
    fetch(API_URL)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.json()
      })
      .then(dados => this.setState({ list: dados, erro: null, atualizadoEm: new Date() }))
      .catch(e => this.setState({ erro: e.message }))
  }

  onDismiss(id) {
    this.setState(state => ({ ocultas: [...state.ocultas, id] }))
  }

  mostrarTodas() {
    this.setState({ ocultas: [] })
  }

  handleInputChange(event) {
    const { name, value } = event.target
    this.setState({ [name]: value })
  }

  render() {
    const { list, searchTerm, ocultas, erro, atualizadoEm } = this.state
    const visiveis = list
      ? list.filter(imp => !ocultas.includes(imp.id)).filter(contemTermo(searchTerm))
      : null
    const imprimindo = list ? list.filter(imp => imp.status === 'imprimindo').length : 0
    const naFila = list ? list.reduce((total, imp) => total + imp.fila.length, 0) : 0

    return (
      <div className="App">
        <header className="topo">
          <div className="marca">
            <img src="/logo.svg" alt="" />
            <b>Sync<span>3D</span></b>
          </div>
          <div>
            <span className="eyebrow">Painel em tempo real</span>
            <h1>Filas de impressão</h1>
          </div>
        </header>

        <main>
          <div className="barra-controle">
            <Search searchTerm={searchTerm} handleInputChange={this.handleInputChange}>
              Buscar:
            </Search>
            {ocultas.length > 0 && (
              <Button onClick={this.mostrarTodas}>Mostrar todas ({ocultas.length} ocultas)</Button>
            )}
            <small className="atualizacao">
              {atualizadoEm
                ? `Atualizado às ${atualizadoEm.toLocaleTimeString('pt-BR')} · a cada ${INTERVALO_MS / 1000} s`
                : 'Carregando…'}
            </small>
          </div>

          {erro && (
            <p className="erro">
              Não foi possível acessar a API ({erro}). Verifique se o Django está rodando em http://127.0.0.1:8000.
            </p>
          )}

          {list && (
            <div className="resumo">
              <div><strong>{list.length}</strong> impressoras ativas</div>
              <div><strong>{imprimindo}</strong> imprimindo agora</div>
              <div><strong>{naFila}</strong> itens nas filas</div>
            </div>
          )}

          {visiveis
            ? (
              <div className="paineis">
                {visiveis.map(imp => (
                  <PainelImpressora key={imp.id} impressora={imp} onDismiss={this.onDismiss} />
                ))}
                {visiveis.length === 0 && <p className="vazio">Nenhuma fila encontrada para "{searchTerm}".</p>}
              </div>
            )
            : null}
        </main>
      </div>
    )
  }
}

export default App
