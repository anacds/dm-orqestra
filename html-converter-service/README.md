# HTML to Image API

API Spring Boot que converte HTML de e-mail em imagem reduzida, retornando em formato base64.

**Exposto também como MCP Server** - permite que agentes de IA consumam o serviço via Model Context Protocol.

## Tecnologias Utilizadas

- Java 17
- Spring Boot 3.2.1
- Flying Saucer (HTML para PDF)
- Apache PDFBox (PDF para Imagem)
- Apache Commons Codec (Decodificação de email)
- **MCP Java SDK** (Model Context Protocol)
- Lombok
- Maven

## Funcionalidades

- ✅ Converte HTML em imagem
- ✅ Decodificação automática de encodings de email (Quoted-Printable, URL, Base64, HTML Entities)
- ✅ Redução de tamanho da imagem (escala configurável)
- ✅ Retorna imagem em base64
- ✅ Suporta formatos PNG e JPEG
- ✅ Validação de entrada
- ✅ Tratamento global de erros
- ✅ Logging detalhado
- ✅ **MCP Server nativo** - expõe tool `convert_html_to_image` para agentes de IA

## Como Executar

### Requisitos

- Java 17 ou superior
- Maven 3.6+

### Passos

1. Compile o projeto:
```bash
mvn clean install
```

2. Execute a aplicação:
```bash
mvn spring-boot:run
```

A API estará disponível em: `http://localhost:8011`

## Endpoints

### 1. Converter HTML para Imagem

**POST** `/api/v1/html-to-image/convert`

#### Request Body

```json
{
  "htmlContent": "<html><body><h1>Olá Mundo!</h1></body></html>",
  "width": 800,
  "height": 600,
  "scale": 0.5,
  "imageFormat": "PNG"
}
```

#### Parâmetros

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| htmlContent | String | Sim | - | Conteúdo HTML do e-mail |
| width | Integer | Não | 800 | Largura da imagem original |
| height | Integer | Não | 600 | Altura da imagem original |
| scale | Float | Não | 0.5 | Fator de escala (0.5 = 50% do tamanho) |
| imageFormat | String | Não | PNG | Formato da imagem (PNG ou JPEG) |

#### Response

```json
{
  "base64Image": "iVBORw0KGgoAAAANSUhEUgAA...",
  "imageFormat": "PNG",
  "originalWidth": 2550,
  "originalHeight": 3300,
  "reducedWidth": 1275,
  "reducedHeight": 1650,
  "fileSizeBytes": 123456
}
```

### 2. Health Check

**GET** `/api/v1/html-to-image/health`

Retorna: `"HTML to Image API is running"`

---

## MCP Server (Model Context Protocol)

O serviço expõe um **MCP Server nativo** que permite que agentes de IA (como Claude, GPT, etc.) consumam a funcionalidade de conversão HTML-para-imagem sem precisar conhecer a implementação por trás.

### Endpoints MCP

| Endpoint | Descrição |
|----------|-----------|
| `/sse` | SSE endpoint para conexão do cliente MCP |
| `/mcp/message` | Endpoint para mensagens do protocolo MCP |

### Tool Disponível

#### `convert_html_to_image`

Converte conteúdo HTML em imagem Base64.

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Default | Descrição |
|-----------|------|-------------|---------|-----------|
| `htmlContent` | string | Sim | - | HTML a converter |
| `scale` | number | Não | 0.5 | Fator de escala (0.1 a 2.0) |
| `imageFormat` | string | Não | "PNG" | Formato: "PNG" ou "JPEG" |

**Resposta:**

```json
{
  "success": true,
  "base64Image": "iVBORw0KGgo...",
  "imageFormat": "PNG",
  "originalWidth": 2550,
  "originalHeight": 3300,
  "reducedWidth": 1275,
  "reducedHeight": 1650,
  "fileSizeBytes": 123456
}
```

### Configuração no Cursor/Claude Desktop

Adicione ao seu arquivo de configuração MCP:

```json
{
  "mcpServers": {
    "html-converter": {
      "url": "http://localhost:8011/sse"
    }
  }
}
```

### Exemplo de Uso por Agente

Quando um agente de IA se conecta ao MCP Server, ele pode invocar a tool assim:

```
Tool: convert_html_to_image
Arguments: {
  "htmlContent": "<html><body><h1>Hello World</h1></body></html>",
  "scale": 0.5,
  "imageFormat": "PNG"
}
```

---

## Exemplos de Uso

### Usando cURL

```bash
curl -X POST http://localhost:8011/api/v1/html-to-image/convert \
  -H "Content-Type: application/json" \
  -d '{
    "htmlContent": "<html><body><h1>Meu Email</h1><p>Conteúdo do email aqui</p></body></html>",
    "scale": 0.5,
    "imageFormat": "PNG"
  }'
```

### Usando JavaScript/Fetch

```javascript
const response = await fetch('http://localhost:8011/api/v1/html-to-image/convert', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    htmlContent: '<html><body><h1>Olá!</h1></body></html>',
    scale: 0.5,
    imageFormat: 'PNG'
  })
});

const data = await response.json();
console.log(data.base64Image);

// Para exibir a imagem:
const img = document.createElement('img');
img.src = `data:image/png;base64,${data.base64Image}`;
document.body.appendChild(img);
```

## HTML de E-mail

O serviço aceita HTML completo ou fragmentos. Se você enviar apenas um fragmento (sem tags `<html>`, `<head>`, `<body>`), o serviço automaticamente envolverá seu conteúdo em uma estrutura XHTML válida.

### Decodificação Automática

O serviço detecta e decodifica automaticamente os seguintes formatos comuns em emails:

- **Quoted-Printable**: `=3D` → `=`, `=0A` → newline
- **URL Encoding**: `%20` → espaço, `%3D` → `=`
- **HTML Entities**: `&lt;` → `<`, `&amp;` → `&`
- **Base64**: Conteúdo codificado em Base64

### Importante para XHTML

O renderizador (Flying Saucer) requer HTML bem formado no padrão XHTML:

- Todas as tags devem ser fechadas: `<br />`, `<img ... />`, `<meta ... />`
- Use `&#160;` em vez de `&nbsp;`
- Atributos devem estar entre aspas

## Configurações

Edite `application.properties` para ajustar:

- Porta do servidor
- Tamanho máximo de requisição
- Níveis de log

## Tratamento de Erros

A API retorna erros estruturados:

```json
{
  "timestamp": "2026-01-29T10:30:00",
  "status": 422,
  "error": "Unprocessable Entity",
  "message": "Failed to convert HTML to image: The element type 'meta' must be terminated..."
}
```

| Status | Descrição |
|--------|-----------|
| 400 | Erro de validação (campo obrigatório faltando, etc) |
| 422 | Erro de conversão (HTML malformado, etc) |
| 500 | Erro interno do servidor |

## Notas Importantes

1. **Tamanho do HTML**: A API suporta até 10MB de conteúdo HTML
2. **Escala**: Valores menores produzem imagens menores (ex: 0.3 = 30% do tamanho original)
3. **Formato**: PNG oferece melhor qualidade, JPEG gera arquivos menores
4. **Performance**: HTML complexo pode levar alguns segundos para processar

## Estrutura do Projeto

```
src/main/java/com/example/htmlconverter/
├── HtmlConverterApplication.java      # Classe principal
├── config/
│   └── McpServerConfig.java           # Configuração do MCP Server
├── controller/
│   └── HtmlConverterController.java   # REST endpoints
├── dto/
│   ├── ConversionRequest.java         # Request DTO
│   └── ConversionResponse.java        # Response DTO
├── service/
│   ├── HtmlConversionService.java     # Orquestração da conversão
│   ├── HtmlDecoderService.java        # Decodificação de encodings
│   └── ImageProcessingService.java    # Processamento de imagens
└── exception/
    ├── ConversionException.java       # Exception de domínio
    └── GlobalExceptionHandler.java    # Handler global de erros
```

## Licença

Este projeto é open source e está disponível para uso livre.
