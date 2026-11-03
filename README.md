# UFES Redes Trab2 — LLM Node

Pacote de implantação reutilizável para N nós: cada processo executa um runtime llama.cpp residente, com configuração própria por host, ID/porta/modelo/slots fixados. Este repositório não contém gateway, balanceador, fila de aplicação, token de usuário ou lógica de domínio.

## CPU e modelos

Entre em `devenv shell`. Os manifestos e hashes esperados ficam em `models/manifest.json`; os pesos GGUF não são versionados. `scripts/download-models` baixa revisões fixas para `models/` e valida SHA-256. Confirme model cards/licenças oficiais antes de redistribuir. O fluxo independente padrão é baixar os pesos para esse diretório e executar `python scripts/node.py --config configs/qwen3-small.toml --check`; isso valida configuração, arquivo e hash, mas não inicia inferência.

`model_file` relativo é resolvido dentro de `models_root`, mantendo subdiretórios e rejeitando traversal. Por padrão, a raiz é `models/` deste repositório; `models_root` relativo no TOML é relativo ao diretório do arquivo de configuração. Para pesos já armazenados fora do repositório, passe `--models-root /caminho/autorizado` (caminhos relativos desse argumento são relativos ao diretório corrente). Um `model_file` absoluto é aceito explicitamente. O download/verificação e a escolha de uma raiz externa não dependem de uma cópia legada.

`tls_certfile`/`tls_keyfile` relativos são resolvidos a partir da raiz do repositório LLM, não do diretório corrente. `public_url` deve usar host/porta do endpoint e não aceita caminhos, credenciais ou query.

Perfis `*-dev-http.toml` destinam-se somente a desenvolvimento em loopback confiável e devem corresponder aos URLs HTTP no `configs/cpu_minimal.toml` do Backend. Os perfis normais usam HTTPS; gere certificado e chave por host, com SAN igual ao DNS/IP usado pelo Backend, por exemplo `devenv shell -- scripts/create-node-cert.sh llm-small-a llm-small-a`. O certificado é self-signed: agregue os certificados públicos dos nós ao trust bundle local do Backend (`backend_ca_file=secrets/llm-nodes-ca.pem`); a chave privada fica somente no host LLM em `secrets/llm-small-a.key`. O script recusa sobrescrever arquivos, permite `NODE_SECRETS_DIR`, `CERT_DAYS` e SANs extras, mas não é uma PKI para provisionamento remoto. Em hosts remotos, gere chave/CSR no destino e assine com CA aprovada.

`./scripts/start-node --config configs/qwen3-small.toml` inicia a réplica após verificação estrita do hash. Configure réplicas com IDs e portas distintos. Cada profile publica HTTPS e referencia certificado/chave em `secrets/`; provisione por host e acrescente a CA ao trust bundle privado do Backend. Nunca copie a chave ao Backend. Perfis de exemplo reservam slots/threads por processo: distribua threads dentro do budget total da máquina; não some RSS para estimar RAM física compartilhada.

O bind é separado do endereço público que o Backend usa. Em rede não confiável, exponha atrás de TLS e ACL/autenticação de serviço; nunca exponha llama-server diretamente à Internet. Não encaminhe tokens de usuário ao nó.

## GPU

`n_gpu_layers` é configuração por processo e permanece 0 no baseline CPU. Perfil GPU é futuro e exige validação de VRAM/contexto sem substituir resultados CPU.
