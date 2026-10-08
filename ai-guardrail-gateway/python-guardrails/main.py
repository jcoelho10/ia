from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import httpx
import re
import logging

# Configuracao de Logs para Observabilidade
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("guardrails-service")

app = FastAPI(
    title="AI Guardrails & Security Service",
    description="Serviço de inspeção de prompts, sanitização de PII e prevenção de Prompt Injection",
    version="1.0.0"
)

# Inicializacao dos motores do Microsoft Presidio
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

class PromptRequest(BaseModel):
    prompt: str

class PromptResponse(BaseModel):
    original_prompt: str
    sanitized_prompt: str
    is_safe: bool
    llm_response: str = None

def detect_prompt_injection(text: str) -> bool:
    """
    Inspeção baseada em padrões do OWASP Top 10 para LLMs (LLM01: Prompt Injection).
    Detecta tentativas de sobrescrever o System Prompt ou instruir o modelo a burlar regras.
    """
    injection_patterns = [
        r"ignore (all|previous) instructions",
        r"you are now an usrestricted ai",
        r"system prompt override",
        r"bypass security rules",
        r"do anything now",
        r"dan mode",
        r"revelar instrucoes internas"
    ]
    for pattern in injection_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

@app.post("/validate-and-execute", response_model=PromptResponse)
async def validate_and_execute(request: PromptRequest):
    logger.info(f"Recebendo requisição para validação de prompt.")

    # 1. Validacao de Seguranca contra Prompt Injection
    if detect_prompt_injection(request.prompt):
        logger.warning(f"Ataque de Prompt Injection detectado e bloqueado!")
        raise HTTPException(
            status_code=400,
            detail="Requisição bloqueada: Tentativa de manipulação de prompt (Prompt Injection) detectada por políticas de segurança."
        )

    # 2. Sanitizacao de Dados Sensiveis (PII / LGPD)
    # Detecta e mascarara automaticamente e-mails, telefones e numeros de documentos
    analysis_results = analyzer.analyze(
        text=request.prompt,
        entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CPF", "CREDIT_CARD"],
        language="en"
    )
    anonymized_result = anonymizer.anonymize(
        text=request.prompt,
        analyzer_results=analysis_results
    )
    sanitized_prompt = anonymized_result.text

    if sanitized_prompt != request.prompt:
        logger.info("Dados sensíveis (PII) identificados e anonimizados com sucesso.")

    # 3. Encaminhamento para a LLM Local (Ollama - Llama 3)
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": sanitized_prompt,
        "stream": False
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(ollama_url, json=payload, timeout=60.0)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Falha ao obter resposta do modelo de LLM.")

            response_json = response.json()
            llm_text = response_json.get("response", "")
        except httpx.ConnectError:
            logger.error("Não foi possível conectar ao container do Ollama na porta 11434.")
            raise HTTPException(
                status_code=503,
                detail="Serviço de LLM (Ollama) temporariamente indisponível. Verifique se o container está rodando."
            )

    return PromptResponse(
        original_prompt=request.prompt,
        sanitized_prompt=sanitized_prompt,
        is_safe=True,
        llm_response=llm_text
    )