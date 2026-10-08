# 🛡️ AI Guardrail Gateway Architecture

> **Enterprise AI Security & Governance Gateway**

Arquitetura de referência para o consumo seguro e governado de **Large Language Models (LLMs)**.

O **AI Guardrail Gateway** atua como uma camada intermediária entre as aplicações consumidoras e o provedor de IA (**Ollama / Llama 3**), aplicando:

* 🔒 Sanitização de dados sensíveis — LGPD/GDPR
* 🛡️ Validação de segurança de prompts
* 🚦 Controle de tráfego — Rate Limiting
* 📊 Observabilidade centralizada

---

## 🎯 Arquitetura da Solução

```text
┌─────────────────────────────┐
│         Cliente / App       │
└──────────────┬──────────────┘
               │
               │ HTTP POST
               │ /api/v1/ai/validate-and-execute
               │ :8080
               ▼
┌─────────────────────────────────────────────┐
│         Spring Cloud Gateway                │
│                 Java 21                     │
│                                             │
│  KeyResolver: IP do cliente                 │
│  RequestRateLimiter                         │
└──────────────┬──────────────────────────────┘
               │
               │ Rate Limiting
               ▼
        ┌───────────────┐
        │ Redis 7       │
        │ :6379         │
        │ Token Bucket  │
        └───────────────┘
               │
               │ HTTP POST
               │ /validate-and-execute
               │ StripPrefix=3
               │ :8000
               ▼
┌─────────────────────────────────────────────┐
│          FastAPI Guardrail Engine           │
│                Python 3.13                 │
│                                             │
│  Presidio Analyzer + Spacy                 │
│  pt_core_news_sm                            │
│  Anonimização de PII                        │
│  Validação de Prompt Injection              │
└──────────────┬──────────────────────────────┘
               │
               │ HTTP POST
               │ /api/generate
               │ :11434
               ▼
┌─────────────────────────────────────────────┐
│              Ollama Server                  │
│                                             │
│  Docker: ai_ollama                          │
│  Modelo: Llama 3                            │
└─────────────────────────────────────────────┘
```

---

## 🧩 Componentes do Ecossistema

| Componente             | Tecnologia                       | Container / Porta      | Responsabilidade                                     |
| ---------------------- | -------------------------------- | ---------------------- | ---------------------------------------------------- |
| **Edge Gateway**       | Spring Cloud Gateway 4 / Java 21 | Native — `:8080`       | Entrada única, roteamento reativo e Rate Limiting.   |
| **Rate Limit Storage** | Redis 7 Alpine                   | `ai_redis` — `:6379`   | Controle reativo do algoritmo Token Bucket.          |
| **Guardrail Engine**   | FastAPI / Python 3.13            | Native — `:8000`       | Sanitização de PII com Microsoft Presidio + Spacy.   |
| **LLM Provider**       | Ollama                           | `ai_ollama` — `:11434` | Execução local do modelo `llama3:latest`.            |
| **Observabilidade**    | Grafana + Loki + Promtail        | `ai_grafana` — `:3000` | Coleta, agregação e navegação de logs centralizados. |

---

# 🚀 Como Executar a Solução

## Pré-requisitos

Antes de iniciar o projeto, certifique-se de possuir:

* Docker Desktop ativo
* Java 21
* Maven
* Python 3.13

---

## 1️⃣ Subir a Infraestrutura

Na raiz do projeto, inicialize os serviços de infraestrutura:

* Ollama
* Redis
* Grafana
* Loki
* Promtail

```bash
docker compose up -d
```

---

## 2️⃣ Subir o Guardrail Engine

Abra uma nova aba do terminal e acesse a pasta do serviço Python.

### PowerShell

```powershell
cd python-guardrails

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

python -m spacy download pt_core_news_sm

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

O FastAPI ficará disponível em:

```text
http://localhost:8000
```

### Swagger

A documentação interativa estará disponível em:

```text
http://localhost:8000/docs
```

---

## 3️⃣ Subir o API Gateway

Na pasta do projeto Java:

```bash
mvn spring-boot:run
```

O Spring Cloud Gateway ficará disponível na porta:

```text
http://localhost:8080
```

---

# 🔄 Sequência de Inicialização

A ordem recomendada para iniciar a solução é:

```text
1. Docker Compose
       │
       ├── Redis
       ├── Ollama
       ├── Grafana
       ├── Loki
       └── Promtail
       │
       ▼
2. FastAPI Guardrail Engine
       │
       ├── Presidio
       └── Spacy
       │
       ▼
3. Spring Cloud Gateway
       │
       └── Rate Limiting → Redis
       │
       ▼
4. Cliente / Testes
```

Após a inicialização, o fluxo de uma requisição será:

```text
Cliente
   │
   ▼
Spring Cloud Gateway :8080
   │
   ├── KeyResolver: IP
   │
   └── RequestRateLimiter
          │
          ▼
       Redis :6379
          │
          ▼
FastAPI Guardrail :8000
   │
   ├── Presidio
   ├── Spacy
   ├── Sanitização de PII
   └── Validação de Prompt Injection
          │
          ▼
Ollama :11434
   │
   ▼
Llama 3
```

---

# 🧪 Validando a Arquitetura

## Teste 1 — Sanitização de Dados Sensíveis

### LGPD

Este teste valida a substituição automática de **e-mail** e **telefone** por placeholders antes do envio ao Llama 3.

### PowerShell

```powershell
$json = '{"prompt": "Olá! Meu e-mail é joao.silva@exemplo.com.br e meu celular é 11999998888. Resuma esta mensagem."}'

$body = [System.Text.Encoding]::UTF8.GetBytes($json)

Invoke-RestMethod `
  -Uri "http://localhost:8080/api/v1/ai/validate-and-execute" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

### Retorno Esperado

```json
{
  "original_prompt": "Olá! Meu e-mail é joao.silva@exemplo.com.br e meu celular é 11999998888. Resuma esta mensagem.",
  "sanitized_prompt": "Olá! Meu e-mail é <EMAIL_ADDRESS> e meu celular é <PHONE_NUMBER>. Resuma esta mensagem.",
  "is_safe": true,
  "llm_response": "..."
}
```

---

## Teste 2 — Rate Limiting Reativo

### Redis

Este teste valida o bloqueio de tráfego no Spring Cloud Gateway ao exceder o limite de requisições por segundo.

### PowerShell

```powershell
1..15 | ForEach-Object {
    $i = $_

    try {
        $json = '{"prompt": "Teste de carga para rate limit."}'

        $body = [System.Text.Encoding]::UTF8.GetBytes($json)

        $res = Invoke-RestMethod `
          -Uri "http://localhost:8080/api/v1/ai/validate-and-execute" `
          -Method Post `
          -ContentType "application/json; charset=utf-8" `
          -Body $body

        Write-Host "Requisição $i : OK (HTTP 200)" -ForegroundColor Green
    }
    catch {
        Write-Host "Requisição $i : Bloqueada pelo Rate Limiter (HTTP 429)" -ForegroundColor Red
    }
}
```

---

# 📊 Dashboard de Observabilidade

## Grafana

Acesse:

```text
http://localhost:3000
```

Credenciais:

```text
Usuário: admin
Senha: admin
```

---

## 🔎 Consultando Logs no Grafana

No Grafana:

```text
Explore
   ↓
Fonte de dados: Loki
   ↓
LogQL
```

### Logs da LLM

```logql
{container_name="ai_ollama"}
```

### Logs do Collector

```logql
{container_name="ai_promtail"}
```

---

# 📌 Roadmap de Evolução

### Implementado

* [x] Roteamento reativo com Spring Cloud Gateway
* [x] Controle de vazão (Rate Limiting) com Redis Token Bucket
* [x] Sanitização automática de PII em português (Presidio + Spacy)
* [x] Agregação de logs com Promtail + Loki + Grafana


