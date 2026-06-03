"""
Script de comparación entre Clustering Tradicional y MAPPER (TDA).

Genera un informe comparativo con métricas cuantitativas y cualitativas para el TFG.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict
import numpy as np

from creditdataqc._log import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"


def leer_metricas_clustering(fecha: str = None) -> Dict:
    """Lee métricas de clustering tradicional."""
    if fecha is None:
        # fecha = pd.Timestamp.today().strftime('%Y-%m-%d')
        fecha = '2026-04-23'  # Fecha fija para testing

    json_file = DATA_OUTPUT_DIR / f"clustering_metrics_{fecha}.json"

    if not json_file.exists():
        raise FileNotFoundError(f"No se encontró archivo de métricas clustering: {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def leer_metricas_mapper(fecha: str = None) -> Dict:
    """Lee métricas de MAPPER."""
    if fecha is None:
        # fecha = pd.Timestamp.today().strftime('%Y-%m-%d')
        fecha = '2026-04-23'  # Fecha fija para testing

    json_file = DATA_OUTPUT_DIR / f"mapper_metrics_{fecha}.json"

    if not json_file.exists():
        raise FileNotFoundError(f"No se encontró archivo de métricas MAPPER: {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generar_tabla_comparativa(metricas_clustering: Dict, metricas_mapper: Dict) -> pd.DataFrame:
    """
    Genera tabla comparativa de métricas cuantitativas.

    Returns:
        DataFrame con comparación lado a lado
    """
    # Extraer métricas de cada método
    kmeans = metricas_clustering['kmeans']
    dbscan = metricas_clustering['dbscan']
    hierarchical = metricas_clustering['hierarchical']
    mapper = metricas_mapper['capacidad_predictiva']
    mapper_estructura = metricas_mapper['estructura_grafo']

    # Crear DataFrame comparativo
    data = {
        'Métrica': [
            '--- CALIDAD DE CLUSTERING ---',
            'Silhouette Score',
            'Davies-Bouldin Index',
            'Calinski-Harabasz',
            '',
            '--- CAPACIDAD PREDICTIVA ---',
            'Precision',
            'Recall',
            'F1-Score',
            '',
            '--- ESTRUCTURA ---',
            'Número de Grupos',
            'Grupos Estancos',
            'Solapamiento Permitido',
            'Outliers Detectados',
        ],
        'K-Means': [
            '',
            f"{kmeans['silhouette']:.3f}",
            f"{kmeans['davies_bouldin']:.3f}",
            f"{kmeans['calinski_harabasz']:.0f}",
            '',
            '',
            f"{kmeans['precision']:.3f}",
            f"{kmeans['recall']:.3f}",
            f"{kmeans['f1_score']:.3f}",
            '',
            '',
            f"{kmeans['n_clusters']}",
            'Sí',
            'No',
            'No',
        ],
        'DBSCAN': [
            '',
            f"{dbscan['silhouette']:.3f}" if dbscan['silhouette'] is not None else 'N/A',
            f"{dbscan['davies_bouldin']:.3f}" if dbscan['davies_bouldin'] is not None else 'N/A',
            f"{dbscan['calinski_harabasz']:.0f}" if dbscan['calinski_harabasz'] is not None else 'N/A',
            '',
            '',
            f"{dbscan['precision']:.3f}",
            f"{dbscan['recall']:.3f}",
            f"{dbscan['f1_score']:.3f}",
            '',
            '',
            f"{dbscan['n_clusters']}",
            'Sí',
            'No',
            f"Sí ({dbscan['pct_outliers']:.1f}%)",
        ],
        'Hierarchical': [
            '',
            f"{hierarchical['silhouette']:.3f}",
            f"{hierarchical['davies_bouldin']:.3f}",
            f"{hierarchical['calinski_harabasz']:.0f}",
            '',
            '',
            f"{hierarchical['precision']:.3f}",
            f"{hierarchical['recall']:.3f}",
            f"{hierarchical['f1_score']:.3f}",
            '',
            '',
            f"{hierarchical['n_clusters']}",
            'Sí',
            'No',
            'No',
        ],
        'MAPPER (TDA)': [
            '',
            'N/A',
            'N/A',
            'N/A',
            '',
            '',
            f"{mapper['precision']:.3f}",
            f"{mapper['recall']:.3f}",
            f"{mapper['f1_score']:.3f}",
            '',
            '',
            f"{mapper_estructura['n_nodos']} nodos",
            'No',
            f"Sí ({mapper_estructura['pct_solapamiento']:.1f}%)",
            'Implícito en grafo',
        ]
    }

    df_comparativa = pd.DataFrame(data)
    return df_comparativa


def analizar_ventajas_desventajas() -> Dict:
    """
    Análisis cualitativo: ventajas y desventajas de cada enfoque.

    Returns:
        Dict con ventajas/desventajas por método
    """
    analisis = {
        'clustering_tradicional': {
            'ventajas': [
                '✅ Rápido y escalable (O(n·k) para K-Means)',
                '✅ Fácil de implementar y reproducir',
                '✅ Asignación clara: cada cliente pertenece a un solo cluster',
                '✅ Métricas bien establecidas (Silhouette, DBI, CHI)',
                '✅ Interpretable con análisis de centroides (K-Means)'
            ],
            'desventajas': [
                '❌ Supone clusters esféricos (K-Means) o de densidad uniforme (DBSCAN)',
                '❌ No captura transiciones graduales entre perfiles',
                '❌ Pierde información de estructura topológica',
                '❌ Sensible a hiperparámetros (k, eps)',
                '❌ No visualiza "caminos" de deterioro crediticio'
            ]
        },
        'mapper_tda': {
            'ventajas': [
                '✅ Preserva estructura topológica (caminos, ciclos, huecos)',
                '✅ Permite solapamiento: clientes en múltiples nodos',
                '✅ Visualización intuitiva: grafo interactivo 2D',
                '✅ Detecta regiones de transición (zona gris)',
                '✅ Ideal para datos de alta dimensión con relaciones no lineales',
                '✅ Robusto a outliers (aparecen como nodos aislados)'
            ],
            'desventajas': [
                '❌ Más lento que clustering tradicional (O(n²) en casos extremos)',
                '❌ Métricas de calidad menos estandarizadas',
                '❌ Requiere elección de lens function (PCA, t-SNE...)',
                '❌ Sensible a parámetros (n_cubes, overlap, clustering interno)',
                '❌ Grafo puede ser difícil de interpretar sin contexto de negocio'
            ]
        }
    }

    return analisis


def recomendar_cuando_usar(metricas_clustering: Dict, metricas_mapper: Dict) -> Dict:
    """
    Genera recomendaciones prácticas de cuándo usar cada enfoque.
    """
    # Comparar F1-scores
    f1_kmeans = metricas_clustering['kmeans']['f1_score']
    f1_dbscan = metricas_clustering['dbscan']['f1_score']
    f1_hier = metricas_clustering['hierarchical']['f1_score']
    f1_mapper = metricas_mapper['capacidad_predictiva']['f1_score']

    mejor_clustering = max(
        [('K-Means', f1_kmeans), ('DBSCAN', f1_dbscan), ('Hierarchical', f1_hier)],
        key=lambda x: x[1]
    )[0]

    recomendaciones = {
        'clustering_tradicional': {
            'usar_cuando': [
                '🎯 Necesitas segmentación rápida de clientes (producción)',
                '🎯 Quieres asignación única por cliente (sin ambigüedad)',
                '🎯 Prioridad: velocidad de ejecución',
                '🎯 Dataset < 100k clientes',
                '🎯 Clusters bien separados y esféricos',
                f'🎯 Mejor método: {mejor_clustering} (F1={max(f1_kmeans, f1_dbscan, f1_hier):.3f})'
            ]
        },
        'mapper_tda': {
            'usar_cuando': [
                '🔍 Necesitas explorar estructura de los datos (análisis exploratorio)',
                '🔍 Quieres detectar caminos de deterioro crediticio',
                '🔍 Prioridad: interpretabilidad visual',
                '🔍 Datos con relaciones no lineales complejas',
                '🔍 Importante identificar zonas de transición (zona gris)',
                f'🔍 F1-Score MAPPER: {f1_mapper:.3f}'
            ]
        }
    }

    return recomendaciones


def generar_informe_completo(fecha: str = None) -> str:
    """
    Genera informe completo comparando clustering tradicional vs MAPPER.

    Args:
        fecha: Fecha de los archivos de métricas (formato YYYY-MM-DD)

    Returns:
        Path al archivo de informe generado
    """
    logger.info("=" * 80)
    logger.info("GENERANDO INFORME COMPARATIVO: CLUSTERING vs MAPPER")
    logger.info("=" * 80)

    # 1. Cargar métricas
    try:
        metricas_clustering = leer_metricas_clustering(fecha)
        metricas_mapper = leer_metricas_mapper(fecha)
    except FileNotFoundError as e:
        logger.error(f"Error al cargar métricas: {e}")
        return None

    # 2. Generar tabla comparativa
    df_comparativa = generar_tabla_comparativa(metricas_clustering, metricas_mapper)

    # 3. Análisis cualitativo
    ventajas_desventajas = analizar_ventajas_desventajas()
    recomendaciones = recomendar_cuando_usar(metricas_clustering, metricas_mapper)

    # 4. Exportar informe a Excel
    # fecha_str = fecha or pd.Timestamp.today().strftime('%Y-%m-%d')
    fecha_str = fecha or '2026-04-23'  # Fecha fija para testing
    output_file = DATA_OUTPUT_DIR / f"informe_comparativo_{fecha_str}.xlsx"

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Hoja 1: Resumen ejecutivo
        resumen_data = {
            'Aspecto': [
                'Total Clientes Analizados',
                'Total Morosos',
                '% Morosidad Global',
                '',
                'Mejor F1-Score (Clustering)',
                'F1-Score MAPPER',
                '',
                'Tiempo de Análisis (aprox)',
            ],
            'Valor': [
                metricas_clustering['metadata']['n_clientes'],
                metricas_clustering['metadata']['n_morosos_total'],
                f"{metricas_clustering['metadata']['pct_morosos_global']:.2f}%",
                '',
                f"{max(metricas_clustering['kmeans']['f1_score'], metricas_clustering['dbscan']['f1_score'], metricas_clustering['hierarchical']['f1_score']):.3f}",
                f"{metricas_mapper['capacidad_predictiva']['f1_score']:.3f}",
                '',
                'Clustering: ~1 min | MAPPER: ~17 min',
            ]
        }
        pd.DataFrame(resumen_data).to_excel(writer, sheet_name='Resumen Ejecutivo', index=False)

        # Hoja 2: Comparación cuantitativa
        df_comparativa.to_excel(writer, sheet_name='Comparacion Cuantitativa', index=False)

        # Hoja 3: Ventajas y Desventajas
        ventajas_df = pd.DataFrame({
            'Clustering Tradicional - VENTAJAS': ventajas_desventajas['clustering_tradicional']['ventajas'],
        })
        desventajas_df = pd.DataFrame({
            'Clustering Tradicional - DESVENTAJAS': ventajas_desventajas['clustering_tradicional']['desventajas'],
        })
        ventajas_mapper_df = pd.DataFrame({
            'MAPPER (TDA) - VENTAJAS': ventajas_desventajas['mapper_tda']['ventajas'],
        })
        desventajas_mapper_df = pd.DataFrame({
            'MAPPER (TDA) - DESVENTAJAS': ventajas_desventajas['mapper_tda']['desventajas'],
        })

        # Concatenar todas en una hoja
        df_cualitativo = pd.concat([
            ventajas_df,
            pd.DataFrame([''] * len(ventajas_df)),  # Espacio
            desventajas_df,
            pd.DataFrame([''] * len(desventajas_df)),  # Espacio
            ventajas_mapper_df,
            pd.DataFrame([''] * len(ventajas_mapper_df)),  # Espacio
            desventajas_mapper_df
        ], axis=1)
        df_cualitativo.to_excel(writer, sheet_name='Analisis Cualitativo', index=False)

        # Hoja 4: Recomendaciones
        rec_clustering_df = pd.DataFrame({
            'Usar Clustering Tradicional Cuando': recomendaciones['clustering_tradicional']['usar_cuando'],
        })
        rec_mapper_df = pd.DataFrame({
            'Usar MAPPER (TDA) Cuando': recomendaciones['mapper_tda']['usar_cuando'],
        })
        df_recomendaciones = pd.concat([rec_clustering_df, rec_mapper_df], axis=1)
        df_recomendaciones.to_excel(writer, sheet_name='Recomendaciones', index=False)

        # Hoja 5: Top Clusters de Alto Riesgo (K-Means)
        top_clusters_km = pd.DataFrame(metricas_clustering['kmeans']['top_3_clusters_alto_riesgo'])
        if not top_clusters_km.empty:
            top_clusters_km['top_features'] = top_clusters_km['top_features'].apply(
                lambda x: ', '.join([f"{f[0]}={f[1]:.2f}" for f in x]) if isinstance(x, list) else str(x)
            )
            top_clusters_km.to_excel(writer, sheet_name='Top Clusters K-Means', index=False)

        # Hoja 6: Top Clusters de Alto Riesgo (DBSCAN)
        top_clusters_db = pd.DataFrame(metricas_clustering['dbscan']['top_3_clusters_alto_riesgo'])
        if not top_clusters_db.empty:
            top_clusters_db['top_features'] = top_clusters_db['top_features'].apply(
                lambda x: ', '.join([f"{f[0]}={f[1]:.2f}" for f in x]) if isinstance(x, list) else str(x)
            )
            top_clusters_db.to_excel(writer, sheet_name='Top Clusters DBSCAN', index=False)

        # Hoja 7: Top Clusters de Alto Riesgo (Hierarchical)
        top_clusters_hier = pd.DataFrame(metricas_clustering['hierarchical']['top_3_clusters_alto_riesgo'])
        if not top_clusters_hier.empty:
            top_clusters_hier['top_features'] = top_clusters_hier['top_features'].apply(
                lambda x: ', '.join([f"{f[0]}={f[1]:.2f}" for f in x]) if isinstance(x, list) else str(x)
            )
            top_clusters_hier.to_excel(writer, sheet_name='Top Clusters Hierarchical', index=False)

    logger.info(f"Informe comparativo generado: {output_file}")
    logger.info("=" * 80)
    logger.info("RESUMEN DE COMPARACIÓN")
    logger.info("=" * 80)
    logger.info(f"Total clientes: {metricas_clustering['metadata']['n_clientes']:,}")
    logger.info(f"Morosidad global: {metricas_clustering['metadata']['pct_morosos_global']:.2f}%")
    logger.info("\nF1-Scores:")
    logger.info(f"  K-Means:      {metricas_clustering['kmeans']['f1_score']:.3f}")
    logger.info(f"  DBSCAN:       {metricas_clustering['dbscan']['f1_score']:.3f}")
    logger.info(f"  Hierarchical: {metricas_clustering['hierarchical']['f1_score']:.3f}")
    logger.info(f"  MAPPER (TDA): {metricas_mapper['capacidad_predictiva']['f1_score']:.3f}")
    logger.info("=" * 80)

    return str(output_file)


if __name__ == "__main__":
    # Generar informe con fecha más reciente
    try:
        informe_path = generar_informe_completo()
        if informe_path:
            print(f"\n[OK] Informe comparativo generado: {informe_path}")
        else:
            print("\n[ERROR] No se pudo generar el informe")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
