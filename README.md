# Orqestra - Sistema de Gerenciamento de Campanhas CRM

Sistema completo de gerenciamento de campanhas de CRM com validação jurídica baseada em IA, aprimoramento de textos e análise de conteúdo.

## 🏗️ Arquitetura

O projeto é composto por uma arquitetura de microserviços:

- **API Gateway**: Roteamento centralizado, autenticação e rate limiting
- **Auth Service**: Gerenciamento de usuários e autenticação JWT
- **Campaigns Service**: Gerenciamento completo do ciclo de vida de campanhas
- **Briefing Enhancer Service**: Aprimoramento de textos usando IA (LangGraph + OpenAI)
- **Content Service**: Análise e geração de conteúdo para campanhas
- **Legal Service**: Validação jurídica de comunicações usando RAG (Weaviate + OpenAI)
- **Frontend**: Interface React com TypeScript

## 📋 Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **OpenAI API Key** configurada (obrigatória)
- Mínimo **8GB de RAM** disponível para Docker

## 🚀 Execução

### 1. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (opcional, pode usar variáveis de ambiente do sistema):

```bash
OPENAI_API_KEY=sua_chave_openai_aqui
NVIDIA_APIKEY=sua_chave_nvidia_aqui  # Opcional - necessário para reranking
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
LOG_LEVEL=INFO
```

Ou exporte as variáveis:

```bash
export OPENAI_API_KEY=sua_chave_openai_aqui
```

### 2. Subir Todos os Serviços

```bash
docker-compose up -d
```

Este comando irá:
- Criar e iniciar todos os containers
- Configurar os bancos de dados
- Inicializar os serviços de infraestrutura (PostgreSQL, Redis, Weaviate, LocalStack)

### 3. Executar Ingestão de Documentos no Weaviate

**⚠️ IMPORTANTE**: A ingestão de documentos jurídicos é necessária para o funcionamento do Legal Service. Execute este passo **apenas uma vez** após subir os serviços:

```bash
docker-compose run --rm documents-ingestion
```

Este job irá:
- Extrair documentos PDF da pasta `doc-juridico`
- Processar e criar chunks semânticos
- Indexar no Weaviate para busca RAG

**Nota**: O job é batch e termina automaticamente após a conclusão. Se precisar re-executar, simplesmente rode o comando novamente.

### 4. Verificar Status dos Serviços

```bash
docker-compose ps
```

Todos os serviços devem estar com status `Up` ou `Up (healthy)`.

## 🌐 Acessos

Após subir os serviços, você pode acessar:

- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8000
- **API Gateway Docs**: http://localhost:8000/docs
- **Weaviate**: http://localhost:8080
- **Legal Service**: http://localhost:8005
- **Legal Service Docs**: http://localhost:8005/docs

## 📚 Serviços e Portas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| Frontend | 3000 | Interface React |
| API Gateway | 8000 | Gateway centralizado |
| Briefing Enhancer | 8001 | Aprimoramento de textos |
| Auth Service | 8002 | Autenticação |
| Campaigns Service | 8003 | Gerenciamento de campanhas |
| Content Service | 8004 | Análise de conteúdo |
| Legal Service | 8005 | Validação jurídica |
| PostgreSQL | 5432 | Banco de dados |
| Redis | 6379 | Cache |
| Weaviate | 8080 | Vector database |
| LocalStack | 4566 | S3 local |

## 🔧 Comandos Úteis

### Ver logs de um serviço específico
```bash
docker-compose logs -f legal-service
```

### Parar todos os serviços
```bash
docker-compose down
```

### Parar e remover volumes (limpar dados)
```bash
docker-compose down -v
```

### Reconstruir um serviço específico
```bash
docker-compose build legal-service
docker-compose up -d legal-service
```

### Verificar saúde do Weaviate
```bash
curl http://localhost:8080/v1/.well-known/ready
```

## 🐛 Troubleshooting

### Serviços não iniciam

1. Verifique se todas as portas estão livres:
```bash
docker-compose ps
```

2. Verifique os logs:
```bash
docker-compose logs
```

### Legal Service retorna erro "Nenhum documento encontrado"

Execute a ingestão de documentos:
```bash
docker-compose run --rm documents-ingestion
```

### Erro de autenticação (401 Unauthorized)

Verifique se o `SECRET_KEY` está configurado corretamente. O valor padrão em desenvolvimento é `dev-secret-key-change-in-production`.

### Weaviate não conecta

1. Verifique se o Weaviate está saudável:
```bash
curl http://localhost:8080/v1/.well-known/ready
```

2. Verifique os logs:
```bash
docker-compose logs weaviate
```

## 📖 Documentação Adicional

- [API Gateway README](api-gateway/README.md)
- [Auth Service README](auth-service/README.md)
- [Campaigns Service README](campaigns-service/README.md)
- [Briefing Enhancer Service README](briefing-enhancer-service/README.md)

## 🔐 Segurança

- Em produção, altere o `SECRET_KEY` padrão
- Configure `ENVIRONMENT=production` para habilitar cookies seguros
- Revise as configurações de CORS para seu domínio
- Mantenha as variáveis de ambiente seguras (use secrets management)

## 📝 Notas

- O projeto usa **LocalStack** para S3 local em desenvolvimento
- **Weaviate** é usado para busca vetorial e RAG no Legal Service
- **Redis** é usado para cache no Legal Service
- Todos os serviços compartilham a mesma rede Docker para comunicação interna

