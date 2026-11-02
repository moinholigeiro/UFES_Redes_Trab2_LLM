# Contrato runtime interno v1

O Backend envia HTTP POST `/v1/chat/completions` com `stream=true`, OpenAI-compatible SSE. Uma tentativa válida contém zero ou mais frames JSON `choices[]` (delta content opcional e no máximo um finish reason `stop`/`length`), usage opcional e exatamente um `[DONE]` final. EOF sem `[DONE]`, finish ausente/incompatível, frame malformado ou bytes depois da terminação falham a tentativa; a implementação do Backend fixa o parser estrito.

`GET /health` é liveness apenas. Metadados versionados de readiness/modelo/hash/template/slots serão publicados pelo runtime em incremento posterior; até lá, não anunciar readiness sem verificar modelo e processo. Nós não recebem token de usuário, não escolhem domínio/modelo e não balanceiam.
