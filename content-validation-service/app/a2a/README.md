# A2A (Content Validation Service)

O content-validation-service expõe o orquestrador também via **A2A** (Agent-to-Agent), além da API REST.

## Endpoints

- **GET** `/a2a/.well-known/agent-card.json` — Agent Card (discovery)
- **POST** `/a2a/v1/message:send` ou `/a2a/v1/message/send` — Enviar mensagem (analyze-piece)

## Request (POST message:send)

Corpo no formato `SendMessageRequest` do A2A. O `message` deve ter `role: 1` (user) e `content` com um `DataPart` cujo JSON tenha:

```json
{
  "message": {
    "messageId": "msg-001",
    "role": 1,
    "content": [
      {
        "data": {
          "data": {
            "task": "VALIDATE_COMMUNICATION",
            "channel": "SMS",
            "content": { "body": "Olá, teste." }
          }
        }
      }
    ]
  }
}
```

- **task**: `"VALIDATE_COMMUNICATION"`
- **channel**: `"SMS"` | `"PUSH"` | `"EMAIL"` | `"APP"`
- **content**: conforme o canal (inline ou ref). Igual ao `POST /api/ai/analyze-piece`.

Também é aceito payload flat em `content[0].data` (sem `data.data`), desde que tenha `task`, `channel`, `content`.

## Response

`Message` com `DataPart` contendo:

- `validation_result`, `orchestration_result`, `compliance_result`
- `requires_human_approval`, `human_approval_reason`
- `final_verdict` (`status`, `message`, `contributors`)

## Config

`A2A_BASE_URL`: URL base do serviço (ex. `http://localhost:8004` ou `http://content-validation-service:8004` em Docker). O Agent Card usa essa URL para `url` e links.
