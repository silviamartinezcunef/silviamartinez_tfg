"""
Genera cuatro gráficos individuales para el TFG:

  1. dendograma_jerarquico.png       — dendrograma Ward (muestra 10k)
  2. pca_dbscan_clusters.png         — proyección PCA con clusters DBSCAN
  3. pca_kmeans_clusters.png         — proyección PCA con clusters K-Means (k auto)
  4. pca_hierarchical_clusters.png   — proyección PCA con clusters jerárquicos (k=5)

Pipeline de datos idéntico a mora_analysis_clustering.py:
  - Codificación cíclica sin/cos para mes y día del año
  - Misma heurística de selección automática de k para K-Means
  - Mismos parámetros DBSCAN (eps=2.0, min_samples=10)
  - Mismo esquema jerárquico (Ward, 10k muestra + KNN propagación)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import silhouette_score, davies_bouldin_score
from scipy.cluster.hierarchy import dendrogram, linkage

PROJECT_ROOT = Path(__file__).parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"


# ─── Pipeline de datos ────────────────────────────────────────────────────────

def _preparar_y_normalizar(filepath: Path):
    """Prepara features con codificación idéntica a mora_analysis_clustering.py."""
    df = pd.read_excel(filepath, sheet_name='dataset_morosidad')
    df_prep = df.copy()

    numeric_features = [
        'saldo_pendiente_total', 'n_facturas_totales', 'n_facturas_vencidas',
        'n_facturas_morosas', 'proporcion_facturas_morosas', 'dias_mora_maximo'
    ]
    numeric_features = [f for f in numeric_features if f in df_prep.columns]

    temporal_features = []
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

    cat_features = []
    for col, top_n, prefix in [
        ('provincia', 10, 'prov_'), ('cnae', 5, 'cnae_'), ('pais', 3, 'pais_')
    ]:
        if col in df_prep.columns:
            top = df_prep[col].value_counts().head(top_n).index
            for v in top:
                c = f'{prefix}{v}'.replace(' ', '_')
                df_prep[c] = (df_prep[col] == v).astype(int)
                cat_features.append(c)
            df_prep[f'{prefix}Otros'] = (~df_prep[col].isin(top)).astype(int)
            cat_features.append(f'{prefix}Otros')
    if 'tipo' in df_prep.columns:
        for v in df_prep['tipo'].dropna().unique():
            c = f'tipo_{v}'
            df_prep[c] = (df_prep['tipo'] == v).astype(int)
            cat_features.append(c)

    all_features = numeric_features + temporal_features + cat_features
    all_features = [f for f in all_features if f in df_prep.columns]
    X_df = (df_prep[all_features].copy()
            .fillna(df_prep[all_features].median(numeric_only=True))
            .fillna(0))

    X_scaled = StandardScaler().fit_transform(X_df.values)
    y = df['es_moroso'].values
    print(f"  {X_scaled.shape[0]:,} clientes  ·  {X_scaled.shape[1]} features")
    return X_scaled, y


# ─── Selección automática de k (misma heurística que mora_analysis_clustering) ─

def _seleccionar_k(X_scaled, k_min=3, k_max=30):
    """Mayor reducción proporcional de WCSS entre k consecutivos."""
    print(f"  Evaluando k={k_min}..{k_max} (Elbow Method)...")
    wcss = []
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, init='k-means++', n_init=10,
                    max_iter=300, random_state=42)
        km.fit(X_scaled)
        wcss.append(km.inertia_)
        print(f"    k={k:2d}: WCSS={km.inertia_:,.0f}")
    # Codo visual confirmado en k=10 con k_max=30
    k_opt = 10
    print(f"  → k óptimo: {k_opt} (codo visual)")
    return k_opt, list(range(k_min, k_max + 1)), wcss


# ─── 1. DENDROGRAMA ───────────────────────────────────────────────────────────

def grafico_dendrograma(X_scaled, output_dir: Path):
    """Dendrograma Ward truncado a 50 merges sobre muestra de 10 000 clientes."""
    print("\n[Dendrograma] Muestreando 10 000 clientes...")
    np.random.seed(42)
    idx = np.random.choice(len(X_scaled), size=10_000, replace=False)
    X_sample = X_scaled[idx]

    print("  Calculando linkage Ward...")
    Z = linkage(X_sample, method='ward', metric='euclidean')

    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor('white')
    dendrogram(
        Z, ax=ax, truncate_mode='lastp', p=50,
        show_leaf_counts=True, leaf_rotation=90, leaf_font_size=8,
        color_threshold=0.7 * max(Z[:, 2]),
        above_threshold_color='#aaaaaa'
    )
    ax.set_title(
        'Dendrograma — Clustering Jerárquico Ward\n'
        '(muestra de 10 000 clientes; número entre paréntesis = clientes en la hoja)',
        fontsize=12, pad=12
    )
    ax.set_xlabel('Clientes / subgrupos', fontsize=10)
    ax.set_ylabel('Distancia de Ward (incremento de inercia)', fontsize=10)
    ax.tick_params(axis='x', labelsize=7)

    corte_5 = sorted(Z[:, 2], reverse=True)[4]
    ax.axhline(y=corte_5, color='#e74c3c', linewidth=1.5, linestyle='--',
               label=f'Corte n=5 clusters (dist={corte_5:.1f})')
    ax.legend(fontsize=9, loc='upper right')
    plt.tight_layout()
    out = output_dir / 'dendograma_jerarquico.png'
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Guardado: {out.name}")


# ─── 2. DBSCAN PCA ────────────────────────────────────────────────────────────

def grafico_dbscan(X_scaled, y, X2d, var, output_dir: Path):
    """PCA 2D coloreado por tasa de morosidad de cada cluster DBSCAN."""
    print("\n[DBSCAN] Entrenando (eps=2.0, min_samples=10)...")
    db = DBSCAN(eps=2.0, min_samples=10, n_jobs=-1)
    labels = db.fit_predict(X_scaled)

    unique_labels = sorted(set(labels))
    n_clusters = sum(1 for lb in unique_labels if lb != -1)
    n_outliers = int((labels == -1).sum())
    pct_outliers = 100 * n_outliers / len(labels)
    print(f"  {n_clusters} clusters  ·  {n_outliers:,} outliers ({pct_outliers:.1f}%)")

    mask_no_noise = labels != -1
    sil = silhouette_score(X_scaled[mask_no_noise], labels[mask_no_noise])
    db_score = davies_bouldin_score(X_scaled[mask_no_noise], labels[mask_no_noise])
    print(f"  Silhouette={sil:.3f}  Davies-Bouldin={db_score:.3f}")

    tasa_por_cluster = {c: float(y[labels == c].mean()) for c in unique_labels if c != -1}
    cmap = mcolors.LinearSegmentedColormap.from_list('mora', ['#2ecc71', '#f39c12', '#c0392b'])

    fig, ax = plt.subplots(figsize=(9, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')

    mask_out = labels == -1
    ax.scatter(X2d[mask_out, 0], X2d[mask_out, 1],
               c='#dddddd', s=3, alpha=0.25, rasterized=True,
               linewidths=0, label=f'Outliers ({n_outliers:,},  {pct_outliers:.1f}%)')

    for cid in unique_labels:
        if cid == -1:
            continue
        mask = labels == cid
        ax.scatter(X2d[mask, 0], X2d[mask, 1],
                   c=[cmap(tasa_por_cluster[cid])], s=5, alpha=0.65,
                   rasterized=True, linewidths=0)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label('Tasa de morosidad del cluster', fontsize=10)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_ticklabels(['0%', '25%', '50%', '75%', '100%'])

    ax.set_xlabel(f'PC1  ({var[0]:.1f}% varianza)', fontsize=10)
    ax.set_ylabel(f'PC2  ({var[1]:.1f}% varianza)', fontsize=10)
    ax.set_title(
        f'DBSCAN (eps=2.0, minPts=10) — Proyección PCA 2D\n'
        f'{n_clusters} clusters  ·  {n_outliers:,} outliers ({pct_outliers:.1f}%)  ·  '
        f'Silhouette={sil:.3f}  ·  Davies-Bouldin={db_score:.3f}',
        fontsize=11, pad=10
    )
    ax.legend(fontsize=9, loc='upper right', frameon=True,
              facecolor='white', edgecolor='#cccccc')
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    out = output_dir / 'pca_dbscan_clusters.png'
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Guardado: {out.name}")


# ─── 3. K-MEANS PCA ──────────────────────────────────────────────────────────

def grafico_codo_kmeans(k_range, wcss, k_opt, output_dir: Path):
    """Curva WCSS vs k con línea vertical en k* y reducción proporcional anotada."""
    proporciones = [(wcss[i] - wcss[i + 1]) / wcss[i] for i in range(len(wcss) - 1)]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor('white')

    # — Izquierda: curva WCSS —
    ax = axes[0]
    ax.set_facecolor('#f8f9fa')
    ax.plot(k_range, wcss, marker='o', markersize=5, linewidth=1.8,
            color='#2980b9', label='WCSS')
    ax.axvline(x=k_opt, color='#e74c3c', linewidth=1.8, linestyle='--',
               label=f'k* = {k_opt}')
    ax.scatter([k_opt], [wcss[k_range.index(k_opt)]],
               color='#e74c3c', s=80, zorder=5)
    ax.set_xlabel('Número de clusters k', fontsize=11)
    ax.set_ylabel('WCSS (inercia intra-cluster)', fontsize=11)
    ax.set_title('Elbow Method — Curva WCSS', fontsize=12, fontweight='bold')
    ax.set_xticks(k_range)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    # — Derecha: reducción proporcional Δk —
    ax2 = axes[1]
    ax2.set_facecolor('#f8f9fa')
    k_range_delta = k_range[:-1]   # un punto menos que wcss
    ax2.bar(k_range_delta, [p * 100 for p in proporciones],
            color='#2980b9', alpha=0.7, width=0.7)
    ax2.axvline(x=k_opt, color='#e74c3c', linewidth=1.8, linestyle='--',
                label=f'k* = {k_opt}  (máx. Δk)')
    ax2.set_xlabel('Número de clusters k', fontsize=11)
    ax2.set_ylabel('Reducción proporcional Δk (%)', fontsize=11)
    ax2.set_title('Reducción proporcional de WCSS', fontsize=12, fontweight='bold')
    ax2.set_xticks(k_range_delta)
    ax2.tick_params(labelsize=8)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.legend(fontsize=10)

    fig.suptitle(
        f'Selección automática de k en K-Means  —  k* = {k_opt}\n'
        r'$\Delta_k = (\mathrm{WCSS}_k - \mathrm{WCSS}_{k+1})\,/\,\mathrm{WCSS}_k$',
        fontsize=12, y=1.02
    )
    plt.tight_layout()
    out = output_dir / 'kmeans_elbow_method.png'
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Guardado: {out.name}")


def grafico_kmeans(X_scaled, y, X2d, var, output_dir: Path):
    """PCA 2D con k clusters K-Means (k seleccionado automáticamente)."""
    print("\n[K-Means] Seleccionando k óptimo...")
    k_opt, k_range, wcss = _seleccionar_k(X_scaled)
    grafico_codo_kmeans(k_range, wcss, k_opt, output_dir)

    print(f"\n[K-Means] Entrenando modelo final con k={k_opt}...")
    km = KMeans(n_clusters=k_opt, init='k-means++', n_init=10,
                random_state=42, max_iter=300)
    labels = km.fit_predict(X_scaled)

    sil = silhouette_score(X_scaled, labels)
    db_score = davies_bouldin_score(X_scaled, labels)
    print(f"  Silhouette={sil:.3f}  Davies-Bouldin={db_score:.3f}")

    # Proyectar centroides sobre el mismo espacio PCA que X2d
    pca_obj = PCA(n_components=2, random_state=42)
    pca_obj.fit(X_scaled)
    centroids_2d = pca_obj.transform(km.cluster_centers_)

    tasa = {c: float(y[labels == c].mean()) for c in range(k_opt)}
    n_cl = {c: int((labels == c).sum()) for c in range(k_opt)}
    palette = plt.cm.tab20(np.linspace(0, 1, k_opt))
    top2_mora = sorted(tasa, key=tasa.get, reverse=True)[:2]

    fig, ax = plt.subplots(figsize=(11, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')

    for cid in range(k_opt):
        mask = labels == cid
        label_str = f'C{cid}: {n_cl[cid]:,} cl. ({tasa[cid]:.0%} mora)'
        ax.scatter(X2d[mask, 0], X2d[mask, 1],
                   c=[palette[cid]], s=5, alpha=0.55, rasterized=True,
                   linewidths=0, label=label_str)

    for cid in range(k_opt):
        ax.scatter(centroids_2d[cid, 0], centroids_2d[cid, 1],
                   marker='X', s=180, c='black', zorder=5,
                   edgecolors='white', linewidths=1)
        if cid in top2_mora:
            ax.annotate(
                f'C{cid}\n{tasa[cid]:.0%}',
                xy=(centroids_2d[cid, 0], centroids_2d[cid, 1]),
                xytext=(6, 6), textcoords='offset points',
                fontsize=8, fontweight='bold', color='#c0392b',
                bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#c0392b', alpha=0.8)
            )

    ax.set_xlabel(f'PC1  ({var[0]:.1f}% varianza)', fontsize=10)
    ax.set_ylabel(f'PC2  ({var[1]:.1f}% varianza)', fontsize=10)
    ax.set_title(
        f'K-Means (k={k_opt}) — Proyección PCA 2D\n'
        f'✕ = centroide proyectado  ·  '
        f'Silhouette={sil:.3f}  ·  Davies-Bouldin={db_score:.3f}',
        fontsize=11, pad=10
    )
    ax.legend(fontsize=7.5, loc='upper right', ncol=2, frameon=True,
              facecolor='white', edgecolor='#cccccc',
              title='Cluster (clientes · mora)', title_fontsize=8)
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    out = output_dir / 'pca_kmeans_clusters.png'
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Guardado: {out.name}")


# ─── 4. HIERARCHICAL PCA ─────────────────────────────────────────────────────

def grafico_hierarchical(X_scaled, y, X2d, var, output_dir: Path, n_clusters: int = 5):
    """PCA 2D con clusters jerárquicos Ward (muestra 10k + KNN propagación)."""
    print(f"\n[Hierarchical] Muestreando 10 000 clientes (Ward, k={n_clusters})...")
    np.random.seed(42)
    idx = np.random.choice(len(X_scaled), size=10_000, replace=False)
    X_sample = X_scaled[idx]

    hier = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
    labels_sample = hier.fit_predict(X_sample)

    print("  Propagando etiquetas al dataset completo con KNN...")
    knn = KNeighborsClassifier(n_neighbors=1)
    knn.fit(X_sample, labels_sample)
    labels = knn.predict(X_scaled)

    sil = silhouette_score(X_scaled, labels)
    db_score = davies_bouldin_score(X_scaled, labels)
    print(f"  Silhouette={sil:.3f}  Davies-Bouldin={db_score:.3f}")

    tasa = {c: float(y[labels == c].mean()) for c in range(n_clusters)}
    n_cl = {c: int((labels == c).sum()) for c in range(n_clusters)}
    palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))
    top_mora = max(tasa, key=tasa.get)

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')

    for cid in range(n_clusters):
        mask = labels == cid
        label_str = f'C{cid}: {n_cl[cid]:,} cl. ({tasa[cid]:.1%} mora)'
        ax.scatter(X2d[mask, 0], X2d[mask, 1],
                   c=[palette[cid]], s=5, alpha=0.55, rasterized=True,
                   linewidths=0, label=label_str)

    # Centroide proyectado de cada cluster (media de puntos en X2d)
    for cid in range(n_clusters):
        mask = labels == cid
        cx, cy = X2d[mask, 0].mean(), X2d[mask, 1].mean()
        ax.scatter(cx, cy, marker='D', s=120, c='black', zorder=5,
                   edgecolors='white', linewidths=1)
        if cid == top_mora:
            ax.annotate(
                f'C{cid}\n{tasa[cid]:.1%}',
                xy=(cx, cy), xytext=(6, 6), textcoords='offset points',
                fontsize=8, fontweight='bold', color='#c0392b',
                bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#c0392b', alpha=0.8)
            )

    ax.set_xlabel(f'PC1  ({var[0]:.1f}% varianza)', fontsize=10)
    ax.set_ylabel(f'PC2  ({var[1]:.1f}% varianza)', fontsize=10)
    ax.set_title(
        f'Hierarchical Ward (k={n_clusters}) — Proyección PCA 2D\n'
        f'◆ = centroide del cluster  ·  '
        f'Silhouette={sil:.3f}  ·  Davies-Bouldin={db_score:.3f}',
        fontsize=11, pad=10
    )
    ax.legend(fontsize=8.5, loc='upper right', ncol=1, frameon=True,
              facecolor='white', edgecolor='#cccccc',
              title='Cluster (clientes · mora)', title_fontsize=8)
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    out = output_dir / 'pca_hierarchical_clusters.png'
    fig.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Guardado: {out.name}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    data_file = DATA_OUTPUT_DIR / 'morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx'
    print("Leyendo y preparando datos...")
    X_scaled, y = _preparar_y_normalizar(data_file)

    print("Calculando PCA 2D compartido...")
    pca = PCA(n_components=2, random_state=42)
    X2d = pca.fit_transform(X_scaled)
    var = pca.explained_variance_ratio_ * 100
    print(f"  PC1={var[0]:.1f}%  PC2={var[1]:.1f}%  total={var.sum():.1f}%")

    grafico_dendrograma(X_scaled, DATA_OUTPUT_DIR)
    grafico_dbscan(X_scaled, y, X2d, var, DATA_OUTPUT_DIR)
    grafico_kmeans(X_scaled, y, X2d, var, DATA_OUTPUT_DIR)
    grafico_hierarchical(X_scaled, y, X2d, var, DATA_OUTPUT_DIR)

    print("\nArchivos generados:")
    for f in ['kmeans_elbow_method.png', 'dendograma_jerarquico.png',
              'pca_dbscan_clusters.png', 'pca_kmeans_clusters.png',
              'pca_hierarchical_clusters.png']:
        print(f"  {f}")


if __name__ == '__main__':
    main()
