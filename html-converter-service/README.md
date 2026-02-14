# HTML Converter Service

Converte HTML de email em imagem (PNG/JPEG), retornando em base64. Decodifica automaticamente Quoted-Printable, URL encoding e HTML entities. Exposto como REST e MCP.

Porta: 8011

## Endpoint REST

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/html-to-image/convert` | Converter HTML para imagem |

## MCP Tool (SSE em `/mcp/message`)

| Tool | Descrição |
|---|---|
| `convert_html_to_image` | Mesma conversão, acessível via MCP |

## Execução manual

Requer Java 17+ e Maven 3.6+.

```bash
mvn clean install
mvn spring-boot:run
```

## Variáveis de ambiente

Nenhuma obrigatória. Configuração em `src/main/resources/application.properties`.
