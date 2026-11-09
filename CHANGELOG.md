# Changelog — Nó LLM

## 09/11/2026 — Plano v2

Detalhes e motivos no Backend: `docs/MUDANCAS.md` (itens 2, 4 e 14). Estado anterior: tag `antes-do-plano-v2`.

- **Novo:** `api_key_file` na config do nó, passado como `--api-key-file` ao `llama-server`. Com a chave, o nó pode
  ouvir em HTTP na rede do laboratório; sem ela, HTTP fora do loopback continua proibido.
- **Novo:** `--bin` e a variável `LLAMA_SERVER` escolhem o binário, para usar o `llama-server` oficial baixado pelo
  `lab.py` do Backend sem depender do devenv.
- **Alterado:** no Windows, o `node.py` roda o `llama-server` como filho, porque o `execvp` perderia o controle do
  processo.
- **Corrigido:** os 4 testes que falhavam no Windows (caminhos com `\` no TOML; Git Bash convertendo `/CN=...`; modo
  0600 que o Windows não representa).
- **Novo:** 3 testes (chave de API, HTTP na LAN sem chave, busca do binário); CI no GitHub Actions; diagramas no
  `EXPLICACAO.md`; `bin/` no `.gitignore`.

## 02/11/2026

- Nó LLM separado do Backend: `node.py`, manifesto de modelos com SHA-256, perfis HTTP e HTTPS, script de certificado
  (commits do Daniel).
