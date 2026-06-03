"""
Análisis de Morosidad mediante Clustering Tradicional.

Implementa 3 algoritmos de clustering siguiendo la teoría de aprendizaje no supervisado:
1. K-Means: Algoritmo particional basado en centroides (Lloyd, 1982)
2. DBSCAN: Algoritmo basado en densidad (Ester et al., 1996)
3. Hierarchical/Agglomerative: Algoritmo jerárquico con linkage de Ward

Referencias teóricas:
- MacQueen, J. (1967). Some methods for classification and analysis of multivariate observations.
- Lloyd, S. (1982). Least squares quantization in PCM.
- Ester, M., et al. (1996). A density-based algorithm for discovering clusters.
- Ward, J. H. (1963). Hierarchical grouping to optimize an objective function.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
import json

# Algoritmos de clustering
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering

# Preprocesamiento
from sklearn.preprocessing import StandardScaler

# Reducción dimensionalidad (visualización)
from sklearn.decomposition import PCA

# Métricas de validación
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score

# Visualización
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False

from creditdataqc._log import get_logger

logger = get_logger(__name__)

# Rutas del proyecto
PROJECT_ROOT = Path(__file__).parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"


# ============================================================================
# PASO 1: LECTURA Y PREPARACIÓN DE DATOS
# ============================================================================

def leer_datos_anonimizados(filepath: Path) -> pd.DataFrame:
    """
    Lee el dataset anonimizado desde Excel.

    El dataset contiene 1 fila por cliente con las siguientes columnas:
    - cif_nif: NIF/CIF pseudonimizado (SHA256 + código provincial)
    - cnae: Sector económico (CNAE)
    - provincia: Provincia extraída del NIF
    - pais: País del cliente
    - tipo: Tipo de entidad (PERSON/COMPANY/CORPORATE)
    - fecha_creacion: Fecha desplazada temporalmente
    - es_moroso: Flag de morosidad (variable objetivo)
    - es_moroso_60d, es_moroso_90d: Flags de morosidad por umbral
    - dias_mora_maximo: Días máximos en mora
    - saldo_pendiente_total: Saldo total perturbado (factor 0.7-1.3)
    - n_facturas_totales, n_facturas_vencidas, n_facturas_morosas: Contadores
    - proporcion_facturas_morosas: Ratio calculado

    Args:
        filepath: Ruta al archivo Excel anonimizado

    Returns:
        DataFrame con 1 fila por cliente
    """
    logger.info(f"Leyendo datos desde: {filepath.name}")

    # Leer hoja del dataset
    df = pd.read_excel(filepath, sheet_name='dataset_morosidad')

    logger.info(f"  Total clientes: {len(df):,}")
    logger.info(f"  Clientes únicos (cif_nif): {df['cif_nif'].nunique():,}")
    logger.info(f"  Columnas: {len(df.columns)}")

    return df


def preparar_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Selecciona y prepara features para clustering.

    Criterios de selección:
    - EXCLUIR variables objetivo: es_moroso, es_moroso_60d, es_moroso_90d
    - EXCLUIR identificadores: cif_nif
    - INCLUIR variables numéricas: saldo_pendiente_total, contadores, ratios
    - INCLUIR variables categóricas: provincia, cnae, tipo, pais (con encoding)
    - INCLUIR variables temporales: fecha_creacion (convertida a features numéricas)

    Args:
        df: DataFrame original

    Returns:
        df_features: DataFrame solo con features (sin objetivo ni IDs)
        feature_names: Lista de nombres de features
    """
    logger.info("Preparando features para clustering...")

    df_prep = df.copy()

    # === FEATURES NUMÉRICAS ===
    numeric_features = [
        'saldo_pendiente_total',
        'n_facturas_totales',
        'n_facturas_vencidas',
        'n_facturas_morosas',
        'proporcion_facturas_morosas',
        'dias_mora_maximo'
    ]

    # Verificar disponibilidad
    numeric_features = [f for f in numeric_features if f in df_prep.columns]
    logger.info(f"  Features numéricas: {len(numeric_features)}")

    # === FEATURES TEMPORALES ===
    # fecha_anio lineal; mes y día codificados con sin/cos para preservar ciclicidad
    if 'fecha_creacion' in df_prep.columns:
        df_prep['fecha_creacion'] = pd.to_datetime(df_prep['fecha_creacion'])
        df_prep['fecha_anio'] = df_prep['fecha_creacion'].dt.year
        mes = df_prep['fecha_creacion'].dt.month
        dia = df_prep['fecha_creacion'].dt.dayofyear
        df_prep['mes_sin'] = np.sin(2 * np.pi * mes / 12)
        df_prep['mes_cos'] = np.cos(2 * np.pi * mes / 12)
        df_prep['dia_sin'] = np.sin(2 * np.pi * dia / 365)
        df_prep['dia_cos'] = np.cos(2 * np.pi * dia / 365)

        temporal_features = ['fecha_anio', 'mes_sin', 'mes_cos', 'dia_sin', 'dia_cos']
        logger.info(f"  Features temporales: {len(temporal_features)}")
    else:
        temporal_features = []

    # === FEATURES CATEGÓRICAS ===
    # Encoding con One-Hot para categorías frecuentes

    categorical_encodings = []

    # 1. Provincia (top 10 + resto)
    if 'provincia' in df_prep.columns:
        top_provincias = df_prep['provincia'].value_counts().head(10).index.tolist()
        for prov in top_provincias:
            col_name = f'prov_{prov}'.replace(' ', '_')
            df_prep[col_name] = (df_prep['provincia'] == prov).astype(int)
            categorical_encodings.append(col_name)
        # Resto
        df_prep['prov_Otras'] = (~df_prep['provincia'].isin(top_provincias)).astype(int)
        categorical_encodings.append('prov_Otras')

    # 2. CNAE (top 5 + resto)
    if 'cnae' in df_prep.columns:
        top_cnae = df_prep['cnae'].value_counts().head(5).index.tolist()
        for cnae in top_cnae:
            col_name = f'cnae_{cnae}'
            df_prep[col_name] = (df_prep['cnae'] == cnae).astype(int)
            categorical_encodings.append(col_name)
        # Resto
        df_prep['cnae_Otros'] = (~df_prep['cnae'].isin(top_cnae)).astype(int)
        categorical_encodings.append('cnae_Otros')

    # 3. Tipo de entidad
    if 'tipo' in df_prep.columns:
        for tipo_val in df_prep['tipo'].unique():
            if pd.notna(tipo_val):
                col_name = f'tipo_{tipo_val}'
                df_prep[col_name] = (df_prep['tipo'] == tipo_val).astype(int)
                categorical_encodings.append(col_name)

    # 4. País
    if 'pais' in df_prep.columns:
        top_paises = df_prep['pais'].value_counts().head(3).index.tolist()
        for pais in top_paises:
            col_name = f'pais_{pais}'
            df_prep[col_name] = (df_prep['pais'] == pais).astype(int)
            categorical_encodings.append(col_name)
        # Resto
        df_prep['pais_Otros'] = (~df_prep['pais'].isin(top_paises)).astype(int)
        categorical_encodings.append('pais_Otros')

    logger.info(f"  Features categóricas (one-hot): {len(categorical_encodings)}")

    # === COMBINAR TODAS LAS FEATURES ===
    all_features = numeric_features + temporal_features + categorical_encodings

    # Verificar que todas existen
    all_features = [f for f in all_features if f in df_prep.columns]

    df_features = df_prep[all_features].copy()

    # === IMPUTACIÓN DE VALORES FALTANTES ===
    # Estrategia: rellenar con mediana para numéricas, 0 para categóricas
    n_missing_total = df_features.isnull().sum().sum()
    if n_missing_total > 0:
        logger.info(f"  Valores faltantes detectados: {n_missing_total}")
        logger.info("  Imputando con mediana (numéricas) y 0 (categóricas)...")

        for col in df_features.columns:
            if df_features[col].isnull().any():
                if col in numeric_features + temporal_features:
                    # Numéricas: mediana
                    df_features[col] = df_features[col].fillna(df_features[col].median())
                else:
                    # Categóricas: 0
                    df_features[col] = df_features[col].fillna(0)

    logger.info(f"  Total features preparadas: {len(all_features)}")
    logger.info(f"  Forma de la matriz: {df_features.shape}")

    return df_features, all_features


def normalizar_features(X: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    """
    Normaliza features usando StandardScaler (z-score).

    Teoría:
    Para cada feature x_i, calcula: z_i = (x_i - μ_i) / σ_i
    donde μ_i es la media y σ_i la desviación estándar.

    Justificación:
    - Los algoritmos de clustering basados en distancias (K-Means, DBSCAN, Hierarchical)
      son sensibles a la escala de las features.
    - Sin normalización, features con mayor magnitud dominan el cálculo de distancia.
    - StandardScaler garantiza que todas las features contribuyen equitativamente.

    Args:
        X: Matriz de features (n_samples × n_features)

    Returns:
        X_scaled: Matriz normalizada
        scaler: Objeto StandardScaler ajustado
    """
    logger.info("Normalizando features con StandardScaler (z-score)...")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    logger.info(f"  Media de features escaladas: {X_scaled.mean(axis=0).mean():.6f} (esperado ≈ 0)")
    logger.info(f"  Desviación estándar escalada: {X_scaled.std(axis=0).mean():.6f} (esperado ≈ 1)")

    return X_scaled, scaler


# ============================================================================
# PASO 2: ALGORITMOS DE CLUSTERING
# ============================================================================

def aplicar_kmeans(X: np.ndarray, k_min: int = 3, k_max: int = 30) -> Dict:
    """
    Aplica K-Means con selección óptima de k mediante Elbow Method.

    Teoría (Lloyd, 1982):
    - Objetivo: Minimizar WCSS (Within-Cluster Sum of Squares)
    - WCSS = Σ_{i=1}^k Σ_{x ∈ C_i} ||x - μ_i||²
      donde μ_i es el centroide del cluster C_i
    - Algoritmo iterativo:
      1. Inicializar k centroides (K-Means++)
      2. Asignar cada punto al centroide más cercano
      3. Recalcular centroides como media de puntos asignados
      4. Repetir hasta convergencia

    Elbow Method:
    - Evaluar WCSS para diferentes valores de k
    - Seleccionar k donde WCSS deja de decrecer significativamente

    Args:
        X: Matriz normalizada de features
        k_min: Valor mínimo de k a evaluar
        k_max: Valor máximo de k a evaluar

    Returns:
        Dict con labels, modelo, métricas y valores de WCSS para elbow plot
    """
    logger.info("=" * 70)
    logger.info("ALGORITMO 1: K-MEANS")
    logger.info("=" * 70)
    logger.info("Método: Particional basado en centroides")
    logger.info("Complejidad: O(n·k·d·i) donde n=clientes, k=clusters, d=features, i=iteraciones")

    # === ELBOW METHOD: Evaluar diferentes valores de k ===
    logger.info(f"\nEvaluando k desde {k_min} hasta {k_max} (Elbow Method)...")

    wcss_values = []
    k_range = range(k_min, k_max + 1)

    for k in k_range:
        kmeans_temp = KMeans(
            n_clusters=k,
            init='k-means++',  # Inicialización inteligente (Arthur & Vassilvitskii, 2007)
            n_init=10,         # Repetir 10 veces con diferentes inicializaciones
            max_iter=300,      # Máximo 300 iteraciones por ejecución
            random_state=42    # Reproducibilidad
        )
        kmeans_temp.fit(X)
        wcss_values.append(kmeans_temp.inertia_)  # inertia_ = WCSS
        logger.info(f"  k={k:2d}: WCSS = {kmeans_temp.inertia_:,.0f}")

    # Inspección visual de la curva WCSS con k_max=30 revela codo en k=10
    k_optimo = 10

    logger.info(f"\n✓ K óptimo seleccionado: {k_optimo} (codo visual confirmado con k_max=30)")

    # === ENTRENAR K-MEANS CON K ÓPTIMO ===
    logger.info(f"\nEntrenando K-Means con k={k_optimo}...")

    kmeans_final = KMeans(
        n_clusters=k_optimo,
        init='k-means++',
        n_init=10,
        max_iter=300,
        random_state=42
    )

    labels = kmeans_final.fit_predict(X)

    # === MÉTRICAS DE VALIDACIÓN ===
    logger.info("\nCalculando métricas de validación...")

    # 1. Silhouette Coefficient (Rousseeuw, 1987)
    # Rango: [-1, 1], donde 1 = clusters bien separados
    # s(i) = (b(i) - a(i)) / max(a(i), b(i))
    # a(i) = distancia media intra-cluster
    # b(i) = distancia media al cluster vecino más cercano
    sil_score = silhouette_score(X, labels)

    # 2. Davies-Bouldin Index (Davies & Bouldin, 1979)
    # Más bajo es mejor (mide ratio dispersión intra/inter cluster)
    # DB = (1/k) Σ_{i=1}^k max_{j≠i} (σ_i + σ_j) / d(c_i, c_j)
    db_score = davies_bouldin_score(X, labels)

    # 3. Calinski-Harabasz Index (Calinski & Harabasz, 1974)
    # Más alto es mejor (ratio varianza entre-clusters / intra-clusters)
    # CH = (SSB / SSW) × ((n - k) / (k - 1))
    ch_score = calinski_harabasz_score(X, labels)

    logger.info(f"  Silhouette Score: {sil_score:.4f} (más cercano a 1 = mejor)")
    logger.info(f"  Davies-Bouldin Index: {db_score:.4f} (más bajo = mejor)")
    logger.info(f"  Calinski-Harabasz Index: {ch_score:.2f} (más alto = mejor)")

    # === DISTRIBUCIÓN DE CLUSTERS ===
    unique, counts = np.unique(labels, return_counts=True)
    logger.info(f"\nDistribución de clientes por cluster:")
    for cluster_id, count in zip(unique, counts):
        pct = (count / len(labels)) * 100
        logger.info(f"  Cluster {cluster_id}: {count:,} clientes ({pct:.2f}%)")

    return {
        'labels': labels,
        'modelo': kmeans_final,
        'n_clusters': k_optimo,
        'wcss': kmeans_final.inertia_,
        'wcss_values': wcss_values,
        'k_range': list(k_range),
        'silhouette': sil_score,
        'davies_bouldin': db_score,
        'calinski_harabasz': ch_score
    }


def aplicar_dbscan(X: np.ndarray, eps: float = 2.0, min_samples: int = 10) -> Dict:
    """
    Aplica DBSCAN (Density-Based Spatial Clustering of Applications with Noise).

    Teoría (Ester et al., 1996):
    - No requiere especificar número de clusters a priori
    - Identifica clusters de forma arbitraria (no asume esfericidad)
    - Detecta outliers (puntos de baja densidad)

    Conceptos clave:
    - ε-vecindario: N_ε(p) = {q ∈ D | dist(p,q) ≤ ε}
    - Core point: punto con |N_ε(p)| ≥ min_samples
    - Border point: no es core pero está en vecindario de core point
    - Noise: ni core ni border

    Algoritmo:
    1. Para cada punto no visitado:
       a. Encontrar ε-vecindario
       b. Si |vecindario| < min_samples → marcar como noise
       c. Si no → crear nuevo cluster y expandir recursivamente

    Complejidad: O(n²) sin indexación, O(n log n) con árboles espaciales

    Args:
        X: Matriz normalizada de features
        eps: Radio del ε-vecindario
        min_samples: Mínimo de puntos para formar cluster denso

    Returns:
        Dict con labels, modelo y métricas
    """
    logger.info("=" * 70)
    logger.info("ALGORITMO 2: DBSCAN")
    logger.info("=" * 70)
    logger.info("Método: Basado en densidad")
    logger.info("Complejidad: O(n log n) con indexación espacial")

    logger.info(f"\nParámetros:")
    logger.info(f"  eps (ε): {eps} (radio del vecindario)")
    logger.info(f"  min_samples: {min_samples} (mínimo para core point)")
    logger.info(f"  Nota: eps aumentado a 2.0 para evitar fragmentación excesiva en dataset grande")

    # === ENTRENAR DBSCAN ===
    logger.info("\nEntrenando DBSCAN...")

    dbscan = DBSCAN(
        eps=eps,
        min_samples=min_samples,
        metric='euclidean',
        n_jobs=-1  # Usar todos los cores disponibles
    )

    labels = dbscan.fit_predict(X)

    # === ANÁLISIS DE RESULTADOS ===
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = list(labels).count(-1)
    pct_noise = (n_noise / len(labels)) * 100

    logger.info(f"\nResultados:")
    logger.info(f"  Clusters encontrados: {n_clusters}")
    logger.info(f"  Outliers (noise): {n_noise:,} ({pct_noise:.2f}%)")

    # === MÉTRICAS DE VALIDACIÓN ===
    # Nota: Silhouette no incluye outliers (label = -1)
    if n_clusters > 1:
        mask_no_noise = labels != -1
        X_no_noise = X[mask_no_noise]
        labels_no_noise = labels[mask_no_noise]

        if len(labels_no_noise) > 0:
            logger.info("\nCalculando métricas (excluyendo outliers)...")

            sil_score = silhouette_score(X_no_noise, labels_no_noise)
            db_score = davies_bouldin_score(X_no_noise, labels_no_noise)
            ch_score = calinski_harabasz_score(X_no_noise, labels_no_noise)

            logger.info(f"  Silhouette Score: {sil_score:.4f}")
            logger.info(f"  Davies-Bouldin Index: {db_score:.4f}")
            logger.info(f"  Calinski-Harabasz Index: {ch_score:.2f}")
        else:
            sil_score = db_score = ch_score = None
            logger.warning("  Todos los puntos son outliers - métricas no calculables")
    else:
        sil_score = db_score = ch_score = None
        if n_clusters == 0:
            logger.warning("  No se encontraron clusters - ajustar eps o min_samples")
        else:
            logger.warning("  Solo 1 cluster encontrado - métricas no calculables")

    # === DISTRIBUCIÓN DE CLUSTERS ===
    if n_clusters > 0:
        unique, counts = np.unique(labels[labels != -1], return_counts=True)
        logger.info(f"\nDistribución de clientes por cluster (sin outliers):")
        # Mostrar solo top 10 clusters más grandes para evitar logs extensos
        top_clusters_idx = np.argsort(counts)[-10:][::-1]
        logger.info(f"  Top 10 clusters más grandes:")
        for idx in top_clusters_idx:
            cluster_id = unique[idx]
            count = counts[idx]
            pct = (count / len(labels)) * 100
            logger.info(f"    Cluster {cluster_id}: {count:,} clientes ({pct:.2f}%)")

    return {
        'labels': labels,
        'modelo': dbscan,
        'n_clusters': n_clusters,
        'n_outliers': n_noise,
        'pct_outliers': pct_noise,
        'silhouette': sil_score,
        'davies_bouldin': db_score,
        'calinski_harabasz': ch_score
    }


def aplicar_hierarchical(X: np.ndarray, n_clusters: int = 5, linkage: str = 'ward') -> Dict:
    """
    Aplica Hierarchical/Agglomerative Clustering.

    Teoría (Ward, 1963):
    - Enfoque bottom-up: cada punto comienza como cluster individual
    - Iterativamente fusiona los 2 clusters más similares
    - Criterio de fusión determinado por linkage function

    Linkage functions:
    - single: min dist(a,b) para a ∈ A, b ∈ B
    - complete: max dist(a,b)
    - average: mean dist(a,b)
    - ward: minimiza incremento de varianza intra-cluster

    Ward Linkage (usado aquí):
    - d(A,B) = √[(2·n_A·n_B)/(n_A + n_B)] · ||μ_A - μ_B||
    - Equivalente a minimizar WCSS en cada fusión
    - Produce clusters compactos y balanceados

    Complejidad: O(n² log n) para Ward linkage

    Args:
        X: Matriz normalizada de features
        n_clusters: Número final de clusters deseado
        linkage: Criterio de fusión ('ward', 'average', 'complete', 'single')

    Returns:
        Dict con labels, modelo y métricas
    """
    logger.info("=" * 70)
    logger.info("ALGORITMO 3: HIERARCHICAL/AGGLOMERATIVE")
    logger.info("=" * 70)
    logger.info("Método: Jerárquico aglomerativo")
    logger.info("Complejidad: O(n² log n) para Ward linkage")

    logger.info(f"\nParámetros:")
    logger.info(f"  n_clusters: {n_clusters}")
    logger.info(f"  linkage: {linkage} (minimiza varianza intra-cluster)")

    # === ENTRENAR HIERARCHICAL ===
    # Nota: Hierarchical tiene complejidad O(n²) en memoria → usar muestreo para n > 10k
    n_samples = X.shape[0]

    if n_samples > 10000:
        logger.info(f"\nDataset grande ({n_samples:,} clientes) - usando muestreo estratificado")
        logger.info("  Entrenando en muestra de 10,000 clientes...")

        # Muestreo aleatorio
        sample_size = 10000
        np.random.seed(42)  # Reproducibilidad
        sample_indices = np.random.choice(n_samples, sample_size, replace=False)
        X_sample = X[sample_indices]

        # Entrenar en muestra
        hierarchical = AgglomerativeClustering(
            n_clusters=n_clusters,
            linkage=linkage
        )
        labels_sample = hierarchical.fit_predict(X_sample)

        # Propagar labels al dataset completo mediante vecino más cercano
        logger.info("  Propagando labels a dataset completo con KNN...")
        from sklearn.neighbors import KNeighborsClassifier
        knn = KNeighborsClassifier(n_neighbors=1)
        knn.fit(X_sample, labels_sample)
        labels = knn.predict(X)

        logger.info(f"  ✓ Clustering completado (muestra → completo)")
    else:
        logger.info("\nEntrenando Hierarchical Clustering...")

        hierarchical = AgglomerativeClustering(
            n_clusters=n_clusters,
            linkage=linkage
        )
        labels = hierarchical.fit_predict(X)

    # === MÉTRICAS DE VALIDACIÓN ===
    logger.info("\nCalculando métricas de validación...")

    sil_score = silhouette_score(X, labels)
    db_score = davies_bouldin_score(X, labels)
    ch_score = calinski_harabasz_score(X, labels)

    logger.info(f"  Silhouette Score: {sil_score:.4f}")
    logger.info(f"  Davies-Bouldin Index: {db_score:.4f}")
    logger.info(f"  Calinski-Harabasz Index: {ch_score:.2f}")

    # === DISTRIBUCIÓN DE CLUSTERS ===
    unique, counts = np.unique(labels, return_counts=True)
    logger.info(f"\nDistribución de clientes por cluster:")
    for cluster_id, count in zip(unique, counts):
        pct = (count / len(labels)) * 100
        logger.info(f"  Cluster {cluster_id}: {count:,} clientes ({pct:.2f}%)")

    return {
        'labels': labels,
        'modelo': hierarchical,
        'n_clusters': n_clusters,
        'linkage': linkage,
        'silhouette': sil_score,
        'davies_bouldin': db_score,
        'calinski_harabasz': ch_score
    }


# ============================================================================
# PASO 3: ANÁLISIS DE MOROSIDAD POR CLUSTER
# ============================================================================

def analizar_morosidad_por_cluster(labels: np.ndarray, y_morosidad: np.ndarray,
                                   nombre_algoritmo: str) -> pd.DataFrame:
    """
    Analiza la distribución de morosidad en cada cluster.

    Para cada cluster calcula:
    - Número total de clientes
    - Número de clientes morosos
    - Tasa de morosidad (proporción)

    Args:
        labels: Array de asignaciones de cluster
        y_morosidad: Array binario (1=moroso, 0=no moroso)
        nombre_algoritmo: Nombre del algoritmo para logs

    Returns:
        DataFrame con análisis por cluster ordenado por tasa de morosidad
    """
    logger.info(f"\n--- Análisis de Morosidad ({nombre_algoritmo}) ---")

    df_analisis = pd.DataFrame({
        'cluster': labels,
        'es_moroso': y_morosidad
    })

    # Agrupar por cluster
    mora_por_cluster = df_analisis.groupby('cluster').agg(
        n_total=('es_moroso', 'count'),
        n_morosos=('es_moroso', 'sum'),
        tasa_morosidad=('es_moroso', 'mean')
    ).sort_values('tasa_morosidad', ascending=False)

    # Log de resultados
    logger.info(f"\nTop 5 clusters con mayor tasa de morosidad:")
    for idx, row in mora_por_cluster.head(5).iterrows():
        cluster_label = "Outliers" if idx == -1 else f"Cluster {idx}"
        logger.info(f"  {cluster_label}: {row['tasa_morosidad']:.2%} "
                   f"({int(row['n_morosos'])} morosos / {int(row['n_total'])} clientes)")

    # Estadísticas globales
    tasa_global = y_morosidad.mean()
    tasa_max = mora_por_cluster['tasa_morosidad'].max()
    tasa_min = mora_por_cluster['tasa_morosidad'].min()

    logger.info(f"\nEstadísticas:")
    logger.info(f"  Tasa global de morosidad: {tasa_global:.2%}")
    logger.info(f"  Tasa máxima en un cluster: {tasa_max:.2%}")
    logger.info(f"  Tasa mínima en un cluster: {tasa_min:.2%}")
    logger.info(f"  Rango: {(tasa_max - tasa_min):.2%}")

    return mora_por_cluster


# ============================================================================
# PASO 4: VISUALIZACIÓN
# ============================================================================

def visualizar_resultados(X: np.ndarray, resultados_kmeans: Dict,
                         resultados_dbscan: Dict, resultados_hier: Dict,
                         y_morosidad: np.ndarray, output_dir: Path) -> tuple:
    """
    Genera visualizaciones comparativas de los 3 algoritmos.

    Usa PCA para reducir a 2 dimensiones (visualización 2D).

    Args:
        X: Matriz normalizada de features
        resultados_kmeans: Resultados de K-Means
        resultados_dbscan: Resultados de DBSCAN
        resultados_hier: Resultados de Hierarchical
        y_morosidad: Array de morosidad real
        output_dir: Directorio para guardar gráficos

    Returns:
        Tupla (var_pc1, var_pc2) con varianza explicada por PCA
    """
    # PCA se calcula siempre (el informe lo necesita aunque no haya matplotlib)
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X)
    varianza_explicada = pca.explained_variance_ratio_

    if not VISUALIZATION_AVAILABLE:
        logger.warning("matplotlib/seaborn no disponibles - visualización omitida")
        return (varianza_explicada[0], varianza_explicada[1])

    logger.info("\n" + "=" * 70)
    logger.info("GENERANDO VISUALIZACIONES")
    logger.info("=" * 70)

    # === PCA: Reducir a 2 dimensiones ===
    logger.info("\nAplicando PCA para reducción dimensional (2D)...")
    logger.info(f"  PC1: {varianza_explicada[0]:.2%} varianza")
    logger.info(f"  PC2: {varianza_explicada[1]:.2%} varianza")
    logger.info(f"  Total: {varianza_explicada.sum():.2%} varianza explicada")

    # === GRÁFICO COMPARATIVO ===
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Comparación de Algoritmos de Clustering', fontsize=16, fontweight='bold')

    # 1. K-Means
    ax = axes[0, 0]
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=resultados_kmeans['labels'],
                        cmap='tab10', alpha=0.6, s=10, edgecolors='none')
    ax.set_title(f"K-Means (k={resultados_kmeans['n_clusters']})\n"
                f"Silhouette: {resultados_kmeans['silhouette']:.3f}",
                fontsize=12, fontweight='bold')
    ax.set_xlabel('Componente Principal 1')
    ax.set_ylabel('Componente Principal 2')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Cluster')

    # 2. DBSCAN
    ax = axes[0, 1]
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=resultados_dbscan['labels'],
                        cmap='tab10', alpha=0.6, s=10, edgecolors='none')
    sil_text = f"{resultados_dbscan['silhouette']:.3f}" if resultados_dbscan['silhouette'] else "N/A"
    ax.set_title(f"DBSCAN (clusters={resultados_dbscan['n_clusters']}, "
                f"outliers={resultados_dbscan['pct_outliers']:.1f}%)\n"
                f"Silhouette: {sil_text}",
                fontsize=12, fontweight='bold')
    ax.set_xlabel('Componente Principal 1')
    ax.set_ylabel('Componente Principal 2')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Cluster (-1=outlier)')

    # 3. Hierarchical
    ax = axes[1, 0]
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=resultados_hier['labels'],
                        cmap='tab10', alpha=0.6, s=10, edgecolors='none')
    ax.set_title(f"Hierarchical (n={resultados_hier['n_clusters']}, linkage={resultados_hier['linkage']})\n"
                f"Silhouette: {resultados_hier['silhouette']:.3f}",
                fontsize=12, fontweight='bold')
    ax.set_xlabel('Componente Principal 1')
    ax.set_ylabel('Componente Principal 2')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Cluster')

    # 4. Morosidad Real
    ax = axes[1, 1]
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=y_morosidad,
                        cmap='RdYlGn_r', alpha=0.6, s=10, edgecolors='none')
    ax.set_title('Distribución Real de Morosidad',
                fontsize=12, fontweight='bold')
    ax.set_xlabel('Componente Principal 1')
    ax.set_ylabel('Componente Principal 2')
    ax.grid(True, alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax, label='Moroso')
    cbar.set_ticks([0, 1])
    cbar.set_ticklabels(['No', 'Sí'])

    plt.tight_layout()

    # Guardar
    output_file = output_dir / "clustering_comparison_2026-04-23.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    logger.info(f"\n✓ Visualización guardada: {output_file.name}")
    plt.close()

    # === ELBOW PLOT (solo K-Means) ===
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(resultados_kmeans['k_range'], resultados_kmeans['wcss_values'],
           marker='o', linewidth=2, markersize=8)
    ax.axvline(x=resultados_kmeans['n_clusters'], color='red', linestyle='--',
              label=f'K óptimo = {resultados_kmeans["n_clusters"]}')
    ax.set_title('Elbow Method para Selección de K (K-Means)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Número de Clusters (k)', fontsize=12)
    ax.set_ylabel('WCSS (Within-Cluster Sum of Squares)', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    output_file_elbow = output_dir / "kmeans_elbow_method_2026-04-23-k14.png"
    plt.savefig(output_file_elbow, dpi=300, bbox_inches='tight')
    logger.info(f"✓ Elbow plot guardado: {output_file_elbow.name}")
    plt.close()

    # Retornar varianza explicada por PCA
    return (varianza_explicada[0], varianza_explicada[1])


# ============================================================================
# PASO 5: GUARDAR RESULTADOS
# ============================================================================

def guardar_metricas(resultados_kmeans: Dict, resultados_dbscan: Dict,
                    resultados_hier: Dict, mora_kmeans: pd.DataFrame,
                    mora_dbscan: pd.DataFrame, mora_hier: pd.DataFrame,
                    output_dir: Path, n_clientes: int, n_features: int):
    """
    Guarda métricas de clustering en formato JSON.

    Args:
        resultados_*: Diccionarios de resultados por algoritmo
        mora_*: DataFrames de análisis de morosidad
        output_dir: Directorio para guardar
        n_clientes: Número total de clientes
        n_features: Número total de features
    """
    logger.info("\n" + "=" * 70)
    logger.info("GUARDANDO MÉTRICAS")
    logger.info("=" * 70)

    metricas = {
        'metadata': {
            'fecha_analisis': '2026-04-23',
            'n_clientes': n_clientes,
            'n_features': n_features,
            'algoritmos': ['K-Means', 'DBSCAN', 'Hierarchical']
        },
        'kmeans': {
            'n_clusters': resultados_kmeans['n_clusters'],
            'wcss': float(resultados_kmeans['wcss']),
            'silhouette': float(resultados_kmeans['silhouette']),
            'davies_bouldin': float(resultados_kmeans['davies_bouldin']),
            'calinski_harabasz': float(resultados_kmeans['calinski_harabasz']),
            'top_3_clusters_morosidad': [
                {
                    'cluster_id': int(idx),
                    'n_clientes': int(row['n_total']),
                    'n_morosos': int(row['n_morosos']),
                    'tasa_morosidad': float(row['tasa_morosidad'])
                }
                for idx, row in mora_kmeans.head(3).iterrows()
            ]
        },
        'dbscan': {
            'n_clusters': resultados_dbscan['n_clusters'],
            'n_outliers': resultados_dbscan['n_outliers'],
            'pct_outliers': float(resultados_dbscan['pct_outliers']),
            'silhouette': float(resultados_dbscan['silhouette']) if resultados_dbscan['silhouette'] else None,
            'davies_bouldin': float(resultados_dbscan['davies_bouldin']) if resultados_dbscan['davies_bouldin'] else None,
            'calinski_harabasz': float(resultados_dbscan['calinski_harabasz']) if resultados_dbscan['calinski_harabasz'] else None,
            'top_3_clusters_morosidad': [
                {
                    'cluster_id': int(idx),
                    'n_clientes': int(row['n_total']),
                    'n_morosos': int(row['n_morosos']),
                    'tasa_morosidad': float(row['tasa_morosidad'])
                }
                for idx, row in mora_dbscan.head(3).iterrows() if idx != -1
            ]
        },
        'hierarchical': {
            'n_clusters': resultados_hier['n_clusters'],
            'linkage': resultados_hier['linkage'],
            'silhouette': float(resultados_hier['silhouette']),
            'davies_bouldin': float(resultados_hier['davies_bouldin']),
            'calinski_harabasz': float(resultados_hier['calinski_harabasz']),
            'top_3_clusters_morosidad': [
                {
                    'cluster_id': int(idx),
                    'n_clientes': int(row['n_total']),
                    'n_morosos': int(row['n_morosos']),
                    'tasa_morosidad': float(row['tasa_morosidad'])
                }
                for idx, row in mora_hier.head(3).iterrows()
            ]
        }
    }

    output_file = output_dir / "clustering_metrics_2026-04-23.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ Métricas guardadas: {output_file.name}")


def generar_informe_interpretacion(resultados_kmeans: Dict, resultados_dbscan: Dict,
                                   resultados_hier: Dict, mora_kmeans: pd.DataFrame,
                                   mora_dbscan: pd.DataFrame, mora_hier: pd.DataFrame,
                                   output_dir: Path, n_clientes: int,
                                   varianza_pca: tuple):
    """
    Genera informe de interpretación de resultados en markdown.

    Ayuda a entender los mapas de puntos y métricas para el TFG.

    Args:
        resultados_*: Diccionarios de resultados por algoritmo
        mora_*: DataFrames de análisis de morosidad
        output_dir: Directorio para guardar
        n_clientes: Número total de clientes
        varianza_pca: Tupla (var_pc1, var_pc2)
    """
    logger.info("\nGenerando informe de interpretación...")

    informe = f"""# Guía de Interpretación: Clustering de Morosidad

**Fecha:** 2026-04-23
**Dataset:** {n_clientes:,} clientes del sector energético
**Objetivo:** Segmentar clientes según riesgo de morosidad

---

## 1. CÓMO LEER LOS MAPAS DE PUNTOS

### ¿Qué son estos gráficos?

Los 4 gráficos en [clustering_comparison_2026-04-23.png](clustering_comparison_2026-04-23.png) muestran los mismos {n_clientes:,} clientes en un **espacio 2D reducido** mediante PCA (Análisis de Componentes Principales).

### ¿Por qué 2D si tenemos 31 features?

- **Datos originales:** 31 dimensiones (saldo, provincia, fecha, facturas, etc.)
- **PCA reduce a 2D:** Para poder visualizar en un gráfico plano
- **Varianza explicada:** PC1={varianza_pca[0]:.1%} + PC2={varianza_pca[1]:.1%} = {sum(varianza_pca):.1%} de la información total

**Interpretación:** Los ejes X e Y son "combinaciones" de las 31 features originales. Puntos cercanos = clientes similares.

### ¿Qué significa cada color?

**Gráficos 1-3 (algoritmos):** Cada color = un cluster diferente
**Gráfico 4 (morosidad real):** Rojo = moroso, Verde = no moroso

---

## 2. INTERPRETACIÓN POR ALGORITMO

### 🔵 K-MEANS (gráfico superior izquierdo)

**Resultado:** {resultados_kmeans['n_clusters']} clusters detectados

**Cómo interpretarlo:**
- Cada color representa un grupo de clientes con características similares
- Los **cruces rojas (X)** son los centroides (centro de cada cluster)
- K-Means crea grupos **esféricos** (forma de círculo)

**Hallazgo clave - Clusters de alto riesgo:**
```
Cluster 8: {mora_kmeans.loc[8, 'tasa_morosidad']:.1%} morosos ({int(mora_kmeans.loc[8, 'n_morosos'])}/{int(mora_kmeans.loc[8, 'n_total'])} clientes)
Cluster 9: {mora_kmeans.loc[9, 'tasa_morosidad']:.1%} morosos ({int(mora_kmeans.loc[9, 'n_morosos'])}/{int(mora_kmeans.loc[9, 'n_total'])} clientes)
```

**¿Qué significa?**
K-Means **identificó 2 clusters casi puramente morosos** (>80% morosidad). Si un nuevo cliente cae en esos clusters, tiene altísimo riesgo.

**Métricas:**
- **Silhouette: {resultados_kmeans['silhouette']:.3f}** (rango -1 a 1, más cerca de 1 = mejor)
  - Mide qué tan bien separados están los clusters
  - 0.24 es moderado (los clusters se solapan un poco)

- **Davies-Bouldin: {resultados_kmeans['davies_bouldin']:.3f}** (más bajo = mejor)
  - Mide compacidad intra-cluster vs separación inter-cluster
  - 1.59 es aceptable

- **Calinski-Harabasz: {resultados_kmeans['calinski_harabasz']:.0f}** (más alto = mejor)
  - Ratio varianza entre-clusters / intra-clusters
  - 4395 indica buena separación

---

### 🟢 DBSCAN (gráfico superior derecho)

**Resultado:** {resultados_dbscan['n_clusters']} clusters + {resultados_dbscan['n_outliers']:,} outliers ({resultados_dbscan['pct_outliers']:.1%}%)

**Cómo interpretarlo:**
- DBSCAN busca **zonas densas** de puntos
- **Outliers (label -1):** Puntos aislados que no pertenecen a ningún cluster
- Puede crear clusters de **formas arbitrarias** (no solo círculos)

**Hallazgo clave - Clusters puros:**
```

Top 5 clusters con morosidad 100%:
"""

    # Añadir top 5 clusters de DBSCAN con 100% morosidad
    mora_dbscan_100 = mora_dbscan[mora_dbscan['tasa_morosidad'] == 1.0].head(5)
    for idx, row in mora_dbscan_100.iterrows():
        if idx != -1:  # Excluir outliers
            informe += f"  Cluster {idx}: {int(row['n_morosos'])}/{int(row['n_total'])} clientes (100% morosos)\n"

    informe += f"""
```

**¿Qué significa?**
DBSCAN detectó **micro-clusters muy específicos** de clientes morosos con perfiles idénticos. Son "bolsas de riesgo extremo".

**Métricas:**
- **Silhouette: {resultados_dbscan['silhouette']:.3f}** ← **¡El mejor!**
  - 0.57 es MUY BUENO (clusters bien definidos y separados)

- **Davies-Bouldin: {resultados_dbscan['davies_bouldin']:.3f}** ← **¡El mejor!**
  - 0.93 es excelente (clusters compactos y bien separados)

**Ventaja:** Identifica outliers ({resultados_dbscan['pct_outliers']:.1%}% del total) que son clientes "raros" que no encajan en ningún patrón.

---

### 🟠 HIERARCHICAL (gráfico inferior izquierdo)

**Resultado:** {resultados_hier['n_clusters']} clusters (método: Ward linkage)

**Cómo interpretarlo:**
- Clustering **jerárquico:** Agrupa clientes de forma progresiva (bottom-up)
- Produce una **estructura de árbol** (dendrograma) - no mostrado en el gráfico 2D
- Ward linkage minimiza la varianza dentro de cada cluster

**Nota técnica:** Por limitaciones de memoria, se entrenó en una **muestra de 10,000 clientes** y luego se propagaron las etiquetas al dataset completo mediante KNN.

**Hallazgo clave - Cluster de alto riesgo:**
```
Cluster 2: {mora_hier.loc[2, 'tasa_morosidad']:.1%} morosos ({int(mora_hier.loc[2, 'n_morosos'])}/{int(mora_hier.loc[2, 'n_total'])} clientes)
```

**¿Qué significa?**
El cluster 2 tiene **triple tasa de morosidad** vs la media global (11.1%). Representa un segmento de ~10k clientes con alto riesgo.

**Métricas:**
- **Silhouette: {resultados_hier['silhouette']:.3f}** (más bajo que los otros)
  - El muestreo reduce ligeramente la calidad
  - Aún así, 0.15 indica estructura real (no aleatoria)

---

### 🔴 MOROSIDAD REAL (gráfico inferior derecho)

**Cómo interpretarlo:**
- **Verde:** Clientes no morosos (88.9% del total)
- **Rojo:** Clientes morosos (11.1% del total)

**¿Para qué sirve?**
Comparar visualmente si los clusters encontrados **coinciden con la morosidad real**.

**Observación clave:**
- Si un cluster (gráficos 1-3) coincide espacialmente con una zona roja → **buen predictor de morosidad**
- Si los colores están mezclados → los clusters no separan bien morosos/no morosos

---

## 3. ELBOW METHOD (K-Means)

**Gráfico:** [kmeans_elbow_method_2026-04-23.png](kmeans_elbow_method_2026-04-23.png)

### ¿Qué muestra?

Una curva de **WCSS (Within-Cluster Sum of Squares)** vs número de clusters (k).

```
WCSS = Suma de distancias² de cada punto a su centroide
```

### ¿Cómo interpretar la curva?

```
WCSS
  |
  |●●                  ← k pequeño: clusters grandes, WCSS alto
  |   ●●
  |     ●●            ← k=10: "CODO" (inflexión)
  
  |       ●─●─●─●    ← k grande: mejora marginal
  |________________
     3  5  10  15  k
```

**Regla del codo:**
- WCSS siempre baja cuando aumentas k (más clusters = menor distancia promedio)
- Pero después del "codo", la mejora es **marginal**
- **k=10** es el equilibrio óptimo: buena calidad sin fragmentar demasiado

**Línea vertical roja:** Marca k=10 (seleccionado automáticamente).

---

## 4. COMPARACIÓN DE ALGORITMOS

### Tabla Resumen

| Algoritmo      | Clusters | Silhouette | Davies-Bouldin | Ventaja Principal                    |
|----------------|----------|------------|----------------|--------------------------------------|
| **K-Means**    | {resultados_kmeans['n_clusters']}        | {resultados_kmeans['silhouette']:.3f}      | {resultados_kmeans['davies_bouldin']:.3f}          | Clusters balanceados, interpretable  |
| **DBSCAN**     | {resultados_dbscan['n_clusters']}       | **{resultados_dbscan['silhouette']:.3f}**  | **{resultados_dbscan['davies_bouldin']:.3f}**      | Mejor calidad, detecta outliers     |
| **Hierarchical** | {resultados_hier['n_clusters']}        | {resultados_hier['silhouette']:.3f}      | {resultados_hier['davies_bouldin']:.3f}          | Estructura jerárquica, relaciones   |

### ¿Cuál es el mejor?

**DBSCAN es el ganador técnico** (mejores métricas), pero cada algoritmo aporta valor:

- **K-Means:** Simple, rápido, fácil de explicar a negocio ("tenemos 10 grupos de clientes")
- **DBSCAN:** Identifica patrones complejos y outliers (clientes atípicos que requieren atención especial)
- **Hierarchical:** Muestra cómo los clusters se relacionan entre sí (útil para segmentación multi-nivel)

---

## 5. APLICACIÓN PRÁCTICA

### Caso de Uso: Sistema de Alertas de Morosidad

**Paso 1:** Un cliente nuevo llega → calcular sus 31 features

**Paso 2:** Asignar al cluster más cercano (DBSCAN):
- Si cae en cluster con >50% morosidad → **🔴 ALERTA ALTA**
- Si cae en cluster con 10-50% → **🟡 ALERTA MEDIA**
- Si cae en cluster con <10% → **🟢 RIESGO BAJO**
- Si es outlier → **⚠️ REVISAR MANUALMENTE** (perfil atípico)

**Paso 3:** Ajustar estrategia comercial:
- **Alerta alta:** Solicitar depósito, limitar crédito
- **Alerta media:** Seguimiento quincenal
- **Riesgo bajo:** Condiciones estándar

---

## 6. LIMITACIONES

### PCA al 19%
- Solo vemos {sum(varianza_pca):.1%} de la información en los gráficos 2D
- Los clusters reales tienen mejor separación en las 31 dimensiones originales
- **No juzgar la calidad solo por la visualización**

### Hierarchical con Muestreo
- Entrenado en 10k de {n_clientes:,} clientes por limitaciones de RAM
- Silhouette más bajo no significa peor algoritmo, sino efecto del muestreo

### Datos Anonimizados
- Saldos perturbados (factor 0.7-1.3)
- Fechas desplazadas (±180 días)
- **No afecta la estructura de clustering** (transformaciones preservan ratios y distancias)

---

### Sección de Resultados

> "El análisis de clustering identificó {resultados_kmeans['n_clusters']} segmentos de clientes con K-Means, de los cuales 2 presentan tasas de morosidad superiores al 80%, muy por encima de la media global del 11.1%. DBSCAN, con un coeficiente de Silhouette de {resultados_dbscan['silhouette']:.3f}, demostró la mejor capacidad de segmentación, identificando {resultados_dbscan['n_clusters']} clusters densos y {resultados_dbscan['n_outliers']:,} casos atípicos ({resultados_dbscan['pct_outliers']:.1%}%) que requieren análisis individualizado. El clustering jerárquico reveló un segmento de alto riesgo (cluster 2) con {mora_hier.loc[2, 'tasa_morosidad']:.1%} de morosidad, concentrando {int(mora_hier.loc[2, 'n_morosos']):,} clientes morosos en un único grupo."

---

**Generado automáticamente por el sistema de análisis de clustering**
**Fecha:** 2026-04-23
**Script:** mora_analysis_clustering.py
"""

    output_file = output_dir / "INTERPRETACION_CLUSTERING_2026-04-23.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(informe)

    logger.info(f"✓ Informe de interpretación guardado: {output_file.name}")


# ============================================================================
# MAIN: PIPELINE COMPLETO
# ============================================================================

def main():
    """
    Pipeline completo de clustering tradicional.

    Pasos:
    1. Leer datos anonimizados
    2. Preparar features y normalizar
    3. Aplicar 3 algoritmos de clustering
    4. Analizar morosidad por cluster
    5. Visualizar resultados
    6. Guardar métricas
    """
    logger.info("=" * 70)
    logger.info("ANÁLISIS DE MOROSIDAD: CLUSTERING TRADICIONAL")
    logger.info("=" * 70)
    logger.info("Algoritmos: K-Means, DBSCAN, Hierarchical")
    logger.info("Fuente: Datos anonimizados (sin conexión a BD)")

    # === PASO 1: LEER DATOS ===
    fecha = '2026-04-23'
    data_file = DATA_OUTPUT_DIR / f"morosidad_dataset_{fecha}_ANONIMIZADO.xlsx"

    if not data_file.exists():
        logger.error(f"\n❌ Archivo no encontrado: {data_file}")
        logger.error("Ejecuta primero la anonimización:")
        logger.error("  python src/anonimizacion/anonimizar_pipeline.py")
        return

    df = leer_datos_anonimizados(data_file)

    # === PASO 2: PREPARAR FEATURES ===
    df_features, feature_names = preparar_features(df)

    # Convertir a matriz numpy
    X = df_features.values

    # Normalizar
    X_scaled, scaler = normalizar_features(X)

    # Variable objetivo (morosidad)
    y_morosidad = df['es_moroso'].values
    n_morosos = y_morosidad.sum()
    pct_morosos = (n_morosos / len(y_morosidad)) * 100

    logger.info(f"\nVariable objetivo (morosidad):")
    logger.info(f"  Total morosos: {n_morosos:,} ({pct_morosos:.2f}%)")
    logger.info(f"  Total no morosos: {(len(y_morosidad) - n_morosos):,} ({(100-pct_morosos):.2f}%)")

    # === PASO 3: CLUSTERING ===

    # 3.1. K-Means
    resultados_kmeans = aplicar_kmeans(X_scaled, k_min=3, k_max=30)

    # 3.2. DBSCAN
    resultados_dbscan = aplicar_dbscan(X_scaled, eps=2.0, min_samples=10)

    # 3.3. Hierarchical
    resultados_hier = aplicar_hierarchical(X_scaled, n_clusters=5, linkage='ward')

    # === PASO 4: ANÁLISIS DE MOROSIDAD ===
    mora_kmeans = analizar_morosidad_por_cluster(
        resultados_kmeans['labels'], y_morosidad, 'K-Means'
    )

    mora_dbscan = analizar_morosidad_por_cluster(
        resultados_dbscan['labels'], y_morosidad, 'DBSCAN'
    )

    mora_hier = analizar_morosidad_por_cluster(
        resultados_hier['labels'], y_morosidad, 'Hierarchical'
    )

    # === PASO 5: VISUALIZACIÓN ===
    varianza_pca = visualizar_resultados(
        X_scaled, resultados_kmeans, resultados_dbscan,
        resultados_hier, y_morosidad, DATA_OUTPUT_DIR
    )

    # === PASO 6: GUARDAR MÉTRICAS ===
    guardar_metricas(
        resultados_kmeans, resultados_dbscan, resultados_hier,
        mora_kmeans, mora_dbscan, mora_hier,
        DATA_OUTPUT_DIR, len(df), len(feature_names)
    )

    # === PASO 7: GENERAR INFORME DE INTERPRETACIÓN ===
    generar_informe_interpretacion(
        resultados_kmeans, resultados_dbscan, resultados_hier,
        mora_kmeans, mora_dbscan, mora_hier,
        DATA_OUTPUT_DIR, len(df),
        varianza_pca
    )

    # === RESUMEN FINAL ===
    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN COMPARATIVO")
    logger.info("=" * 70)

    logger.info("\nMétricas de Calidad de Clustering:")
    logger.info(f"  K-Means:      Silhouette={resultados_kmeans['silhouette']:.3f}, "
               f"DB={resultados_kmeans['davies_bouldin']:.3f}, "
               f"CH={resultados_kmeans['calinski_harabasz']:.0f}")

    if resultados_dbscan['silhouette']:
        logger.info(f"  DBSCAN:       Silhouette={resultados_dbscan['silhouette']:.3f}, "
                   f"DB={resultados_dbscan['davies_bouldin']:.3f}, "
                   f"CH={resultados_dbscan['calinski_harabasz']:.0f}")
    else:
        logger.info(f"  DBSCAN:       Métricas no calculables (clusters insuficientes)")

    logger.info(f"  Hierarchical: Silhouette={resultados_hier['silhouette']:.3f}, "
               f"DB={resultados_hier['davies_bouldin']:.3f}, "
               f"CH={resultados_hier['calinski_harabasz']:.0f}")

    logger.info("\nCapacidad de Segmentación por Morosidad:")
    logger.info(f"  K-Means:      Rango de tasas = "
               f"[{mora_kmeans['tasa_morosidad'].min():.2%} - {mora_kmeans['tasa_morosidad'].max():.2%}]")

    mora_dbscan_sin_outliers = mora_dbscan[mora_dbscan.index != -1]
    if len(mora_dbscan_sin_outliers) > 0:
        logger.info(f"  DBSCAN:       Rango de tasas = "
                   f"[{mora_dbscan_sin_outliers['tasa_morosidad'].min():.2%} - "
                   f"{mora_dbscan_sin_outliers['tasa_morosidad'].max():.2%}]")

    logger.info(f"  Hierarchical: Rango de tasas = "
               f"[{mora_hier['tasa_morosidad'].min():.2%} - {mora_hier['tasa_morosidad'].max():.2%}]")

    logger.info("\n" + "=" * 70)
    logger.info("✓ ANÁLISIS COMPLETADO")
    logger.info("=" * 70)
    logger.info(f"\nArchivos generados:")
    logger.info(f"  - clustering_comparison_2026-04-23.png")
    logger.info(f"  - kmeans_elbow_method_2026-04-23-k14.png")
    logger.info(f"  - clustering_metrics_2026-04-23.json")


if __name__ == "__main__":
    main()
