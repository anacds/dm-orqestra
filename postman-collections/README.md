# Postman Collections - Orqestra API

Este diretório contém as collections do Postman para todos os serviços da arquitetura Orqestra.

## Collections Disponíveis

### 1. Orqestra-API-Complete.postman_collection.json
Collection completa com todos os endpoints de todos os serviços, roteados através do API Gateway.

**Uso recomendado**: Para testar o fluxo completo da aplicação através do gateway.

### 2. Auth-Service.postman_collection.json
Collection específica para o serviço de autenticação.

**Endpoints incluídos**:
- `POST /api/auth/register` - Registrar novo usuário
- `POST /api/auth/login` - Login (OAuth2)
- `POST /api/auth/refresh` - Renovar access token
- `GET /api/auth/me` - Obter informações do usuário atual
- `POST /api/auth/logout` - Revogar refresh token

### 3. Campaigns-Service.postman_collection.json
Collection específica para o serviço de campanhas.

**Endpoints incluídos**:
- **Campaigns**: CRUD completo (GET, POST, PUT, DELETE)
- **Comments**: Adicionar comentários
- **Creative Pieces**: Submeter peças criativas (SMS/Push), upload de arquivos (App/E-mail), deletar arquivos

### 4. Briefing-Enhancer-Service.postman_collection.json
Collection específica para o serviço de aprimoramento de texto.

**Endpoints incluídos**:
- `POST /api/enhance-objective` - Aprimorar texto usando IA
- `GET /api/health` - Health check

### 5. AI-Studio-Service.postman_collection.json
Collection específica para o serviço de análise de peças criativas.

**Endpoints incluídos**:
- `POST /api/ai/analyze-piece` - Analisar peça criativa (SMS ou Push)
- `GET /api/ai/analyze-piece/{campaign_id}/{channel}` - Obter análise existente

## Variáveis de Ambiente

Todas as collections incluem variáveis que podem ser configuradas no Postman:

### Variáveis Globais (Orqestra-API-Complete)
- `api_gateway_url`: `http://localhost:8000`
- `auth_service_url`: `http://localhost:8002`
- `campaigns_service_url`: `http://localhost:8003`
- `briefing_enhancer_url`: `http://localhost:8001`
- `ai_studio_url`: `http://localhost:8004`
- `access_token`: (preenchido automaticamente após login)
- `refresh_token`: (preenchido automaticamente após login)
- `campaign_id`: (preencher manualmente após criar uma campanha)

### Variáveis por Collection
Cada collection individual tem suas próprias variáveis específicas.

## Como Usar

### 1. Importar Collections
1. Abra o Postman
2. Clique em "Import"
3. Selecione os arquivos `.postman_collection.json` que deseja importar

### 2. Configurar Variáveis de Ambiente
1. Crie um novo Environment no Postman
2. Configure as variáveis de URL conforme seu ambiente:
   - **Local**: `http://localhost:XXXX`
   - **Docker**: Use os nomes dos serviços (ex: `http://api-gateway:8000`)
   - **Produção**: URLs de produção

### 3. Fluxo de Teste Recomendado

1. **Autenticação**:
   - Execute `Login` (Auth Service)
   - Os tokens serão salvos automaticamente nas variáveis

2. **Criar Campanha**:
   - Execute `Create Campaign` (Campaigns Service)
   - Copie o `id` da resposta e configure na variável `campaign_id`

3. **Trabalhar com Campanha**:
   - Use os outros endpoints para adicionar comentários, submeter peças, etc.

4. **Análise de Peças**:
   - Execute `Analyze Piece` (AI Studio Service) para validar peças criativas
   - Execute `Get Analysis` para recuperar análises existentes

## Autenticação

A maioria dos endpoints requer autenticação JWT. O token é automaticamente incluído no header `Authorization` usando a variável `{{access_token}}`.

**Nota**: O endpoint `Login` tem um script de teste que automaticamente salva os tokens nas variáveis de ambiente após um login bem-sucedido.

## Exemplos de Uso

### Criar uma Campanha Completa

1. Login -> Obter token
2. Create Campaign -> Obter `campaign_id`
3. Submit Creative Piece (SMS) -> Submeter texto SMS
4. Analyze Piece (SMS) -> Validar o texto
5. Upload App File -> Enviar imagem
6. Add Comment -> Adicionar comentário

### Validar Peça Criativa

1. Login -> Obter token
2. Analyze Piece (SMS) -> Analisar texto SMS
3. Get Analysis (SMS) -> Verificar resultado da análise

## Troubleshooting

### Erro 401 Unauthorized
- Verifique se o token está configurado corretamente
- Execute o endpoint `Login` novamente para obter um novo token
- Verifique se o token não expirou (tokens JWT têm tempo de expiração)

### Erro 404 Not Found
- Verifique se o `campaign_id` está correto
- Verifique se a URL do serviço está correta
- Se estiver usando API Gateway, verifique se o gateway está roteando corretamente

### Erro 403 Forbidden
- Verifique se o usuário tem permissão para a ação
- Alguns endpoints requerem roles específicas (ex: Creative Analyst para submeter peças)

## Notas Importantes

- **API Gateway**: A collection completa usa o API Gateway como ponto de entrada único
- **Serviços Individuais**: As collections individuais podem ser usadas para testar serviços diretamente
- **Formato de Dados**: Todos os endpoints esperam JSON, exceto uploads de arquivo que usam `multipart/form-data`
- **OAuth2 Login**: O endpoint de login usa `application/x-www-form-urlencoded` (padrão OAuth2)

