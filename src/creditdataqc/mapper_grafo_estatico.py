"""
Genera imagen estática (PNG) del grafo Mapper para incluir en el TFG.

Ejecuta el Mapper sobre los datos anonimizados y dibuja el grafo con
networkx + matplotlib, coloreando cada nodo por su tasa de morosidad.

Produce también:
- mapper_sensibilidad_hiperparametros.xlsx   (análisis de sensibilidad)
- mapper_grafo_sinmora_FECHA.png             (versión sin variables derivadas de mora)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import networkx as nx
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import DBSCAN
import kmapper as km

PROJECT_ROOT = Path(__file__).parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"

# Variables directamente derivadas de mora — excluibles para análisis sin sesgo tautológico
_VARS_MORA = ['n_facturas_morosas', 'proporcion_facturas_morosas', 'dias_mora_maximo']


# ============================================================================
# PREPARACIÓN DE DATOS
# ============================================================================

def _preparar_datos(filepath: Path, excluir_mora: bool = False):
    """
    Lee el Excel anonimizado y devuelve X_scaled, y_morosidad, df.

    Args:
        filepath: Ruta al Excel anonimizado.
        excluir_mora: Si True, elimina n_facturas_morosas, proporcion_facturas_morosas
            y dias_mora_maximo para evitar validación tautológica (el resultado
            de mora no puede predecir mora porque las features ya la codifican).
    """
    df = pd.read_excel(filepath, sheet_name='dataset_morosidad')

    numeric_features = [
        'saldo_pendiente_total', 'n_facturas_totales', 'n_facturas_vencidas',
        'n_facturas_morosas', 'proporcion_facturas_morosas', 'dias_mora_maximo'
    ]
    if excluir_mora:
        numeric_features = [f for f in numeric_features if f not in _VARS_MORA]
    numeric_features = [f for f in numeric_features if f in df.columns]

    df_prep = df.copy()
    if 'fecha_creacion' in df_prep.columns:
        df_prep['fecha_creacion'] = pd.to_datetime(df_prep['fecha_creacion'])
        # Año: no es cíclico, se mantiene como entero
        df_prep['fecha_anio'] = df_prep['fecha_creacion'].dt.year
        # Mes y día del año: variables cíclicas → codificación seno/coseno
        # para que distancia(dic, ene) ≈ distancia(ene, feb) en métricas euclídeas
        mes = df_prep['fecha_creacion'].dt.month
        dia = df_prep['fecha_creacion'].dt.dayofyear
        df_prep['mes_sin'] = np.sin(2 * np.pi * mes / 12)
        df_prep['mes_cos'] = np.cos(2 * np.pi * mes / 12)
        df_prep['dia_sin'] = np.sin(2 * np.pi * dia / 365)
        df_prep['dia_cos'] = np.cos(2 * np.pi * dia / 365)
        temporal_features = ['fecha_anio', 'mes_sin', 'mes_cos', 'dia_sin', 'dia_cos']
    else:
        temporal_features = []

    cat_features = []
    if 'provincia' in df_prep.columns:
        top = df_prep['provincia'].value_counts().head(10).index
        for v in top:
            col = f'prov_{v}'.replace(' ', '_')
            df_prep[col] = (df_prep['provincia'] == v).astype(int)
            cat_features.append(col)
        df_prep['prov_Otras'] = (~df_prep['provincia'].isin(top)).astype(int)
        cat_features.append('prov_Otras')

    if 'cnae' in df_prep.columns:
        top = df_prep['cnae'].value_counts().head(5).index
        for v in top:
            col = f'cnae_{v}'
            df_prep[col] = (df_prep['cnae'] == v).astype(int)
            cat_features.append(col)
        df_prep['cnae_Otros'] = (~df_prep['cnae'].isin(top)).astype(int)
        cat_features.append('cnae_Otros')

    all_features = numeric_features + temporal_features + cat_features
    all_features = [f for f in all_features if f in df_prep.columns]

    X = df_prep[all_features].copy()
    X = X.fillna(X.median(numeric_only=True)).fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X.values)

    y = df['es_moroso'].values
    return X_scaled, y, df


# ============================================================================
# CONSTRUCCIÓN DEL GRAFO MAPPER
# ============================================================================

def _construir_grafo_mapper(X_scaled: np.ndarray,
                             n_cubes: int = 15,
                             perc_overlap: float = 0.3,
                             eps: float = 0.5,
                             min_samples: int = 5,
                             lente: str = 'pca') -> dict:
    """Aplica Mapper y devuelve el grafo."""
    mapper = km.KeplerMapper(verbose=0)

    if lente == 'pca':
        lens = PCA(n_components=2).fit_transform(X_scaled)
    else:
        lens = np.linalg.norm(X_scaled, axis=1).reshape(-1, 1)

    graph = mapper.map(
        lens=lens,
        X=X_scaled,
        cover=km.Cover(n_cubes=n_cubes, perc_overlap=perc_overlap),
        clusterer=DBSCAN(eps=eps, min_samples=min_samples)
    )
    return graph


def _grafo_a_networkx(graph: dict, y_morosidad: np.ndarray) -> nx.Graph:
    G = nx.Graph()
    for node_id, members in graph['nodes'].items():
        tasa = float(y_morosidad[members].mean())
        G.add_node(node_id, tasa=tasa, size=len(members))
    for node_id, vecinos in graph['links'].items():
        for vecino in vecinos:
            if not G.has_edge(node_id, vecino):
                G.add_edge(node_id, vecino)
    return G


def _metricas_estructura(G: nx.Graph) -> dict:
    """Calcula métricas estructurales del grafo NetworkX."""
    componentes = list(nx.connected_components(G))
    n_isolated = sum(1 for n in G.nodes if G.degree(n) == 0)
    sizes = [G.nodes[n]['size'] for n in G.nodes]
    tasas = [G.nodes[n]['tasa'] for n in G.nodes]
    comp_principal = len(max(componentes, key=len)) if componentes else 0
    return {
        'n_nodos': G.number_of_nodes(),
        'n_aristas': G.number_of_edges(),
        'n_componentes': len(componentes),
        'n_aislados': n_isolated,
        'pct_aislados': n_isolated / max(G.number_of_nodes(), 1),
        'comp_principal': comp_principal,
        'tam_medio': float(np.mean(sizes)),
        'n_mora_50': sum(1 for t in tasas if t > 0.5),
        'n_mora_80': sum(1 for t in tasas if t > 0.8),
        'densidad': nx.density(G),
    }


# ============================================================================
# DIBUJO DEL GRAFO
# ============================================================================

def dibujar_grafo(G: nx.Graph, output_path: Path, subtitulo: str = ''):
    """
    Dibuja el grafo Mapper con:
    - Nodos coloreados por tasa de morosidad (verde → naranja → rojo)
    - Tamaño de nodo proporcional a número de clientes
    - Anillo visual que separa nodos aislados del núcleo conectado
    - Recuadro de métricas estructurales
    - Nota metodológica crítica al pie
    """
    m = _metricas_estructura(G)
    print(f"  Nodos: {m['n_nodos']}, Aristas: {m['n_aristas']}, "
          f"Componentes: {m['n_componentes']}, Aislados: {m['n_aislados']}")

    # ── Layout ──────────────────────────────────────────────────────────────
    connected_nodes = [n for n in G.nodes if G.degree(n) > 0]
    isolated = [n for n in G.nodes if G.degree(n) == 0]

    subgraph = G.subgraph(connected_nodes)
    pos_connected = nx.spring_layout(subgraph, seed=42, k=0.6, iterations=80) if connected_nodes else {}

    rng = np.random.default_rng(0)
    angles = np.linspace(0, 2 * np.pi, max(len(isolated), 1), endpoint=False)
    radius = 3.2
    pos_isolated = {n: (radius * np.cos(a) + rng.uniform(-0.08, 0.08),
                        radius * np.sin(a) + rng.uniform(-0.08, 0.08))
                    for n, a in zip(isolated, angles)}
    pos = {**pos_connected, **pos_isolated}

    sizes_raw = [G.nodes[n]['size'] for n in G.nodes]
    min_s, max_s = min(sizes_raw), max(sizes_raw)

    def _escalar_size(s):
        return 18 + 200 * (s - min_s) / max(max_s - min_s, 1)

    cmap = mcolors.LinearSegmentedColormap.from_list(
        'morosidad', ['#27ae60', '#f39c12', '#c0392b']
    )

    # ── Figura ──────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(15, 11))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f9fa')

    # Anillo de referencia para nodos aislados
    if isolated:
        anillo = plt.Circle((0, 0), radius, fill=False, linestyle='--',
                             color='#cccccc', linewidth=0.8, alpha=0.6)
        ax.add_patch(anillo)
        ax.text(0, radius + 0.18, 'Nodos aislados (sin aristas)',
                ha='center', va='bottom', fontsize=7.5, color='#999999', style='italic')

    # Aristas
    edges = list(G.edges())
    if edges:
        edge_tasas = [(G.nodes[u]['tasa'] + G.nodes[v]['tasa']) / 2 for u, v in edges]
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=edges,
                               edge_color=[cmap(t) for t in edge_tasas],
                               alpha=0.50, width=1.0)

    # Nodos aislados (borde gris claro)
    if isolated:
        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=isolated,
                               node_size=[_escalar_size(G.nodes[n]['size']) for n in isolated],
                               node_color=[G.nodes[n]['tasa'] for n in isolated],
                               cmap=cmap, vmin=0, vmax=1,
                               alpha=0.65, linewidths=0.6, edgecolors='#aaaaaa')

    # Nodos conectados (borde oscuro)
    if connected_nodes:
        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=connected_nodes,
                               node_size=[_escalar_size(G.nodes[n]['size']) for n in connected_nodes],
                               node_color=[G.nodes[n]['tasa'] for n in connected_nodes],
                               cmap=cmap, vmin=0, vmax=1,
                               alpha=0.90, linewidths=0.5, edgecolors='#444444')

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.50, pad=0.02)
    cbar.set_label('Tasa de morosidad por nodo', fontsize=11)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_ticklabels(['0 %', '25 %', '50 %', '75 %', '100 %'])

    # Título
    titulo = 'Grafo Mapper — Análisis Topológico de Morosidad'
    if subtitulo:
        titulo += f'\n{subtitulo}'
    ax.set_title(titulo, fontsize=13, pad=14, color='#222222')
    ax.axis('off')

    # Leyenda de tamaño
    for label, s in [('1 cliente', 18), ('50 clientes', 118), ('≥ 100 clientes', 218)]:
        ax.scatter([], [], s=s, color='#aaaaaa', alpha=0.85, label=label,
                   edgecolors='#555555', linewidths=0.5)
    ax.legend(scatterpoints=1, frameon=True, labelspacing=1.1,
              title='Tamaño del nodo', title_fontsize=9,
              fontsize=9, loc='lower left',
              facecolor='white', edgecolor='#cccccc', fancybox=True)

    # Recuadro de métricas estructurales
    stats_text = (
        f"Métricas del grafo\n"
        f"{'─'*22}\n"
        f"Nodos:            {m['n_nodos']}\n"
        f"Aristas:          {m['n_aristas']}\n"
        f"Comp. conexas:    {m['n_componentes']}\n"
        f"Nodos aislados:   {m['n_aislados']} ({m['pct_aislados']:.0%})\n"
        f"Comp. principal:  {m['comp_principal']} nodos\n"
        f"Tam. medio nodo:  {m['tam_medio']:.1f} clientes\n"
        f"Nodos mora >50 %: {m['n_mora_50']}\n"
        f"Nodos mora >80 %: {m['n_mora_80']}"
    )
    ax.text(0.01, 0.99, stats_text,
            transform=ax.transAxes, fontsize=8.5, verticalalignment='top',
            fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='#cccccc', alpha=0.92))

    # Nota metodológica inferior
    ax.text(
        0.5, -0.01,
        'El grafo muestra alta fragmentación. La morosidad alta (rojo) aparece dispersa y no forma '
        'un supercluster conectado,\nlo que indica que esta parametrización no detecta un segmento '
        'de riesgo topológicamente separado con esta configuración.',
        transform=ax.transAxes, fontsize=8, color='#555555',
        ha='center', va='top', style='italic'
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Guardado: {output_path.name}")
    return m


# ============================================================================
# ANÁLISIS DE SENSIBILIDAD DE HIPERPARÁMETROS
# ============================================================================

def analizar_sensibilidad(X_scaled: np.ndarray, y_morosidad: np.ndarray,
                           output_dir: Path) -> pd.DataFrame:
    """
    Ejecuta Mapper con 5 configuraciones distintas.

    Genera:
    - mapper_sensibilidad_hiperparametros.png  (imagen de tabla para el TFG)
    - mapper_sensibilidad_hiperparametros.xlsx (datos en bruto)
    """
    configuraciones = [
        {
            'cfg': 'A', 'label': 'Original (referencia)',
            'n_cubes': 15, 'perc_overlap': 0.30, 'eps': 0.5, 'min_samples': 5, 'lente': 'PCA',
        },
        {
            'cfg': 'B', 'label': 'Menos cubos + más solapamiento',
            'n_cubes': 8,  'perc_overlap': 0.50, 'eps': 0.5, 'min_samples': 3, 'lente': 'PCA',
        },
        {
            'cfg': 'C', 'label': 'Solapamiento alto',
            'n_cubes': 10, 'perc_overlap': 0.60, 'eps': 0.5, 'min_samples': 3, 'lente': 'PCA',
        },
        {
            'cfg': 'D', 'label': 'DBSCAN permisivo (ε mayor)',
            'n_cubes': 10, 'perc_overlap': 0.50, 'eps': 1.0, 'min_samples': 3, 'lente': 'PCA',
        },
        {
            'cfg': 'E', 'label': 'Lente norma L2',
            'n_cubes': 10, 'perc_overlap': 0.50, 'eps': 0.5, 'min_samples': 3, 'lente': 'L2',
        },
    ]

    filas = []
    for cfg in configuraciones:
        print(f"  Ejecutando configuración {cfg['cfg']}...")
        try:
            graph = _construir_grafo_mapper(
                X_scaled,
                n_cubes=cfg['n_cubes'],
                perc_overlap=cfg['perc_overlap'],
                eps=cfg['eps'],
                min_samples=cfg['min_samples'],
                lente='l2norm' if cfg['lente'] == 'L2' else 'pca'
            )
            G = _grafo_a_networkx(graph, y_morosidad)
            m = _metricas_estructura(G)
            filas.append({
                'cfg': cfg['cfg'],
                'label': cfg['label'],
                'n_cubes': cfg['n_cubes'],
                'perc_overlap': cfg['perc_overlap'],
                'eps': cfg['eps'],
                'min_samples': cfg['min_samples'],
                'lente': cfg['lente'],
                'n_nodos': m['n_nodos'],
                'n_aristas': m['n_aristas'],
                'n_componentes': m['n_componentes'],
                'n_aislados': m['n_aislados'],
                'pct_aislados': m['pct_aislados'],
                'comp_principal': m['comp_principal'],
                'tam_medio': round(m['tam_medio'], 1),
                'n_mora_50': m['n_mora_50'],
            })
        except Exception as e:
            print(f"    Error: {e}")

    df = pd.DataFrame(filas)

    # ── Guardar Excel ────────────────────────────────────────────────────
    out_xlsx = output_dir / 'mapper_sensibilidad_hiperparametros.xlsx'
    df.to_excel(out_xlsx, index=False)

    # ── Generar imagen visual de la tabla ────────────────────────────────
    out_png = output_dir / 'mapper_sensibilidad_hiperparametros.png'
    _dibujar_tabla_sensibilidad(df, out_png)

    print(f"  Tabla guardada: {out_png.name}")
    return df


def _dibujar_tabla_sensibilidad(df: pd.DataFrame, output_path: Path):
    """Genera una imagen PNG con la tabla de sensibilidad de hiperparámetros."""

    # Columnas de parámetros y columnas de resultados
    col_params  = ['n_cubes', 'perc_overlap', 'eps', 'min_samples', 'lente']
    col_results = ['n_nodos', 'n_aristas', 'n_componentes', 'n_aislados',
                   'comp_principal', 'tam_medio', 'n_mora_50']

    # Cabeceras legibles
    headers = {
        'n_cubes':        'Cubos',
        'perc_overlap':   'Overlap',
        'eps':            'ε',
        'min_samples':    'min_s',
        'lente':          'Lente',
        'n_nodos':        'Nodos',
        'n_aristas':      'Aristas',
        'n_componentes':  'Comp.\nconexas',
        'n_aislados':     'Nodos\naislados',
        'comp_principal': 'Comp.\nprincipal',
        'tam_medio':      'Tam.\nmedio',
        'n_mora_50':      'Mora\n>50 %',
    }

    all_cols = col_params + col_results
    n_rows = len(df)
    n_cols = 1 + len(all_cols)  # +1 para la columna de cfg/label

    fig_w = 1.2 + n_cols * 1.05
    fig_h = 1.5 + n_rows * 0.62

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    ax.axis('off')

    # Título
    fig.text(0.5, 0.97,
             'Análisis de Sensibilidad de Hiperparámetros — Mapper',
             ha='center', va='top', fontsize=13, fontweight='bold', color='#1a1a2e')
    fig.text(0.5, 0.92,
             'Efecto de distintas configuraciones sobre la estructura del grafo',
             ha='center', va='top', fontsize=9, color='#555555', style='italic')

    # ── Construir datos de celda ─────────────────────────────────────────
    col_labels = ['Configuración'] + [headers[c] for c in all_cols]

    cell_data = []
    for _, row in df.iterrows():
        fila = [f"{row['cfg']}  {row['label']}"]
        for c in col_params:
            fila.append(str(row[c]))
        for c in col_results:
            if c == 'pct_aislados':
                fila.append(f"{row[c]:.0%}")
            elif c == 'tam_medio':
                fila.append(f"{row[c]:.1f}")
            else:
                fila.append(str(int(row[c])))
        cell_data.append(fila)

    # ── Dibujar tabla ────────────────────────────────────────────────────
    tbl = ax.table(
        cellText=cell_data,
        colLabels=col_labels,
        cellLoc='center',
        loc='center',
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.8)

    # Colores base
    COLOR_HEADER      = '#1a1a2e'
    COLOR_HEADER_TXT  = 'white'
    COLOR_ROW_ODD     = '#f0f4ff'
    COLOR_ROW_EVEN    = 'white'
    COLOR_SEP         = '#c8d0e8'   # línea entre parámetros y resultados
    COLOR_REF_BG      = '#fff9e6'   # fondo fila de referencia (cfg A)

    n_param_cols = len(col_params) + 1  # +1 columna cfg/label

    for (row_i, col_i), cell in tbl.get_celld().items():
        cell.set_edgecolor('#dddddd')
        cell.set_linewidth(0.5)

        if row_i == 0:
            # Cabecera
            cell.set_facecolor(COLOR_HEADER)
            cell.set_text_props(color=COLOR_HEADER_TXT, fontweight='bold', fontsize=8.5)
            # Separador visual entre parámetros y resultados
            if col_i == n_param_cols:
                cell.set_edgecolor(COLOR_SEP)
                cell.set_linewidth(2.5)
        else:
            # Fondo alternado; fila referencia en amarillo suave
            if row_i == 1:
                bg = COLOR_REF_BG
            else:
                bg = COLOR_ROW_ODD if row_i % 2 == 1 else COLOR_ROW_EVEN
            cell.set_facecolor(bg)

            # Columna cfg/label en negrita
            if col_i == 0:
                cell.set_text_props(fontweight='bold', fontsize=8.5)

            # Separador entre bloque parámetros y resultados
            if col_i == n_param_cols:
                cell.set_edgecolor(COLOR_SEP)
                cell.set_linewidth(2.5)

            # Resaltar valores altos de nodos aislados en rojo suave
            col_name = all_cols[col_i - 1] if col_i >= 1 else None
            if col_name == 'n_aislados':
                val = df.iloc[row_i - 1]['n_aislados']
                total = df.iloc[row_i - 1]['n_nodos']
                if total > 0 and val / total > 0.4:
                    cell.set_facecolor('#ffe0e0')

    # Ajustar ancho columna de configuración (más ancha)
    tbl.auto_set_column_width(col=0)

    # Notas al pie
    notas = (
        'Overlap = solapamiento entre hipercubos del recubrimiento. '
        'ε = radio DBSCAN. min_s = mínimo de puntos por clúster.\n'
        'Comp. conexas = subgrafos desconectados. '
        'Comp. principal = tamaño (nodos) del mayor subgrafo conectado. '
        'Mora >50 % = nodos con tasa de morosidad superior al 50 %.\n'
        'Fila sombreada = configuración de referencia usada en el análisis principal. '
        'Celdas en rojo = más del 40 % de nodos aislados.'
    )
    fig.text(0.5, 0.01, notas, ha='center', va='bottom',
             fontsize=7.5, color='#666666', style='italic',
             wrap=True)

    plt.savefig(output_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()


# ============================================================================
# MAIN
# ============================================================================

def main():
    fecha = '2026-04-23'
    data_file = DATA_OUTPUT_DIR / f"morosidad_dataset_{fecha}_ANONIMIZADO.xlsx"

    if not data_file.exists():
        print(f"ERROR: Archivo no encontrado: {data_file}")
        print("Ejecuta primero: python src/anonimizacion/anonimizar_pipeline.py")
        return

    # ── 1. Grafo principal (CON variables de mora) ───────────────────────
    print("\n[1/3] Grafo principal (con variables de mora)...")
    X_scaled, y_morosidad, _ = _preparar_datos(data_file, excluir_mora=False)
    graph = _construir_grafo_mapper(X_scaled)
    G = _grafo_a_networkx(graph, y_morosidad)

    subtitulo_principal = (
        'PCA (2D) · DBSCAN (ε=0.5, min=5) · Cubrimiento: 15 cubos, solapamiento 30 %\n'
        'Variables: todas (incluidas derivadas de mora)'
    )
    out_principal = DATA_OUTPUT_DIR / f"mapper_grafo_estatico_{fecha}.png"
    dibujar_grafo(G, out_principal, subtitulo=subtitulo_principal)

    # ── 2. Grafo sin variables de mora (control metodológico) ────────────
    print("\n[2/3] Grafo sin variables de mora (control metodológico)...")
    X_sinmora, _, _ = _preparar_datos(data_file, excluir_mora=True)
    graph_sinmora = _construir_grafo_mapper(X_sinmora)
    G_sinmora = _grafo_a_networkx(graph_sinmora, y_morosidad)

    subtitulo_sinmora = (
        'PCA (2D) · DBSCAN (ε=0.5, min=5) · Cubrimiento: 15 cubos, solapamiento 30 %\n'
        'Variables: sin n_facturas_morosas, proporcion_facturas_morosas, dias_mora_maximo'
    )
    out_sinmora = DATA_OUTPUT_DIR / f"mapper_grafo_sinmora_{fecha}.png"
    dibujar_grafo(G_sinmora, out_sinmora, subtitulo=subtitulo_sinmora)

    # ── 3. Análisis de sensibilidad de hiperparámetros ───────────────────
    print("\n[3/3] Análisis de sensibilidad de hiperparámetros...")
    analizar_sensibilidad(X_scaled, y_morosidad, DATA_OUTPUT_DIR)

    print("\nArchivos generados:")
    print(f"  - {out_principal.name}")
    print(f"  - {out_sinmora.name}")
    print("  - mapper_sensibilidad_hiperparametros.png  ← imagen para el TFG")
    print("  - mapper_sensibilidad_hiperparametros.xlsx ← datos en bruto")


if __name__ == "__main__":
    main()
