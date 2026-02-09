#!/usr/bin/env python3
"""
Executa experimentos de avaliação de geração do legal-service.

Uso:
    python evals/run_experiments.py                           # Executa todos os experimentos habilitados
    python evals/run_experiments.py --experiment baseline     # Executa apenas um experimento
    python evals/run_experiments.py --group round2            # Executa apenas experimentos do grupo
    python evals/run_experiments.py --list                    # Lista experimentos disponíveis
    python evals/run_experiments.py --report-all              # Relatório consolidado de todos os JSONs
    python evals/run_experiments.py --config custom.yaml      # Usa arquivo de config customizado
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from evals.evaluate_generation import evaluate_generation_dataset, print_summary

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silencia logs verbosos
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("weaviate").setLevel(logging.WARNING)


def load_experiments_config(config_path: str) -> Dict:
    """Carrega configuração de experimentos do YAML."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config


def list_experiments(config: Dict) -> None:
    """Lista todos os experimentos disponíveis."""
    experiments = config.get("experiments", {})
    
    # Agrupar por grupo
    by_group: Dict[str, list] = {}
    for exp_id, exp_config in experiments.items():
        group = exp_config.get("group", "default")
        by_group.setdefault(group, []).append((exp_id, exp_config))
    
    print("\n" + "="*80)
    print("EXPERIMENTOS DISPONÍVEIS")
    print("="*80)
    
    for group, exps in by_group.items():
        print(f"\n--- Grupo: {group} ({len(exps)} experimentos) ---")
        for exp_id, exp_config in exps:
            enabled = "+" if exp_config.get("enabled", True) else "-"
            name = exp_config.get("name", exp_id)
            retrieval = exp_config.get("retrieval_strategy", "hybrid")
            chunking = exp_config.get("chunking", "section")
            llm = exp_config.get("llm_model", "maritaca")
            rerank = "RR" if exp_config.get("rerank_enabled") else "NoRR"
            
            print(f"  [{enabled}] {exp_id:<30s} {chunking:<10s} {retrieval:<10s} {llm:<10s} {rerank}")
    
    total = sum(len(exps) for exps in by_group.values())
    enabled_total = sum(
        1 for exps in by_group.values()
        for _, ec in exps if ec.get("enabled", True)
    )
    print(f"\nTotal: {total} experimentos ({enabled_total} habilitados)")
    print(f"Grupos: {', '.join(by_group.keys())}")
    print("="*80 + "\n")


def resolve_experiment_params(exp_config: Dict, full_config: Dict) -> Dict:
    """
    Resolve parâmetros do experimento com base nas definições do YAML.
    
    Returns:
        Dicionário com parâmetros resolvidos para evaluate_generation_dataset
    """
    # Obter configurações de estratégias
    retrieval_strategies = full_config.get("retrieval_strategies", {})
    chunking_collections = full_config.get("chunking_collections", {})
    llm_models = full_config.get("llm_models", {})
    defaults = full_config.get("defaults", {})
    
    # Resolver retrieval strategy
    retrieval_key = exp_config.get("retrieval_strategy", "hybrid")
    retrieval_config = retrieval_strategies.get(retrieval_key, {})
    alpha = retrieval_config.get("alpha", 0.5)
    
    # Resolver chunking collection
    chunking_key = exp_config.get("chunking", "section")
    chunking_config = chunking_collections.get(chunking_key, {})
    collection_name = chunking_config.get("collection_name", "LegalDocuments")
    
    # Resolver LLM model
    llm_key = exp_config.get("llm_model", "maritaca")
    llm_config = llm_models.get(llm_key, {})
    model_name = llm_config.get("model_name")
    model_base_url = llm_config.get("base_url")
    
    # Resolver reranking (pode ser sobrescrito por experimento)
    rerank_enabled = exp_config.get("rerank_enabled")  # None = usa config padrão
    
    return {
        "alpha": alpha,
        "collection_name": collection_name,
        "model_name": model_name,
        "model_base_url": model_base_url,
        "rerank_enabled": rerank_enabled,
        "dataset": defaults.get("dataset", "evals/eval_retrieval_dataset.csv"),
        "weaviate_url": defaults.get("weaviate_url"),
        "disable_cache": defaults.get("disable_cache", True),
        "output_dir": defaults.get("output_dir", "evals/results"),
    }


def run_single_experiment(
    exp_id: str,
    exp_config: Dict,
    full_config: Dict,
    output_dir: Path,
) -> Dict:
    """
    Executa um único experimento e retorna os resultados.
    """
    logger.info("="*80)
    logger.info(f"INICIANDO EXPERIMENTO: {exp_id}")
    logger.info(f"Nome: {exp_config.get('name', exp_id)}")
    logger.info(f"Descrição: {exp_config.get('description', '')}")
    logger.info("="*80)
    
    # Resolver parâmetros
    params = resolve_experiment_params(exp_config, full_config)
    
    rerank_status = "habilitado" if params.get('rerank_enabled') else "desabilitado"
    if params.get('rerank_enabled') is None:
        rerank_status = "padrão (config)"
    
    logger.info(f"Parâmetros resolvidos:")
    logger.info(f"  Alpha: {params['alpha']}")
    logger.info(f"  Collection: {params['collection_name']}")
    logger.info(f"  LLM: {params['model_name']}")
    logger.info(f"  Reranking: {rerank_status}")
    
    # Preparar caminho do dataset
    dataset_path = Path(params["dataset"])
    if not dataset_path.is_absolute():
        dataset_path = (project_root / dataset_path).resolve()
    
    # Preparar caminho de output (usar caminho absoluto)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = (output_dir / f"{exp_id}_{timestamp}.json").resolve()
    
    logger.info(f"Arquivo de output: {output_file}")
    
    # Executar avaliação
    try:
        summary = evaluate_generation_dataset(
            dataset_path=str(dataset_path),
            weaviate_url=params.get("weaviate_url"),
            output_path=str(output_file),
            disable_cache=params.get("disable_cache", True),
            forced_model=params.get("model_name"),
            forced_model_base_url=params.get("model_base_url"),
            # Parâmetros de experimento
            alpha_override=params.get("alpha"),
            collection_override=params.get("collection_name"),
            rerank_override=params.get("rerank_enabled"),
        )
        
        # Adicionar metadata do experimento
        summary["experiment"] = {
            "id": exp_id,
            "name": exp_config.get("name", exp_id),
            "description": exp_config.get("description", ""),
            "retrieval_strategy": exp_config.get("retrieval_strategy", "hybrid"),
            "chunking": exp_config.get("chunking", "section"),
            "llm_model": exp_config.get("llm_model", "maritaca"),
            "rerank_enabled": params.get("rerank_enabled"),
            "alpha": params.get("alpha"),
            "collection": params.get("collection_name"),
            "timestamp": timestamp,
        }
        
        # Salvar resultado atualizado
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Resultados salvos em: {output_file}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Erro ao executar experimento {exp_id}: {e}", exc_info=True)
        return {
            "experiment": {"id": exp_id, "name": exp_config.get("name", exp_id)},
            "error": str(e),
        }


def generate_comparison_report(
    results: List[Dict],
    output_dir: Path,
    report_config: Dict,
) -> None:
    """
    Gera relatório comparativo de todos os experimentos.
    """
    if not results:
        logger.warning("Nenhum resultado para gerar relatório comparativo")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Preparar dados para o relatório
    comparison_data = []
    for result in results:
        if "error" in result:
            continue
        
        exp = result.get("experiment", {})
        metrics = result.get("metrics_by_class", {})
        
        row = {
            "experiment_id": exp.get("id", "unknown"),
            "experiment_name": exp.get("name", "unknown"),
            "retrieval_strategy": exp.get("retrieval_strategy", ""),
            "alpha": exp.get("alpha", ""),
            "chunking": exp.get("chunking", ""),
            "collection": exp.get("collection", ""),
            "llm_model": exp.get("llm_model", ""),
            "rerank_enabled": exp.get("rerank_enabled"),
            "accuracy": result.get("accuracy_decision", 0),
            "total_examples": result.get("total_examples", 0),
        }
        
        # Adicionar métricas por classe
        for cls, cls_metrics in metrics.items():
            row[f"precision_{cls}"] = cls_metrics.get("precision", 0)
            row[f"recall_{cls}"] = cls_metrics.get("recall", 0)
            row[f"f1_{cls}"] = cls_metrics.get("f1", 0)
        
        # Latência
        latency = result.get("latency", {})
        row["avg_latency_s"] = latency.get("avg_s", 0)
        row["p50_latency_s"] = latency.get("p50_s", 0)
        row["p95_latency_s"] = latency.get("p95_s", 0)
        
        comparison_data.append(row)
    
    # Ordenar por recall de REPROVADO (métrica crítica: não deixar passar violações)
    # Desempate: F1 REPROVADO → Accuracy → menor latência
    comparison_data.sort(
        key=lambda x: (
            x.get("recall_REPROVADO", 0),
            x.get("f1_REPROVADO", 0),
            x.get("accuracy", 0),
            -x.get("avg_latency_s", 999),  # menor latência é melhor
        ),
        reverse=True,
    )
    
    # Salvar em JSON
    if "json" in report_config.get("formats", ["json"]):
        json_path = output_dir / f"comparison_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "generated_at": timestamp,
                "experiments": comparison_data,
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"Relatório JSON salvo em: {json_path}")
    
    # Salvar em CSV
    if "csv" in report_config.get("formats", []):
        csv_path = output_dir / f"comparison_{timestamp}.csv"
        if comparison_data:
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=comparison_data[0].keys())
                writer.writeheader()
                writer.writerows(comparison_data)
            logger.info(f"Relatório CSV salvo em: {csv_path}")
    
    # Imprimir resumo comparativo
    print("\n" + "="*140)
    print("RELATÓRIO COMPARATIVO DE EXPERIMENTOS")
    print("="*140)
    
    # Cabeçalho: recall REPROVADO como métrica principal (custo de aprovar indevidamente é alto)
    header = (
        f"{'#':<3} "
        f"{'Experimento':<35} "
        f"{'Chunking':<10} "
        f"{'Retrieval':<10} "
        f"{'Rerank':<8} "
        f"{'LLM':<12} "
        f"{'Recall REP':<12} "
        f"{'F1 REP':<10} "
        f"{'Accuracy':<10} "
        f"{'Latência':<10}"
    )
    print(f"\n{header}")
    print("-"*140)
    
    for idx, row in enumerate(comparison_data, 1):
        rank = " 1." if idx == 1 else f"{idx:>2}."
        
        rerank = row.get('rerank_enabled')
        rerank_str = "Sim" if rerank else ("Não" if rerank is False else "Config")
        
        recall_rep = row.get('recall_REPROVADO', 0)
        f1_rep = row.get('f1_REPROVADO', 0)
        avg_lat = row.get('avg_latency_s', 0)
        
        print(
            f"{rank:<3} "
            f"{row['experiment_name']:<35} "
            f"{row['chunking']:<10} "
            f"{row['retrieval_strategy']:<10} "
            f"{rerank_str:<8} "
            f"{row['llm_model']:<12} "
            f"{recall_rep*100:>6.2f}%     "
            f"{f1_rep*100:>6.2f}%   "
            f"{row['accuracy']*100:>6.2f}%   "
            f"{avg_lat:>5.1f}s"
        )
    
    print("="*140)
    print("  Ordenado por: Recall REPROVADO (métrica crítica — custo de aprovar indevidamente é alto)")
    
    # Destacar melhor experimento
    if comparison_data:
        best = comparison_data[0]
        rerank_best = best.get('rerank_enabled')
        rerank_str = "Sim" if rerank_best else ("Não" if rerank_best is False else "Config")
        
        print(f"\n{'='*60}")
        print(f"CONFIGURACAO VENCEDORA")
        print(f"{'='*60}")
        print(f"   Experimento:   {best['experiment_name']}")
        print(f"   Recall REP:    {best.get('recall_REPROVADO', 0)*100:.2f}%")
        print(f"   F1 REP:        {best.get('f1_REPROVADO', 0)*100:.2f}%")
        print(f"   Accuracy:      {best['accuracy']*100:.2f}%")
        print(f"   Latência avg:  {best.get('avg_latency_s', 0):.1f}s")
        print(f"   Chunking:      {best['chunking']}")
        print(f"   Retrieval:     {best['retrieval_strategy']} (alpha={best['alpha']})")
        print(f"   Reranking:     {rerank_str}")
        print(f"   LLM:           {best['llm_model']}")
        print(f"   Collection:    {best.get('collection', 'N/A')}")
        print(f"{'='*60}")
    
    # Informar sobre arquivos salvos (caminho amigável)
    display_path = str(output_dir).replace("/app/", "legal-service/")
    print(f"\nArquivos salvos em: {display_path}")
    print("")


def run_experiments(
    config: Dict,
    experiment_filter: Optional[str] = None,
    group_filter: Optional[str] = None,
) -> List[Dict]:
    """
    Executa experimentos conforme configuração.
    
    Args:
        config: Configuração carregada do YAML
        experiment_filter: Se especificado, executa apenas este experimento
        group_filter: Se especificado, executa apenas experimentos deste grupo
    
    Returns:
        Lista de resultados dos experimentos
    """
    experiments = config.get("experiments", {})
    defaults = config.get("defaults", {})
    
    # Criar diretório de output - garante caminho absoluto
    # O diretório de resultados fica sempre em: <script_dir>/results
    evals_dir = Path(__file__).parent.resolve()
    output_dir = evals_dir / "results"
    
    # Cria diretório se não existir
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Diretorio de resultados: {output_dir}")
    
    results = []
    
    # Filtrar experimentos
    if experiment_filter:
        if experiment_filter not in experiments:
            raise ValueError(f"Experimento não encontrado: {experiment_filter}")
        experiments_to_run = {experiment_filter: experiments[experiment_filter]}
    elif group_filter:
        experiments_to_run = {
            exp_id: exp_config
            for exp_id, exp_config in experiments.items()
            if exp_config.get("enabled", True)
            and exp_config.get("group", "default") == group_filter
        }
        if not experiments_to_run:
            raise ValueError(f"Nenhum experimento habilitado no grupo: {group_filter}")
        logger.info(f"Filtrando por grupo: {group_filter}")
    else:
        # Apenas experimentos habilitados
        experiments_to_run = {
            exp_id: exp_config
            for exp_id, exp_config in experiments.items()
            if exp_config.get("enabled", True)
        }
    
    total = len(experiments_to_run)
    logger.info(f"Executando {total} experimento(s)")
    
    for idx, (exp_id, exp_config) in enumerate(experiments_to_run.items(), start=1):
        logger.info(f"\n[{idx}/{total}] Experimento: {exp_id}")
        
        result = run_single_experiment(
            exp_id=exp_id,
            exp_config=exp_config,
            full_config=config,
            output_dir=output_dir,
        )
        
        # Imprimir resumo do experimento
        if "error" not in result:
            print_summary(result)
        
        results.append(result)
    
    # Gerar relatório comparativo se configurado
    report_config = config.get("report", {})
    if report_config.get("generate_comparison", True) and len(results) > 1:
        generate_comparison_report(results, output_dir, report_config)
    
    return results


def report_all_from_disk(config: Dict) -> None:
    """
    Gera relatório consolidado lendo o JSON mais recente de cada experiment_id
    existente no diretório de resultados.  Não executa nenhum experimento.
    """
    evals_dir = Path(__file__).parent.resolve()
    output_dir = evals_dir / "results"

    if not output_dir.exists():
        print("Nenhum resultado encontrado.")
        return

    # Mapear experiment_id → JSON mais recente
    # Nome dos arquivos: {experiment_id}_{timestamp}.json
    latest: Dict[str, Path] = {}
    for json_file in sorted(output_dir.glob("*.json")):
        # Ignorar comparison_*.json
        if json_file.name.startswith("comparison"):
            continue
        # Extrair experiment_id: tudo antes do último _YYYYMMDD_HHMMSS.json
        parts = json_file.stem.rsplit("_", 2)
        if len(parts) >= 3:
            exp_id = "_".join(parts[:-2])
        else:
            exp_id = json_file.stem
        # Como os arquivos estão ordenados, o último sobrescreve (mais recente)
        latest[exp_id] = json_file

    if not latest:
        print("Nenhum resultado de experimento encontrado no diretório de resultados.")
        return

    # Usar nomes do YAML como fonte de verdade (corrige JSONs antigos com nomes diferentes)
    experiments_cfg = config.get("experiments", {})

    print(f"\nCarregando resultados de {len(latest)} experimentos do disco...")
    results = []
    for exp_id, json_path in sorted(latest.items()):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Garantir que tem experiment.id preenchido
            if "experiment" not in data:
                data["experiment"] = {"id": exp_id, "name": exp_id}
            elif "id" not in data["experiment"]:
                data["experiment"]["id"] = exp_id
            # Normalizar nome a partir do YAML (corrige nomes legados)
            if exp_id in experiments_cfg:
                data["experiment"]["name"] = experiments_cfg[exp_id].get("name", data["experiment"].get("name", exp_id))
            results.append(data)
            logger.info(f"  [OK] {exp_id} ({json_path.name})")
        except Exception as e:
            logger.warning(f"  [ERRO] Erro ao ler {json_path.name}: {e}")

    report_config = config.get("report", {})
    generate_comparison_report(results, output_dir, report_config)

    print(f"\nRelatorio consolidado gerado com {len(results)} experimentos")


def main():
    parser = argparse.ArgumentParser(
        description="Executa experimentos de avaliação de geração do legal-service"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="evals/experiments.yaml",
        help="Caminho para o arquivo de configuração YAML (default: evals/experiments.yaml)"
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        help="Executa apenas o experimento especificado"
    )
    parser.add_argument(
        "--group",
        type=str,
        default=None,
        help="Executa apenas experimentos do grupo especificado (ex: round1, round2)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista experimentos disponíveis e sai"
    )
    parser.add_argument(
        "--report-all",
        action="store_true",
        help="Gera relatório consolidado de TODOS os resultados existentes no disco (não executa nada)"
    )
    
    args = parser.parse_args()
    
    # Resolver caminho do config
    config_path = Path(args.config)
    if not config_path.is_absolute():
        if config_path.exists():
            config_path = config_path.resolve()
        else:
            config_path = (project_root / config_path).resolve()
    
    try:
        config = load_experiments_config(str(config_path))
        
        if args.list:
            list_experiments(config)
            return
        
        if args.report_all:
            report_all_from_disk(config)
            return
        
        results = run_experiments(
            config=config,
            experiment_filter=args.experiment,
            group_filter=args.group,
        )
        
        # Resumo final
        successful = sum(1 for r in results if "error" not in r)
        failed = len(results) - successful
        
        print(f"\nExperimentos concluidos: {successful}")
        if failed > 0:
            print(f"Experimentos com erro: {failed}")
        
        # Mostrar localização dos resultados
        output_dir = Path(__file__).parent.resolve() / "results"
        
        # Mostra caminho amigável (dentro do container é /app, mas fora é legal-service)
        display_path = str(output_dir).replace("/app/", "legal-service/")
        print(f"\nResultados salvos em: {display_path}")
        
        # Listar arquivos gerados
        if output_dir.exists():
            result_files = sorted(output_dir.glob("*.json")) + sorted(output_dir.glob("*.csv"))
            if result_files:
                print(f"   Arquivos gerados nesta execução:")
                timestamp_prefix = datetime.now().strftime("%Y%m%d")
                for f in result_files:
                    if timestamp_prefix in f.name:
                        print(f"   - {f.name}")
        
    except Exception as e:
        logger.error(f"Erro ao executar experimentos: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
