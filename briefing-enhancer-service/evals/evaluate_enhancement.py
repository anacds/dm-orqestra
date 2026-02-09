"""
Avaliação do Briefing Enhancer Service — LLM-as-a-Judge
Comparação: sabiazinho-4 (Maritaca) vs gpt-5-nano (OpenAI)

Fluxo:
  1. Carrega dataset CSV (campaign_name, field_name, original_text)
  2. Para cada linha, aprimora o texto com sabiazinho-4 (Maritaca)
  3. Para cada linha, aprimora o texto com gpt-5-nano (OpenAI)
  4. GPT-5.2 atua como juiz, comparando os dois textos aprimorados
  5. Gera relatório com win-rate global e por campo

Execução:
  docker compose exec briefing-enhancer-service python evals/evaluate_enhancement.py
  docker compose exec briefing-enhancer-service python evals/evaluate_enhancement.py --judge-model gpt-5.2
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.agent.graph import create_enhancement_graph
from app.agent.schemas import EnhancedTextResponse
from app.agent.state import EnhancementGraphState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Modelos competidores
# ═══════════════════════════════════════════════════════════════════════

COMPETITORS = {
    "maritaca": {
        "label": "sabiazinho-4 (Maritaca)",
        "model_name": "sabiazinho-4",
        "env_key": "MARITACA_API_KEY",
        "base_url_env": "MARITACA_BASE_URL",
        "base_url_default": "https://chat.maritaca.ai/api",
    },
    "openai": {
        "label": "gpt-5-nano (OpenAI)",
        "model_name": "gpt-5-nano",
        "env_key": "OPENAI_API_KEY",
        "base_url_env": None,
        "base_url_default": "https://api.openai.com/v1",
    },
}

# ═══════════════════════════════════════════════════════════════════════
# Field guidelines (idênticas ao seed da migration 001)
# O juiz precisa conhecer para avaliar de forma justa
# ═══════════════════════════════════════════════════════════════════════

FIELD_GUIDELINES = {
    "businessObjective": {
        "display_name": "Objetivo de Negócio",
        "expectations": (
            "O objetivo de negócio deve ser claro e alinhado com as metas estratégicas "
            "da empresa. Deve descrever o que se pretende alcançar com a campanha e como "
            "os clientes serão tocados, evitando termos vagos ou genéricos."
        ),
        "improvement_guidelines": (
            "Aprimore tornando o objetivo mais específico, eliminando ambiguidades e "
            "garantindo que seja acionável. Evite objetivos muito amplos que não possam "
            "ser medidos."
        ),
    },
    "expectedResult": {
        "display_name": "Resultado Esperado / KPI Principal",
        "expectations": (
            "O resultado esperado deve ser mensurável e relacionado diretamente ao "
            "objetivo de negócio. Deve incluir métricas claras (porcentagens, valores, "
            "prazos) e ser realista."
        ),
        "improvement_guidelines": (
            "Aprimore especificando placeholders para métricas concretas e prazos claros, "
            "garantindo que o resultado seja mensurável e diretamente relacionado ao "
            "objetivo de negócio definido."
        ),
    },
    "targetAudienceDescription": {
        "display_name": "Descrição do Público-Alvo",
        "expectations": (
            "A descrição do público-alvo deve ser específica e detalhada, incluindo "
            "características demográficas, psicográficas, comportamentais e de necessidade. "
            "Deve ser suficientemente segmentada para permitir estratégias eficazes."
        ),
        "improvement_guidelines": (
            "Aprimore adicionando placeholders para que o usuário especifique detalhes "
            "demográficos específicos (idade, gênero, localização), características "
            "psicográficas (interesses, valores), comportamentos e necessidades claras. "
            "Evite descrições muito genéricas ou amplas demais. Transforme em bullets."
        ),
    },
    "exclusionCriteria": {
        "display_name": "Critérios de Exclusão",
        "expectations": (
            "Os critérios de exclusão devem ser claros e específicos, definindo quem não "
            "deve ser incluído na campanha. Devem ser complementares à descrição do "
            "público-alvo e ajudar a refinar o segmento. Os critérios obrigatórios são: "
            "excluir clientes menores de 18 anos e com restrições na base de Riscos."
        ),
        "improvement_guidelines": (
            "Aprimore tornando os critérios mais específicos e mensuráveis. Garanta que "
            "os critérios sejam complementares ao público-alvo definido e ajudem a evitar "
            "desperdício de recursos em audiências não relevantes. Adicione os critérios "
            "obrigatórios se já não estiverem no texto. Transforme em bullets."
        ),
    },
}


JUDGE_SYSTEM_PROMPT = """Você é um avaliador especialista em qualidade de textos para campanhas de CRM.
Sua tarefa é comparar dois textos aprimorados por modelos de IA diferentes para um mesmo campo de briefing,
e decidir qual aprimoramento é melhor considerando as diretrizes e expectativas específicas desse campo.

Você também recebe o texto original (escrito pelo humano) como referência.
Ambos os textos são aprimoramentos do mesmo original. Avalie qual fez um trabalho melhor.

Você deve ser imparcial e avaliar com base em clareza, especificidade, aderência às diretrizes, acionabilidade, 
estrutura e fidelidade ao sentido original."""


def build_judge_prompt(
    field_name: str,
    campaign_name: str,
    original_text: str,
    text_a: str,
    text_b: str,
) -> str:
    guidelines = FIELD_GUIDELINES.get(field_name, {})
    display = guidelines.get("display_name", field_name)
    expectations = guidelines.get("expectations", "N/A")
    improvement = guidelines.get("improvement_guidelines", "N/A")

    return f"""Campanha: {campaign_name}
Campo: {display} ({field_name})

=== DIRETRIZES DO CAMPO ===
O que se espera: {expectations}
Diretrizes de melhoria: {improvement}

=== TEXTO ORIGINAL ===
{original_text}

=== TEXTO APRIMORADO A ===
{text_a}

=== TEXTO APRIMORADO B ===
{text_b}

Ambos os textos são aprimoramentos do texto original, gerados por modelos de IA diferentes.
Compare os textos A e B com base nas diretrizes acima.
Responda EXCLUSIVAMENTE no seguinte formato JSON (sem markdown, sem texto extra):

{{
  "winner": "A" ou "B" ou "TIE",
  "score_a": <1-5>,
  "score_b": <1-5>,
  "justification": "<explicação concisa em 1-2 frases>"
}}

Critérios de pontuação (1-5):
1 = Muito vago, genérico, sem aderência às diretrizes
2 = Parcialmente adequado, mas com lacunas significativas
3 = Adequado, mas com margem de melhoria
4 = Bom, atende a maioria das diretrizes
5 = Excelente, claro, específico e totalmente aderente"""


# ═══════════════════════════════════════════════════════════════════════
# Enhancement: cria o graph com um modelo específico
# ═══════════════════════════════════════════════════════════════════════

def _load_models_config() -> dict:
    config_file = Path("config/models.yaml")
    if config_file.exists():
        with open(config_file) as f:
            return yaml.safe_load(f) or {}
    return {}


def build_enhancer_graph(model_key: str, db_session):
    config = _load_models_config()
    enhancement_cfg = config.get("models", {}).get("enhancement", {})

    comp = COMPETITORS[model_key]
    api_key = os.getenv(comp["env_key"], "").strip()
    if not api_key:
        raise ValueError(f"Env var {comp['env_key']} is required for {comp['label']}")

    if comp["base_url_env"]:
        base_url = os.getenv(comp["base_url_env"], comp["base_url_default"])
    else:
        base_url = comp["base_url_default"]

    temperature = float(enhancement_cfg.get("temperature", 0.3))
    timeout = int(enhancement_cfg.get("timeout", 30))
    max_retries = int(enhancement_cfg.get("max_retries", 2))

    def _is_reasoning_model(name: str) -> bool:
        """Detecta modelos de reasoning."""
        _lower = name.lower()
        return any(tag in _lower for tag in ("gpt-5", "o1", "o3", "o4"))

    if _is_reasoning_model(comp["model_name"]):
        chat_model = ChatOpenAI(
            model=comp["model_name"],
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            model_kwargs={
                "max_completion_tokens": 8000,
                "reasoning_effort": "minimal",
            },
        )
    else:
        max_tokens = int(enhancement_cfg.get("max_tokens", 2000))
        chat_model = ChatOpenAI(
            model=comp["model_name"],
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )

    agent = create_agent(
        model=chat_model,
        tools=[],
        middleware=[],
        response_format=EnhancedTextResponse,
    )

    graph = create_enhancement_graph(db_session, agent, checkpointer=None)
    return graph


async def enhance_with_model(
    graph,
    field_name: str,
    text: str,
    campaign_name: str,
) -> dict:
    initial_state: EnhancementGraphState = {
        "field_name": field_name,
        "text": text,
        "field_info": None,
        "enhanced_text": None,
        "explanation": None,
        "enhancement_history": None,
        "previous_fields_summary": None,
        "campaign_name": campaign_name,
    }
    result = await graph.ainvoke(initial_state)
    return {
        "enhanced_text": result.get("enhanced_text", text),
        "explanation": result.get("explanation", ""),
    }


# ═══════════════════════════════════════════════════════════════════════
# Judge: chama GPT-5.2 como avaliador
# ═══════════════════════════════════════════════════════════════════════

def judge_texts(
    client: OpenAI,
    model: str,
    field_name: str,
    campaign_name: str,
    original_text: str,
    text_maritaca: str,
    text_openai: str,
) -> dict:
    # posição random
    a_is_maritaca = random.choice([True, False])
    if a_is_maritaca:
        text_a, text_b = text_maritaca, text_openai
    else:
        text_a, text_b = text_openai, text_maritaca

    prompt = build_judge_prompt(
        field_name, campaign_name, original_text, text_a, text_b
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_completion_tokens=500,
        )
        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        verdict = json.loads(raw)

        pos_winner = verdict.get("winner", "TIE")
        if pos_winner == "TIE":
            actual_winner = "tie"
        elif pos_winner == "A":
            actual_winner = "maritaca" if a_is_maritaca else "openai"
        else:  
            actual_winner = "openai" if a_is_maritaca else "maritaca"

        return {
            "winner": actual_winner,
            "score_maritaca": verdict.get(
                "score_a" if a_is_maritaca else "score_b", 0
            ),
            "score_openai": verdict.get(
                "score_b" if a_is_maritaca else "score_a", 0
            ),
            "justification": verdict.get("justification", ""),
            "position_a": "maritaca" if a_is_maritaca else "openai",
        }
    except Exception as e:
        logger.error(f"Judge error: {e}")
        return {
            "winner": "error",
            "score_maritaca": 0,
            "score_openai": 0,
            "justification": f"Erro: {str(e)}",
            "position_a": "maritaca" if a_is_maritaca else "openai",
        }


# ═══════════════════════════════════════════════════════════════════════
# Métricas
# ═══════════════════════════════════════════════════════════════════════

def calculate_metrics(results: list[dict]) -> dict:
    total = len(results)
    valid = [r for r in results if r["winner"] != "error"]
    errors = total - len(valid)

    wins_maritaca = sum(1 for r in valid if r["winner"] == "maritaca")
    wins_openai = sum(1 for r in valid if r["winner"] == "openai")
    ties = sum(1 for r in valid if r["winner"] == "tie")

    avg_score_maritaca = (
        sum(r["score_maritaca"] for r in valid) / len(valid) if valid else 0
    )
    avg_score_openai = (
        sum(r["score_openai"] for r in valid) / len(valid) if valid else 0
    )

    times_maritaca = [r["time_maritaca_s"] for r in results if r.get("time_maritaca_s")]
    times_openai = [r["time_openai_s"] for r in results if r.get("time_openai_s")]
    avg_time_maritaca = round(sum(times_maritaca) / len(times_maritaca), 2) if times_maritaca else 0
    avg_time_openai = round(sum(times_openai) / len(times_openai), 2) if times_openai else 0
    p50_maritaca = round(sorted(times_maritaca)[len(times_maritaca) // 2], 2) if times_maritaca else 0
    p50_openai = round(sorted(times_openai)[len(times_openai) // 2], 2) if times_openai else 0
    p95_idx_m = min(int(len(times_maritaca) * 0.95), len(times_maritaca) - 1) if times_maritaca else 0
    p95_idx_o = min(int(len(times_openai) * 0.95), len(times_openai) - 1) if times_openai else 0
    p95_maritaca = round(sorted(times_maritaca)[p95_idx_m], 2) if times_maritaca else 0
    p95_openai = round(sorted(times_openai)[p95_idx_o], 2) if times_openai else 0

    fields = set(r["field_name"] for r in results)
    per_field = {}
    for field in sorted(fields):
        fr = [r for r in valid if r["field_name"] == field]
        if not fr:
            continue
        n = len(fr)
        per_field[field] = {
            "total": n,
            "maritaca_wins": sum(1 for r in fr if r["winner"] == "maritaca"),
            "openai_wins": sum(1 for r in fr if r["winner"] == "openai"),
            "ties": sum(1 for r in fr if r["winner"] == "tie"),
            "win_rate_maritaca": round(
                sum(1 for r in fr if r["winner"] == "maritaca") / n * 100, 1
            ),
            "win_rate_openai": round(
                sum(1 for r in fr if r["winner"] == "openai") / n * 100, 1
            ),
            "avg_score_maritaca": round(
                sum(r["score_maritaca"] for r in fr) / n, 2
            ),
            "avg_score_openai": round(
                sum(r["score_openai"] for r in fr) / n, 2
            ),
        }

    return {
        "total": total,
        "valid": len(valid),
        "errors": errors,
        "maritaca_wins": wins_maritaca,
        "openai_wins": wins_openai,
        "ties": ties,
        "win_rate_maritaca": round(
            wins_maritaca / len(valid) * 100, 1
        ) if valid else 0,
        "win_rate_openai": round(
            wins_openai / len(valid) * 100, 1
        ) if valid else 0,
        "tie_rate": round(ties / len(valid) * 100, 1) if valid else 0,
        "avg_score_maritaca": round(avg_score_maritaca, 2),
        "avg_score_openai": round(avg_score_openai, 2),
        "score_diff": round(avg_score_maritaca - avg_score_openai, 2),
        "latency": {
            "avg_maritaca_s": avg_time_maritaca,
            "avg_openai_s": avg_time_openai,
            "p50_maritaca_s": p50_maritaca,
            "p50_openai_s": p50_openai,
            "p95_maritaca_s": p95_maritaca,
            "p95_openai_s": p95_openai,
        },
        "per_field": per_field,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

async def run_evaluation(args):
    """Run the full evaluation pipeline: maritaca vs openai."""
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    judge_model = args.judge_model
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    maritaca_api_key = os.getenv("MARITACA_API_KEY", "")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY é obrigatória (juiz + competidor gpt-5-nano)")
        sys.exit(1)
    if not maritaca_api_key:
        logger.error("MARITACA_API_KEY é obrigatória (competidor sabiazinho-4)")
        sys.exit(1)

    judge_client = OpenAI(api_key=openai_api_key)

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.error("DATABASE_URL é obrigatória para acessar guidelines do DB")
        sys.exit(1)

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    logger.info("Construindo graphs para os dois modelos competidores...")
    graph_maritaca = build_enhancer_graph("maritaca", db)
    graph_openai = build_enhancer_graph("openai", db)
    logger.info(
        f"  ✓ {COMPETITORS['maritaca']['label']} e "
        f"{COMPETITORS['openai']['label']} prontos"
    )

    logger.info(f"Carregando dataset de {dataset_path}")
    rows = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)

    logger.info(f"Dataset: {len(rows)} linhas")
    logger.info(f"Juiz: {judge_model}")
    logger.info("=" * 60)

    results = []
    start_time = time.time()

    for i, row in enumerate(rows):
        campaign_name = row["campaign_name"]
        field_name = row["field_name"]
        original_text = row["original_text"]

        logger.info(
            f"[{i+1}/{len(rows)}] {campaign_name} — {field_name}"
        )

        t0_maritaca = time.perf_counter()
        try:
            res_maritaca = await enhance_with_model(
                graph_maritaca, field_name, original_text, campaign_name
            )
            text_maritaca = res_maritaca["enhanced_text"]
            expl_maritaca = res_maritaca["explanation"]
            status_maritaca = "success"
        except Exception as e:
            logger.error(f"  Maritaca falhou: {e}")
            text_maritaca = original_text
            expl_maritaca = f"Erro: {str(e)}"
            status_maritaca = "error"
        time_maritaca = round(time.perf_counter() - t0_maritaca, 2)

        t0_openai = time.perf_counter()
        try:
            res_openai = await enhance_with_model(
                graph_openai, field_name, original_text, campaign_name
            )
            text_openai = res_openai["enhanced_text"]
            expl_openai = res_openai["explanation"]
            status_openai = "success"
        except Exception as e:
            logger.error(f"  OpenAI falhou: {e}")
            text_openai = original_text
            expl_openai = f"Erro: {str(e)}"
            status_openai = "error"
        time_openai = round(time.perf_counter() - t0_openai, 2)


        maritaca_ok = status_maritaca == "success" and text_maritaca != original_text
        openai_ok = status_openai == "success" and text_openai != original_text

        if maritaca_ok and openai_ok:
            verdict = judge_texts(
                client=judge_client,
                model=judge_model,
                field_name=field_name,
                campaign_name=campaign_name,
                original_text=original_text,
                text_maritaca=text_maritaca,
                text_openai=text_openai,
            )
        elif maritaca_ok and not openai_ok:
            reason = (
                "OpenAI falhou (exceção)" if status_openai == "error"
                else "OpenAI retornou texto sem alteração (timeout/fallback)"
            )
            verdict = {
                "winner": "maritaca",
                "score_maritaca": 0,
                "score_openai": 0,
                "justification": f"{reason}; Maritaca vence por W.O.",
                "position_a": "N/A",
            }
        elif openai_ok and not maritaca_ok:
            reason = (
                "Maritaca falhou (exceção)" if status_maritaca == "error"
                else "Maritaca retornou texto sem alteração (timeout/fallback)"
            )
            verdict = {
                "winner": "openai",
                "score_maritaca": 0,
                "score_openai": 0,
                "justification": f"{reason}; OpenAI vence por W.O.",
                "position_a": "N/A",
            }
        else:
            verdict = {
                "winner": "error",
                "score_maritaca": 0,
                "score_openai": 0,
                "justification": "Ambos os modelos falharam ou retornaram texto inalterado",
                "position_a": "N/A",
            }

        result = {
            "idx": i + 1,
            "campaign_name": campaign_name,
            "field_name": field_name,
            "original_text": original_text,
            "text_maritaca": text_maritaca,
            "text_openai": text_openai,
            "explanation_maritaca": expl_maritaca,
            "explanation_openai": expl_openai,
            "status_maritaca": status_maritaca,
            "status_openai": status_openai,
            "time_maritaca_s": time_maritaca,
            "time_openai_s": time_openai,
            **verdict,
        }
        results.append(result)

        winner_label = {
            "maritaca": "sabiazinho-4",
            "openai": "gpt-5-nano",
            "tie": "EMPATE",
            "error": "ERRO",
        }.get(verdict["winner"], verdict["winner"])

        logger.info(
            f"  → Vencedor: {winner_label} "
            f"(sabiazinho-4={verdict['score_maritaca']}, "
            f"gpt-5-nano={verdict['score_openai']}) "
            f"| tempo: maritaca={time_maritaca}s, openai={time_openai}s"
        )

    elapsed = time.time() - start_time
    db.close()

    metrics = calculate_metrics(results)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "judge_model": judge_model,
        "competitors": {
            "a": COMPETITORS["maritaca"]["label"],
            "b": COMPETITORS["openai"]["label"],
        },
        "elapsed_seconds": round(elapsed, 1),
        "metrics": metrics,
        "results": results,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"enhancement_eval_{ts}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\nResultados salvos em {output_file}")

    # ── Print summary ──────────────────────────────────────────────
    W = 62
    print()
    print("=" * W)
    print("  AVALIAÇÃO — Briefing Enhancer: sabiazinho-4 vs gpt-5-nano")
    print("=" * W)
    print(f"  Dataset:       {dataset_path}")
    print(f"  Total:         {metrics['total']} linhas")
    print(f"  Juiz:          {judge_model}")
    print(f"  Duração:       {elapsed:.0f}s")
    print("-" * W)
    print(
        f"  sabiazinho-4 vence: "
        f"{metrics['maritaca_wins']}/{metrics['valid']} "
        f"({metrics['win_rate_maritaca']}%)"
    )
    print(
        f"  gpt-5-nano vence:   "
        f"{metrics['openai_wins']}/{metrics['valid']} "
        f"({metrics['win_rate_openai']}%)"
    )
    print(
        f"  Empates:            "
        f"{metrics['ties']}/{metrics['valid']} "
        f"({metrics['tie_rate']}%)"
    )
    print(f"  Erros:              {metrics['errors']}")
    print("-" * W)
    print(f"  Score médio sabiazinho-4:  {metrics['avg_score_maritaca']}")
    print(f"  Score médio gpt-5-nano:    {metrics['avg_score_openai']}")
    diff = metrics["score_diff"]
    diff_label = (
        f"+{diff} para sabiazinho-4" if diff > 0
        else f"+{abs(diff)} para gpt-5-nano" if diff < 0
        else "Iguais"
    )
    print(f"  Diferença:                 {diff_label}")
    print("-" * W)
    lat = metrics["latency"]
    print("  LATÊNCIA (segundos):")
    print(f"    sabiazinho-4:  avg={lat['avg_maritaca_s']}  p50={lat['p50_maritaca_s']}  p95={lat['p95_maritaca_s']}")
    print(f"    gpt-5-nano:    avg={lat['avg_openai_s']}  p50={lat['p50_openai_s']}  p95={lat['p95_openai_s']}")
    speed = (
        f"sabiazinho-4 é {round(lat['avg_openai_s'] / lat['avg_maritaca_s'], 1)}x mais rápido"
        if lat["avg_maritaca_s"] > 0 and lat["avg_openai_s"] > lat["avg_maritaca_s"]
        else f"gpt-5-nano é {round(lat['avg_maritaca_s'] / lat['avg_openai_s'], 1)}x mais rápido"
        if lat["avg_openai_s"] > 0 and lat["avg_maritaca_s"] > lat["avg_openai_s"]
        else "Latências semelhantes"
    )
    print(f"    → {speed}")
    print("-" * W)
    print("  POR CAMPO:")
    for field, fm in metrics["per_field"].items():
        display = FIELD_GUIDELINES.get(field, {}).get("display_name", field)
        print(f"    {display}:")
        print(
            f"      sabiazinho-4: {fm['maritaca_wins']}/{fm['total']} "
            f"({fm['win_rate_maritaca']}%)  score={fm['avg_score_maritaca']}"
        )
        print(
            f"      gpt-5-nano:   {fm['openai_wins']}/{fm['total']} "
            f"({fm['win_rate_openai']}%)  score={fm['avg_score_openai']}"
        )
        print(
            f"      empates:      {fm['ties']}/{fm['total']}"
        )
    print("=" * W)


def main():
    parser = argparse.ArgumentParser(
        description="Avaliação do Briefing Enhancer: sabiazinho-4 vs gpt-5-nano (LLM-as-a-Judge)"
    )
    parser.add_argument(
        "--dataset",
        default="evals/eval_dataset.csv",
        help="Caminho do dataset CSV (default: evals/eval_dataset.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="evals/results",
        help="Diretório de saída (default: evals/results)",
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-5.2",
        help="Modelo OpenAI para o juiz (default: gpt-5.2)",
    )
    args = parser.parse_args()
    asyncio.run(run_evaluation(args))


if __name__ == "__main__":
    main()
