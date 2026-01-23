import csv
import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import logging
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from app.agent.retriever import HybridWeaviateRetriever
from app.core.config import settings
from app.core.models_config import load_models_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_ground_truth(ground_truth_str: str) -> Set[str]:
    """Parse ground truth string (arquivos separados por |) em conjunto."""
    if not ground_truth_str or not ground_truth_str.strip():
        return set()
    return {f.strip() for f in ground_truth_str.split("|") if f.strip()}


def extract_retrieved_files(retrieved_chunks: List[Dict]) -> Set[str]:
    """Extrai os nomes de arquivos únicos dos chunks retornados."""
    files = set()
    for chunk in retrieved_chunks:
        file_name = chunk.get("file_name") or chunk.get("source_file")
        if file_name:
            files.add(file_name)
    return files


def calculate_file_metrics(retrieved_files: Set[str], ground_truth_files: Set[str]) -> Tuple[float, float, float]:
    """
    Calcula precision, recall e F1 baseados em arquivos.
    
    Args:
        retrieved_files: Conjunto de arquivos retornados pelo retriever
        ground_truth_files: Conjunto de arquivos esperados (ground truth)
    
    Returns:
        Tuple (precision, recall, f1)
    """
    if not ground_truth_files:
        logger.warning("Ground truth vazio, não é possível calcular métricas")
        return 0.0, 0.0, 0.0
    
    intersection = retrieved_files & ground_truth_files
    
    # Precision: dos arquivos retornados, quantos estão no ground truth?
    precision = len(intersection) / len(retrieved_files) if retrieved_files else 0.0
    
    # Recall: dos arquivos esperados, quantos foram retornados?
    recall = len(intersection) / len(ground_truth_files)
    
    # F1: média harmônica de precision e recall
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return precision, recall, f1


def evaluate_retrieval_dataset(
    dataset_path: str,
    weaviate_url: str = None,
    output_path: str = None,
    weaviate_url_explicit: bool = False,
) -> Dict:
    """
    Avalia o retrieval usando o dataset CSV.
    
    Args:
        dataset_path: Caminho para o CSV com o dataset
        weaviate_url: URL do Weaviate (default: settings.WEAVIATE_URL)
        output_path: Caminho opcional para salvar resultados detalhados
    
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
    
    logger.info(f"Conectando ao Weaviate em {weaviate_url}")
    
    config = load_models_config()
    retrieval_config = config.get("models", {}).get("retrieval", {})
    limit = retrieval_config.get("limit", 10)
    alpha = retrieval_config.get("alpha", 0.7)
    rerank_enabled = retrieval_config.get("rerank_enabled", False)
    
    retriever = HybridWeaviateRetriever(weaviate_url=weaviate_url)
    
    results = []
    all_precisions = []
    all_recalls = []
    all_f1s = []
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        
        for idx, row in enumerate(reader, start=1):
            question = row.get("question", "").strip()
            ground_truth_str = row.get("ground_truth", "").strip()
            channel = row.get("channel", "").strip()
            content = row.get("content", "").strip()
            
            if not question:
                logger.warning(f"Linha {idx}: question vazio, pulando")
                continue
            
            if not ground_truth_str:
                logger.warning(f"Linha {idx}: ground_truth vazio, pulando")
                continue
            
            ground_truth_files = parse_ground_truth(ground_truth_str)
            
            logger.info(f"[{idx}] Processando: {question[:80]}...")
            logger.debug(f"  Ground truth: {ground_truth_files}")
            
            try:
                # retrieval
                retrieved_chunks = retriever.hybrid_search(
                    query=question,
                    limit=limit,
                    alpha=alpha,
                    channel=channel if channel else None,
                )
                
                retrieved_files = extract_retrieved_files(retrieved_chunks)
                
                # métricas
                precision, recall, f1 = calculate_file_metrics(retrieved_files, ground_truth_files)
                
                all_precisions.append(precision)
                all_recalls.append(recall)
                all_f1s.append(f1)
                
                result = {
                    "idx": idx,
                    "question": question,
                    "channel": channel,
                    "content": content[:100] + "..." if len(content) > 100 else content,
                    "ground_truth_files": sorted(ground_truth_files),
                    "retrieved_files": sorted(retrieved_files),
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "num_retrieved": len(retrieved_chunks),
                    "rerank_enabled": rerank_enabled,
                }
                results.append(result)
                
                logger.info(
                    f"  Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f} | "
                    f"Retrieved: {len(retrieved_files)}, Expected: {len(ground_truth_files)}"
                )
                
            except Exception as e:
                logger.error(f"Erro ao processar linha {idx}: {e}", exc_info=True)
                results.append({
                    "idx": idx,
                    "question": question,
                    "error": str(e),
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                })
    
    retriever.close()
    
    macro_precision = sum(all_precisions) / len(all_precisions) if all_precisions else 0.0
    macro_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0.0
    macro_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0.0
    
    summary = {
        "total_examples": len(results),
        "successful_examples": len([r for r in results if "error" not in r]),
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "rerank_enabled": rerank_enabled,
        "config": {
            "limit": base_limit,
            "alpha": alpha,
            "rerank_enabled": rerank_enabled,
        },
        "results": results,
    }
    
    if output_path:
        output_path = Path(output_path)
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"Resultados detalhados salvos em: {output_path}")
    
    return summary


def print_summary(summary: Dict):
    """Imprime resumo das métricas."""
    print("\n" + "="*80)
    print("RESUMO DA AVALIAÇÃO DE RETRIEVAL")
    print("="*80)
    print(f"\nConfiguração:")
    if "config" in summary:
        config = summary["config"]
        print(f"  Limit: {config.get('limit', 'N/A')}")
        print(f"  Alpha: {config.get('alpha', 'N/A')}")
        print(f"  Reranking: {'enabled' if config.get('rerank_enabled', False) else 'disabled'}")
    print(f"\nTotal de exemplos: {summary['total_examples']}")
    print(f"Exemplos processados com sucesso: {summary['successful_examples']}")
    print(f"\nMétricas agregadas (macro-average):")
    print(f"  Precision: {summary['macro_precision']:.4f}")
    print(f"  Recall:    {summary['macro_recall']:.4f}")
    print(f"  F1:        {summary['macro_f1']:.4f}")
    print("\n" + "="*80)
    
    successful_results = [r for r in summary['results'] if "error" not in r]
    if successful_results:
        sorted_by_f1 = sorted(successful_results, key=lambda x: x['f1'])
        
        print("\nTop 5 piores casos (menor F1):")
        for r in sorted_by_f1[:5]:
            print(f"  [{r['idx']}] F1={r['f1']:.3f} | P={r['precision']:.3f} R={r['recall']:.3f}")
            print(f"      Question: {r['question'][:60]}...")
            print(f"      Expected: {r['ground_truth_files']}")
            print(f"      Retrieved: {r['retrieved_files']}")
        
        print("\nTop 5 melhores casos (maior F1):")
        for r in sorted_by_f1[-5:][::-1]:
            print(f"  [{r['idx']}] F1={r['f1']:.3f} | P={r['precision']:.3f} R={r['recall']:.3f}")
            print(f"      Question: {r['question'][:60]}...")
            print(f"      Expected: {r['ground_truth_files']}")
            print(f"      Retrieved: {r['retrieved_files']}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Avalia a qualidade do retrieval do legal-service"
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
    
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        if dataset_path.exists():
            dataset_path = dataset_path.resolve()
        else:
            dataset_path = (project_root / dataset_path).resolve()
    
    try:
        summary = evaluate_retrieval_dataset(
            dataset_path=str(dataset_path),
            weaviate_url=args.weaviate_url,
            output_path=args.output,
            weaviate_url_explicit=(args.weaviate_url is not None),
        )
        
        print_summary(summary)
        
    except Exception as e:
        logger.error(f"Erro ao executar avaliação: {e}", exc_info=True)
        sys.exit(1)
