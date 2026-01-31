# Branding Service

Serviço de validação determinística de marca para emails HTML da Orqestra.

## Características

- **100% Determinístico**: Não usa IA/LLM - todas as validações são baseadas em regras
- **Exposição via MCP**: Usa o Model Context Protocol para integração
- **Validações de Marca**: Cores, fontes, logo, layout, CTAs, footer, elementos proibidos

## Tools MCP

### `validate_email_brand`

Valida HTML de email contra as diretrizes de marca.

**Input:**
```json
{
  "html": "<html>...</html>"
}
```

**Output:**
```json
{
  "compliant": false,
  "score": 75,
  "violations": [
    {
      "rule": "unapproved_color",
      "category": "colors",
      "severity": "critical",
      "value": "#ff0000",
      "message": "Cor #ff0000 não está na paleta aprovada da marca"
    }
  ],
  "summary": {
    "critical": 1,
    "warning": 1,
    "info": 0,
    "total": 2
  }
}
```

### `get_brand_guidelines`

Retorna as diretrizes de marca para referência.

## Diretrizes de Marca

### Cores

- **Primárias**: `#6B7FFF`, `#8B9FFF`
- **Neutras**: `#FFFFFF`, `#F5F5F5`, `#F8F9FF`
- **Texto**: `#333333`, `#555555`, `#666666`, `#888888`, `#999999`

### Tipografia

- **Fontes aprovadas**: Arial, Helvetica, sans-serif
- **Tamanho mínimo**: 12px
- **Fontes proibidas**: Times, Comic Sans, Courier, Impact, Papyrus

### Logo

- Altura: 40-80px
- Alt text deve conter "Orqestra"

### Layout

- Largura máxima: 600px
- Background: neutro (branco ou cinza claro)

### CTAs

- Background: cor primária `#6B7FFF`
- Texto: branco `#FFFFFF`

### Footer

- Copyright: "© 2026 Orqestra"
- Link de descadastro obrigatório

### Elementos Proibidos

- Animações blink
- Text-shadow excessivo
- Rotações > 2°

## Desenvolvimento

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar localmente
python server.py
```

## Docker

```bash
# Build
docker build -t branding-service .

# Run
docker run -p 8012:8012 branding-service
```

## Pontuação

- **100**: Sem violações
- **-20**: Por cada violação crítica
- **-5**: Por cada warning
- **-1**: Por cada info
- **Mínimo**: 0

## Variáveis de Ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `PORT` | Porta do servidor | `8012` |
| `LOG_LEVEL` | Nível de log | `INFO` |
