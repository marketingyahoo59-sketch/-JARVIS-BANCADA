# Agente de Diagnóstico Eletrônico (Streamlit)

Aplicativo **ativo** de diagnóstico: a IA guia cada medição, interpreta o valor e indica a peça a trocar. O usuário só executa (mãos); o agente é o cérebro.

## O que faz

1. **Início** — pergunta modelo da placa e sintoma.
2. **Visão** — upload de foto; a IA descreve/marca onde colocar as pontas do multímetro.
3. **Loop** — pede uma medição por vez (ex.: pino 3 do CI de standby).
4. **Decisão** — valor OK → próximo ponto; valor errado → **Modo Solução** (componentes do nó + peça a trocar).
5. **Memória** — histórico de medições e notas em `data/cases/` para reavaliar se o conserto falhar.

## Requisitos

- Python 3.10+
- Chave **OpenAI (GPT-4o)** ou **Anthropic (Claude 3.5 Sonnet)** — opcional para demo local

## Instalação

```bash
cd /caminho/do/projeto
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env e coloque OPENAI_API_KEY ou ANTHROPIC_API_KEY
```

## Executar

```bash
streamlit run app.py --server.port 3847 --server.address 0.0.0.0
```

Abra o endereço indicado no terminal (ex.: http://127.0.0.1:3847).

Sem API key o app sobe em **modo demo** (regras locais) para você validar o fluxo.

## Disco / pasta do projeto

Neste ambiente Cloud o código fica em `/workspace`. No seu PC Windows, clone/copie o projeto para o **disco D** (ex.: `D:\projetos\diagnostico-eletronica`) para não ocupar o disco C, conforme sua preferência.

## Estrutura

```
app.py                 # Interface Streamlit
agent/
  diagnostic.py        # Orquestração do agente
  llm.py               # GPT-4o / Claude + fallback demo
  memory.py            # Persistência do caso
data/cases/            # Histórico JSON por caso
data/uploads/          # Fotos enviadas
```

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `LLM_PROVIDER` | `openai` ou `anthropic` |
| `OPENAI_API_KEY` | Chave OpenAI |
| `ANTHROPIC_API_KEY` | Chave Anthropic |
| `OPENAI_MODEL` | Padrão `gpt-4o` |
| `ANTHROPIC_MODEL` | Padrão `claude-3-5-sonnet-20241022` |

## Aviso

Uso educativo/assistido. Trabalhe com segurança em fontes SMPS (capacitores carregados, isolamento). O agente sugere passos; a responsabilidade da intervenção é sua.
