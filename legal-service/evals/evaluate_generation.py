import csv
import os
import sys
from pathlib import Path
from typing import List, Dict
import logging
from collections import defaultdict
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from app.agent.graph import LegalAgent
from app.core.config import settings
from app.core.models_config import load_models_config
from langchain_openai import ChatOpenAI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("weaviate").setLevel(logging.WARNING)

def format_expected_decision(expected: str) -> str:
    """
    Formata expected_decision do CSV para decision (APROVADO ou REPROVADO).
    
    O CSV tem valores como 'APROVADO', 'BLOCKER', 'WARNING'.
    - 'APROVADO' -> 'APROVADO'
    - 'BLOCKER' ou 'WARNING' -> 'REPROVADO'
    """
    expected_upper = expected.strip().upper()
    if expected_upper == "APROVADO":
        return "APROVADO"
    return "REPROVADO"


def calculate_metrics(results: List[Dict]) -> Dict:
    """
    Calcula métricas de classificação: accuracy, precision, recall, F1 (apenas decision).
    """
    true_positives = defaultdict(int)
    false_positives = defaultdict(int)
    false_negatives = defaultdict(int)
    correct_decision = 0
    total = 0

    for result in results:
        if "error" in result:
            continue
        total += 1
        expected_decision = result["expected_decision"]
        predicted_decision = result["predicted_decision"]
        if predicted_decision == expected_decision:
            correct_decision += 1
            true_positives[predicted_decision] += 1
        else:
            false_positives[predicted_decision] += 1
            false_negatives[expected_decision] += 1

    accuracy_decision = correct_decision / total if total > 0 else 0.0
    metrics_by_class = {}
    all_classes = set(
        [r.get("expected_decision") for r in results if "error" not in r]
        + [r.get("predicted_decision") for r in results if "error" not in r]
    )
    for cls in all_classes:
        tp = true_positives.get(cls, 0)
        fp = false_positives.get(cls, 0)
        fn = false_negatives.get(cls, 0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics_by_class[cls] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn,
        }
    return {
        "total_examples": total,
        "accuracy_decision": accuracy_decision,
        "metrics_by_class": metrics_by_class,
    }


def build_confusion_matrix(results: List[Dict], field: str = "decision") -> Dict[str, Dict[str, int]]:
    """
    Constrói matriz de confusão para decision.
    """
    matrix = defaultdict(lambda: defaultdict(int))
    
    for result in results:
        if "error" in result:
            continue
        
        expected_key = f"expected_{field}"
        predicted_key = f"predicted_{field}"
        
        expected = result.get(expected_key, "UNKNOWN")
        predicted = result.get(predicted_key, "UNKNOWN")
        
        matrix[expected][predicted] += 1
    
    return dict(matrix)


def evaluate_generation_dataset(
    dataset_path: str,
    weaviate_url: str = None,
    output_path: str = None,
    disable_cache: bool = True,
    weaviate_url_explicit: bool = False,
    forced_model: str = None,
    forced_model_base_url: str = None,
    alpha_override: float = None,
    collection_override: str = None,
    rerank_override: bool = None,
) -> Dict:
    """
    Avalia a geração (decision APROVADO/REPROVADO) usando o dataset CSV.
    
    Args:
        dataset_path: Caminho para o CSV com o dataset
        weaviate_url: URL do Weaviate (default: settings.WEAVIATE_URL)
        output_path: Caminho opcional para salvar resultados detalhados
        disable_cache: Se True, desabilita cache para avaliação justa
        forced_model: Força uso de um modelo LLM específico
        forced_model_base_url: Base URL do modelo (opcional)
        alpha_override: Sobrescreve alpha do hybrid search (0.0=BM25, 0.5=hybrid, 1.0=semantic)
        collection_override: Sobrescreve nome da collection no Weaviate
        rerank_override: Sobrescreve rerank_enabled (True/False, None=usa config)
    
    Returns:
        Dicionário com métricas agregadas
    """
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset não encontrado: {dataset_path}")
    
    weaviate_url = weaviate_url or os.getenv("WEAVIATE_URL", settings.WEAVIATE_URL)

    if not weaviate_url_explicit and weaviate_url.startswith("http://weaviate:"):
        if not os.path.exists("/.dockerenv"):
            weaviate_url = weaviate_url.replace("weaviate", "localhost")
            logger.info("Detectado ambiente local, ajustando Weaviate URL para localhost")
    
    config = load_models_config()
    llm_config = config.get("models", {}).get("llm", {})
    embeddings_config = config.get("models", {}).get("embeddings", {})
    retrieval_config = config.get("models", {}).get("retrieval", {})
    
    # Reranking: usa override se fornecido, senão usa config
    if rerank_override is not None:
        rerank_enabled = rerank_override
        logger.info(f"[EXPERIMENT] Rerank override: {rerank_enabled}")
    else:
        rerank_enabled = retrieval_config.get("rerank_enabled", False)
    
    # Inicializa agente sem cache
    cache_enabled = not disable_cache
    
    # Preparar kwargs para LegalAgent com overrides de experimento
    agent_kwargs = {
        "weaviate_url": weaviate_url,
        "rerank_override": rerank_override,
        "cache_enabled": cache_enabled,
    }
    
    # Override de alpha para hybrid search
    if alpha_override is not None:
        agent_kwargs["alpha_override"] = alpha_override
    
    # Override de collection name
    if collection_override:
        agent_kwargs["collection_override"] = collection_override
    
    agent = LegalAgent(**agent_kwargs)
    
    if forced_model:
        if forced_model_base_url:
            base_url = forced_model_base_url
            if "maritaca" in base_url.lower():
                provider = "maritaca"
            else:
                provider = "openai"
        elif "sabiazinho" in forced_model.lower():
            base_url = os.getenv("MARITACA_BASE_URL", llm_config.get("base_url", "https://chat.maritaca.ai/api"))
            provider = "maritaca"
        else:
            base_url = "https://api.openai.com/v1"
            provider = "openai"
        
        if provider == "maritaca":
            api_key = (os.getenv("MARITACA_API_KEY") or "").strip()
            if not api_key:
                raise ValueError(f"MARITACA_API_KEY required for model {forced_model}")
        else:
            api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
            if not api_key:
                raise ValueError(f"OPENAI_API_KEY required for model {forced_model}")
        
        llm_temperature = float(llm_config.get("temperature", 0.0))
        max_tokens = int(llm_config.get("max_tokens", 15000))
        timeout = int(llm_config.get("timeout", 20))
        max_retries = int(llm_config.get("max_retries", 2))
        
        forced_llm = ChatOpenAI(
            model=forced_model,
            api_key=api_key,
            base_url=base_url,
            temperature=llm_temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        agent.llm = forced_llm
        agent.model_name = forced_model
        agent.provider = provider
        
        logger.info(f"Modelo forçado: {forced_model} (provider: {provider}, base_url: {base_url})")
    
    logger.info("="*80)
    logger.info("CONFIGURAÇÃO DA AVALIAÇÃO DE GERAÇÃO")
    logger.info("="*80)
    if forced_model:
        logger.info(f"Modelo LLM: {forced_model} (FORÇADO)")
    else:
        logger.info(f"Modelo LLM: {llm_config.get('name', 'N/A')} (fallback: {llm_config.get('fallback_model_name', 'N/A')})")
    logger.info(f"Modelo embeddings: {embeddings_config.get('model', 'N/A')}")
    logger.info(f"Weaviate URL: {weaviate_url}")
    if alpha_override is not None:
        alpha_desc = "BM25 only" if alpha_override == 0.0 else ("Semantic only" if alpha_override == 1.0 else f"Hybrid ({alpha_override})")
        logger.info(f"Retrieval Alpha: {alpha_override} ({alpha_desc}) [OVERRIDE]")
    else:
        logger.info(f"Retrieval Alpha: {retrieval_config.get('alpha', 0.5)} (config)")
    if collection_override:
        logger.info(f"Collection: {collection_override} [OVERRIDE]")
    logger.info("="*80)
    
    logger.info(f"Agent inicializado (cache={'enabled' if cache_enabled else 'disabled'})")
    
    results = []
    try:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            for idx, row in enumerate(reader, start=1):
                channel = row.get("channel", "").strip()
                content = row.get("content", "").strip()
                expected_decision_raw = row.get("expected_decision", "").strip()
                
                if not content:
                    logger.warning(f"Linha {idx}: content vazio, pulando")
                    continue
                
                if not expected_decision_raw:
                    logger.warning(f"Linha {idx}: expected_decision vazio, pulando")
                    continue
                
                expected_decision = format_expected_decision(expected_decision_raw)
                
                logger.info(f"[{idx}] Processando: {content[:60]}...")
                logger.debug(f"  Expected: decision={expected_decision}")
                
                try:
                    # Chama agente completo (retrieval + geração)
                    result = agent.invoke(
                        task="VALIDATE_COMMUNICATION",
                        channel=channel if channel else None,
                        content=content,
                    )
                    
                    predicted_decision = result.get("decision", "UNKNOWN")
                    
                    result_row = {
                        "idx": idx,
                        "channel": channel,
                        "content": content[:100] + "..." if len(content) > 100 else content,
                        "expected_decision": expected_decision,
                        "predicted_decision": predicted_decision,
                        "predicted_summary": result.get("summary", "")[:100] + "..." if len(result.get("summary", "")) > 100 else result.get("summary", ""),
                        "predicted_requires_human_review": result.get("requires_human_review", False),
                        "correct_decision": predicted_decision == expected_decision,
                        "num_sources": len(result.get("sources", [])),
                        "rerank_enabled": rerank_enabled,
                    }
                    results.append(result_row)
                    
                    status = "✓" if result_row["correct_decision"] else "✗"
                    logger.info(
                        f"  {status} Predicted: {predicted_decision} | Expected: {expected_decision}"
                    )
                    
                except Exception as e:
                    logger.error(f"Erro ao processar linha {idx}: {e}", exc_info=True)
                    results.append({
                        "idx": idx,
                        "channel": channel,
                        "content": content[:100] + "..." if len(content) > 100 else content,
                        "error": str(e),
                        "expected_decision": expected_decision,
                    })
        
        # métricas
        metrics = calculate_metrics(results)
        confusion_matrix_decision = build_confusion_matrix(results, "decision")
        
        summary = {
            **metrics,
            "confusion_matrix_decision": confusion_matrix_decision,
            "results": results,
            "config": {
                "llm_model": getattr(agent, "model_name", None) or (forced_model if forced_model else llm_config.get("name", "N/A")),
                "llm_provider": getattr(agent, "provider", None) or "config",
                "embedding_model": embeddings_config.get("model", "N/A"),
                "cache_enabled": cache_enabled,
                "rerank_enabled": rerank_enabled,
                "alpha": alpha_override if alpha_override is not None else retrieval_config.get("alpha", 0.5),
                "collection": collection_override if collection_override else settings.WEAVIATE_CLASS_NAME,
            },
        }
        
        if output_path:
            output_path = Path(output_path)
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            logger.info(f"Resultados detalhados salvos em: {output_path}")
        
        return summary
    finally:
        agent.close()


def print_summary(summary: Dict):
    """Imprime resumo das métricas."""
    print("\n" + "="*80)
    print("RESUMO DA AVALIAÇÃO DE GERAÇÃO")
    print("="*80)
    print(f"\nConfiguração:")
    print(f"  LLM: {summary['config']['llm_model']} ({summary['config']['llm_provider']})")
    print(f"  Embeddings: {summary['config']['embedding_model']}")
    print(f"  Cache: {'enabled' if summary['config']['cache_enabled'] else 'disabled'}")
    print(f"  Reranking: {'enabled' if summary['config'].get('rerank_enabled', False) else 'disabled'}")
    
    # Mostrar alpha e collection se disponíveis
    alpha = summary['config'].get('alpha')
    if alpha is not None:
        alpha_desc = "BM25 only" if alpha == 0.0 else ("Semantic only" if alpha == 1.0 else f"Hybrid")
        print(f"  Retrieval: {alpha_desc} (alpha={alpha})")
    
    collection = summary['config'].get('collection')
    if collection:
        print(f"  Collection: {collection}")
    
    print(f"\nTotal de exemplos: {summary['total_examples']}")
    print(f"\nAccuracy (Decision): {summary['accuracy_decision']:.4f} ({summary['accuracy_decision']*100:.2f}%)")
    
    print(f"\nMétricas por Decision:")
    for cls, metrics_cls in sorted(summary['metrics_by_class'].items()):
        print(f"  {cls:12s} | Precision: {metrics_cls['precision']:.4f} | "
              f"Recall: {metrics_cls['recall']:.4f} | F1: {metrics_cls['f1']:.4f} | "
              f"Support: {metrics_cls['support']}")
    
    print(f"\nMatriz de confusão (Decision):")
    cm_decision = summary['confusion_matrix_decision']
    all_decisions = sorted(set(cm_decision.keys()) | set(d for row in cm_decision.values() for d in row.keys()))
    print(f"  {'':12s} | " + " | ".join(f"{d:12s}" for d in all_decisions))
    for expected in sorted(cm_decision.keys()):
        row = [str(cm_decision[expected].get(pred, 0)) for pred in all_decisions]
        print(f"  {expected:12s} | " + " | ".join(f"{r:12s}" for r in row))
    
    incorrect_results = [r for r in summary['results'] if "error" not in r and not r.get('correct_decision', False)]
    if incorrect_results:
        print(f"\nTop 5 casos incorretos:")
        for r in incorrect_results[:5]:
            print(f"  [{r['idx']}] Expected: {r['expected_decision']} | Predicted: {r['predicted_decision']}")
            print(f"      Content: {r['content'][:60]}...")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Avalia a qualidade da geração (decision APROVADO/REPROVADO) do legal-service"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="evals/eval_retrieval_dataset.csv",
        help="Caminho para o dataset CSV (default: evals/eval_retrieval_dataset.csv)"
    )
    parser.add_argument(
        "--weaviate-url",
        type=str,
        default=None,
        help="URL do Weaviate (default: WEAVIATE_URL do env ou settings)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Caminho opcional para salvar resultados JSON detalhados"
    )
    parser.add_argument(
        "--enable-cache",
        action="store_true",
        help="Habilita cache (por padrão está desabilitado para avaliação justa)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Força uso de um modelo específico. Se não especificado, usa a lógica padrão de fallback."
    )
    parser.add_argument(
        "--model-base-url",
        type=str,
        default=None,
        help="Base URL do modelo (opcional). Se não especificado, detecta automaticamente baseado no nome do modelo ou usa defaults."
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=None,
        help="Sobrescreve alpha do hybrid search (0.0=BM25 only, 0.5=hybrid, 1.0=semantic only)"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Sobrescreve nome da collection no Weaviate"
    )
    
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        if dataset_path.exists():
            dataset_path = dataset_path.resolve()
        else:
            dataset_path = (project_root / dataset_path).resolve()
    
    try:
        summary = evaluate_generation_dataset(
            dataset_path=str(dataset_path),
            weaviate_url=args.weaviate_url,
            output_path=args.output,
            disable_cache=not args.enable_cache,
            weaviate_url_explicit=(args.weaviate_url is not None),
            forced_model=args.model,
            forced_model_base_url=args.model_base_url,
            alpha_override=args.alpha,
            collection_override=args.collection,
        )
        
        print_summary(summary)
        
    except Exception as e:
        logger.error(f"Erro ao executar avaliação: {e}", exc_info=True)
        sys.exit(1)
