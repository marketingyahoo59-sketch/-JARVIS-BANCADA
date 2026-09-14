# JARVIS de Bancada

Assistente ativo de diagnóstico eletrônico (Streamlit): escuta, vê a placa, pesquisa e fala — estilo Homem de Ferro para bancada.

## O que faz

1. **Visão** — marca cruzes nas pontas do multímetro na foto e mostra zoom da área.
2. **Status de voz** — chip Ouvindo / Processando / Falando.
3. **Banco de falhas** — ao marcar resolvido, salva placa/sintoma/peça para casos parecidos.
4. **Esquema/PDF** — anexa datasheet ou esquema; o texto entra no contexto do agente.
5. **Checklist de segurança** — avisos de tomada, capacitores, ESD, escala do multímetro.
6. **Fallback de voz** — TTS OpenAI; se falhar, usa edge-tts (pt-BR).
7. **PWA** — `static/manifest.json` + service worker para instalar no celular.
8. **Confirmação** — medição “errada” pede **confirmo** antes do Modo Solução.

Também: escuta contínua (Web Speech), Whisper para áudio manual, pesquisa web, memória em `data/cases/`.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# OPENAI_API_KEY ou ANTHROPIC_API_KEY
```

## Executar

```bash
streamlit run app.py --server.port 3847 --server.address 0.0.0.0
```

Abra http://127.0.0.1:3847

Sem API key sobe em **modo demo**.

## Testes rápidos

```bash
.venv/bin/python scripts/test_features.py
```

## Estrutura

```
app.py
agent/           # diagnostic, llm, memory, vision, voice, docs, failures, safety
static/          # PWA
data/cases/      # histórico
scripts/test_features.py
```

## Aviso

Uso assistido. Em fontes SMPS: capacitores carregados e isolamento. A responsabilidade da intervenção é sua.
