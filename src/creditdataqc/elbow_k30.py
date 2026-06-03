"""Generador rápido de Elbow plot hasta k=30.

Usar cuando solo se quiere visualizar el codo sin ejecutar todo el pipeline.

Ejemplo:
  python src/creditdataqc/elbow_k30.py 
  python src/creditdataqc/elbow_k30.py --input output/morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx --kmax 30

El script lee el fichero de datos anonimizado, toma columnas numéricas (excluye identificadores),
normaliza con StandardScaler y calcula WCSS para k en [2, kmax]. Guarda el gráfico en `output`.
"""
from pathlib import Path
import argparse
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set(style="whitegrid")
except ImportError:
    raise SystemExit("matplotlib/seaborn no están instalados. Ejecuta: pip install matplotlib seaborn")


PROJECT_ROOT = Path(__file__).parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "output" / "morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


def main():
    p = argparse.ArgumentParser(description="Generar Elbow plot (KMeans) hasta kmax")
    p.add_argument("--input", "-i", default=str(DEFAULT_INPUT), help="Fichero de entrada (xlsx/csv)")
    p.add_argument("--output-dir", "-o", default=str(DEFAULT_OUTPUT_DIR), help="Directorio de salida")
    p.add_argument("--kmax", type=int, default=30, help="k máximo a evaluar (>=3)")
    p.add_argument("--mark-k", type=int, default=10, help="Marcar verticalmente un k específico en la gráfica (por defecto 10)")
    args = p.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    kmax = args.kmax
    mark_k = args.mark_k

    if not input_path.exists():
        raise SystemExit(f"Fichero no encontrado: {input_path}")

    if kmax < 3:
        raise SystemExit("kmax debe ser >= 3")

    # Cargar datos
    if input_path.suffix.lower() in ('.xls', '.xlsx'):
        df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    # Excluir columnas no numéricas e identificadores conocidos
    exclude = {"cif_nif", "es_moroso", "fecha", "fecha_operacion", "id"}
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]

    if len(numeric_cols) == 0:
        raise SystemExit("No se encontraron columnas numéricas para generar el elbow plot.")

    X = df[numeric_cols].values

    # Normalizar
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k_range = range(2, kmax + 1)
    wcss = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        km.fit(X_scaled)
        wcss.append(km.inertia_)

    # Heurística similar al original: reducir proporciones para encontrar codo
    proporciones = [(wcss[i] - wcss[i+1]) / wcss[i] for i in range(len(wcss)-1)]
    if len(proporciones) > 0:
        idx_codo = int(np.argmax(proporciones))
        k_opt = list(k_range)[idx_codo]
    else:
        k_opt = None

    output_dir.mkdir(parents=True, exist_ok=True)
    fecha = "2026-04-23"
    suffix = f"-k{kmax}"
    if mark_k is not None:
        suffix += f"-markk{mark_k}"
    out_png = output_dir / f"kmeans_elbow_method_{fecha}{suffix}.png"

    plt.figure(figsize=(10, 6))
    plt.plot(list(k_range), wcss, marker='o', linewidth=2)
    # Marcar k opcional (prioridad sobre heurística)
    if mark_k is not None:
        plt.axvline(x=mark_k, color='red', linestyle='--', label=f'K marcado = {mark_k}')
    else:
        if k_opt is not None:
            plt.axvline(x=k_opt, color='red', linestyle='--', label=f'K óptimo (heurística) = {k_opt}')
    plt.title(f'Elbow Method (K-Means)  k=2..{kmax}', fontsize=14)
    plt.xlabel('Número de clusters (k)')
    plt.ylabel('WCSS (inertia)')
    plt.grid(True, alpha=0.3)
    if k_opt is not None:
        plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Elbow plot guardado: {out_png}")


if __name__ == '__main__':
    main()
