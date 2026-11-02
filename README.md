# UFES Redes Trab2 — LLM Node

Pacote de implantação reutilizável para N nós: cada processo executa um runtime llama.cpp residente, com configuração própria por host, ID/porta/modelo/slots fixados. Este repositório não contém gateway, balanceador, fila de aplicação, token de usuário ou lógica de domínio.

## CPU e modelos

Entre em `devenv shell`. Os manifestos e hashes esperados ficam em `models/manifest.json`; os pesos GGUF não são versionados. `scripts/download-models` baixa revisões fixas e valida SHA-256. Confirme model cards/licenças oficiais antes de redistribuir. `python scripts/node.py --config configs/qwen3-small.toml --check` valida configuração, arquivo e hash sem iniciar inferência. Durante a migração, os pesos legados não foram copiados: valide-os explicitamente com `--models-root "../Tudo Junto/models"`.

`./scripts/start-node --config configs/qwen3-small.toml` inicia a réplica após verificação estrita do hash. Configure réplicas com IDs e portas distintos. Cada profile publica HTTPS e referencia certificado/chave em `secrets/`; provisione por host e acrescente a CA ao trust bundle privado do Backend. Nunca copie a chave ao Backend. Perfis de exemplo reservam slots/threads por processo: distribua threads dentro do budget total da máquina; não some RSS para estimar RAM física compartilhada.

O bind é separado do endereço público que o Backend usa. Em rede não confiável, exponha atrás de TLS e ACL/autenticação de serviço; nunca exponha llama-server diretamente à Internet. Não encaminhe tokens de usuário ao nó.

## GPU

`n_gpu_layers` é configuração por processo e permanece 0 no baseline CPU. Perfil GPU é futuro e exige validação de VRAM/contexto sem substituir resultados CPU.
