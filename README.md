# UFES Redes Trab2 — Nó LLM

Pacote de implantação dos **nós de inferência** do Projeto 1 (Redes de Computadores, UFES): cada processo é um
`llama-server` (llama.cpp) com um modelo de pesos abertos, uma porta e um número fixo de vagas (*slots*). Este
repositório não tem gateway, fila, balanceamento nem usuários: isso é do
[Backend](../UFES_Redes_Trab2_Backend/). Diagramas e código explicados: [EXPLICACAO.md](EXPLICACAO.md).

## Jeito normal: pelo `lab.py` do Backend

Com os três repositórios lado a lado, o `lab.py` do Backend faz tudo deste repositório:

- baixa o `llama-server` oficial (versão fixa) para `bin/`;
- baixa os modelos para `models/`, conferindo o SHA-256 de cada um;
- gera a config do nó em `../UFES_Redes_Trab2_Backend/.lab/nos/`;
- inicia o `scripts/node.py`.

```bash
cd ../UFES_Redes_Trab2_Backend
python3 lab.py no --modelo pequeno            # nó da rede do laboratório, porta 8101
python3 lab.py no --modelo grande --slots 2   # prontuário, porta 8102, 2 vagas
```

Passo a passo do laboratório: [Backend/docs/LABORATORIO.md](../UFES_Redes_Trab2_Backend/docs/LABORATORIO.md).

## Os modelos

| Apelido | Modelo | Arquivo | Usado em |
|---|---|---|---|
| pequeno | Qwen3 1.7B Q4_K_M (~1,1 GB) | `Qwen3-1.7B-Q4_K_M.gguf` | domínio `redes` (e `prontuario` no modo `--leve`) |
| grande | Qwen3.5 4B Q4_K_M (~2,7 GB) | `Qwen3.5-4B-Q4_K_M.gguf` | domínio `prontuario` |

Origem, revisão fixa e SHA-256 estão em [`models/manifest.json`](models/manifest.json). Os pesos não vão para o git.
Confirme a licença no model card oficial antes de redistribuir.

## Segurança do nó

| Situação | Como o nó fica |
|---|---|
| Mesma máquina do gateway | `bind_host = "127.0.0.1"`; ninguém de fora alcança |
| Rede do laboratório (padrão do `lab.py no`) | `bind_host = "0.0.0.0"` com **`api_key_file`**: o `llama-server` recebe `--api-key-file` e devolve 401 a quem não mandar `Authorization: Bearer <chave>`. O `/health` continua aberto |
| Rede não confiável | HTTPS por nó (`tls_certfile`/`tls_keyfile`, `scripts/create-node-cert.sh`), opcional e fora do caminho padrão |

O `node.py` recusa HTTP fora do loopback **sem** chave. Nunca exponha um nó na internet. Tokens de usuário nunca chegam
ao nó: quem autentica o usuário é o gateway.

## Uso direto (sem o lab.py)

```bash
python scripts/node.py --config configs/qwen3-small-dev-http.toml --check   # valida config e SHA-256, não inicia
python scripts/node.py --config <config.toml> --bin /caminho/llama-server   # inicia
```

O binário é procurado nesta ordem: `--bin`, a variável `LLAMA_SERVER`, e o `PATH` (o `devenv shell` coloca o
llama.cpp do Nix no `PATH`). No Windows, o `node.py` roda o `llama-server` como processo filho.

Campos da config: `node_id`, `bind_host`, `bind_port`, `public_url`, `model_file`, `model_sha256`, `threads`,
`context_tokens`, `slots`, e opcionalmente `n_gpu_layers`, `chat_template_kwargs`, `api_key_file`, `tls_certfile` e
`tls_keyfile`. Campos desconhecidos são recusados.

## Testes

```bash
python -m unittest discover -s tests -v    # 10 testes; não baixam modelo
```

O CI do GitHub Actions roda esses testes a cada push. Histórico de mudanças: [CHANGELOG.md](CHANGELOG.md).

## Teste no laboratório e apresentação

O roteiro de teste com vários PCs e o material para a apresentação (decisões técnicas, trade-offs e perguntas prováveis) estão no repositório Backend: `docs/ROTEIRO-E-APRESENTACAO.pdf`.
