"""
Diagrama de persistencia homológica – Sección 4.5 del TFG.

Calcula H0 (componentes conexas) y H1 (huecos 1-dimensionales) sobre la nube
de puntos del dataset de morosidad preprocesado exactamente como la Sección 4.4.

Aviso técnico: Vietoris–Rips sobre 61 347 puntos en dim=31 es inviable.
Se usa submuestreo estratificado por es_moroso (random_state=42) con n=2000.
"""

import sys
import time
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import pairwise_distances
from ripser import ripser

warnings.filterwarnings('ignore')

# Forzar UTF-8 en la consola de Windows (cp1252 no soporta algunos caracteres)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Rutas ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parents[2]
DATA_FILE    = PROJECT_ROOT / "output" / "morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx"
OUT_DIR      = PROJECT_ROOT / "output"


# ══════════════════════════════════════════════════════════════════════════
# 1. LEER DATOS
# ══════════════════════════════════════════════════════════════════════════
print("=" * 65)
print("DIAGRAMA DE PERSISTENCIA HOMOLÓGICA – SECCIÓN 4.5")
print("=" * 65)
print(f"\nLeyendo: {DATA_FILE.name}")
df = pd.read_excel(DATA_FILE, sheet_name="dataset_morosidad")
print(f"  Filas: {len(df):,}  |  Columnas: {len(df.columns)}")


# ══════════════════════════════════════════════════════════════════════════
# 2. PREPROCESAMIENTO (idéntico a Sección 4.4)
# ══════════════════════════════════════════════════════════════════════════
print("\n[1/5] Preprocesamiento...")
df_prep = df.copy()

# 2a. Variables numéricas (directas)
numeric_features = [
    'saldo_pendiente_total', 'n_facturas_totales', 'n_facturas_vencidas',
    'n_facturas_morosas', 'proporcion_facturas_morosas', 'dias_mora_maximo',
]
numeric_features = [c for c in numeric_features if c in df_prep.columns]

# 2b. fecha_creacion → 3 columnas numéricas; imputar ausentes con mediana
temporal_features = []
if 'fecha_creacion' in df_prep.columns:
    df_prep['fecha_creacion'] = pd.to_datetime(df_prep['fecha_creacion'], errors='coerce')
    df_prep['fecha_anio']     = df_prep['fecha_creacion'].dt.year
    df_prep['fecha_mes']      = df_prep['fecha_creacion'].dt.month
    df_prep['fecha_dia_anio'] = df_prep['fecha_creacion'].dt.dayofyear
    temporal_features = ['fecha_anio', 'fecha_mes', 'fecha_dia_anio']
    for col in temporal_features:
        med = df_prep[col].median()
        df_prep[col] = df_prep[col].fillna(med)
        print(f"    {col}: mediana = {int(med)}")

# 2c. provincia: top-10 + prov_Otras (NaN contabiliza como Otras)
prov_cols = []
if 'provincia' in df_prep.columns:
    top10_prov = df_prep['provincia'].value_counts().head(10).index.tolist()
    for p in top10_prov:
        col = f'prov_{p}'.replace(' ', '_')
        df_prep[col] = (df_prep['provincia'] == p).astype(int)
        prov_cols.append(col)
    df_prep['prov_Otras'] = (~df_prep['provincia'].isin(top10_prov)).astype(int)
    prov_cols.append('prov_Otras')
    print(f"    provincia: {len(prov_cols)} columnas (top-10 + prov_Otras)")

# 2d. pais: one-hot estándar (todas las categorías)
pais_cols = []
if 'pais' in df_prep.columns:
    pais_dummies = pd.get_dummies(df_prep['pais'], prefix='pais', dummy_na=False)
    pais_dummies = pais_dummies.astype(int)
    pais_cols = list(pais_dummies.columns)
    df_prep = pd.concat([df_prep, pais_dummies], axis=1)
    print(f"    pais: {len(pais_cols)} columnas ({pais_cols})")

# 2e. tipo: one-hot estándar (todas las categorías)
tipo_cols = []
if 'tipo' in df_prep.columns:
    tipo_dummies = pd.get_dummies(df_prep['tipo'], prefix='tipo', dummy_na=False)
    tipo_dummies = tipo_dummies.astype(int)
    tipo_cols = list(tipo_dummies.columns)
    df_prep = pd.concat([df_prep, tipo_dummies], axis=1)
    print(f"    tipo: {len(tipo_cols)} columnas ({tipo_cols})")

# 2f. cnae: one-hot con cnae_Otras para categorías < 1% de registros
cnae_cols = []
if 'cnae' in df_prep.columns:
    umbral_cnae = int(0.01 * len(df_prep))  # 1 % de 61 347 ≈ 613
    freq_cnae   = df_prep['cnae'].value_counts()
    cnae_frec   = freq_cnae[freq_cnae >= umbral_cnae].index.tolist()
    for c in cnae_frec:
        col = f'cnae_{c}'
        df_prep[col] = (df_prep['cnae'] == c).astype(int)
        cnae_cols.append(col)
    df_prep['cnae_Otras'] = (~df_prep['cnae'].isin(cnae_frec)).astype(int)
    cnae_cols.append('cnae_Otras')
    print(f"    cnae: {len(cnae_frec)} categorias >=1% + cnae_Otras = {len(cnae_cols)} columnas")

# 2g. Construir matriz X (sin etiquetas objetivo ni cif_nif)
all_features = numeric_features + temporal_features + prov_cols + pais_cols + tipo_cols + cnae_cols
all_features  = [c for c in all_features if c in df_prep.columns]
X_df = df_prep[all_features].copy()

# 2h. Imputar valores faltantes restantes (no debería haber ninguno)
n_miss = X_df.isnull().sum().sum()
if n_miss > 0:
    print(f"    Imputando {n_miss} valores faltantes residuales...")
    for col in X_df.columns:
        if X_df[col].isnull().any():
            if col in numeric_features + temporal_features:
                X_df[col] = X_df[col].fillna(X_df[col].median())
            else:
                X_df[col] = X_df[col].fillna(0)


# ══════════════════════════════════════════════════════════════════════════
# 3. VERIFICACIÓN DE DIMENSIONES
# ══════════════════════════════════════════════════════════════════════════
print(f"\n[2/5] Verificación de la matriz X...")
n_rows, n_cols  = X_df.shape
n_miss_final    = X_df.isnull().sum().sum()
print(f"    Dimensiones: {n_rows:,} filas × {n_cols} columnas")
print(f"    Valores ausentes: {n_miss_final}")

print(f"\n    Desglose de columnas:")
print(f"      numéricas  : {len(numeric_features)}")
print(f"      temporales : {len(temporal_features)}")
print(f"      provincia  : {len(prov_cols)}")
print(f"      pais       : {len(pais_cols)}")
print(f"      tipo       : {len(tipo_cols)}")
print(f"      cnae       : {len(cnae_cols)}")
print(f"      TOTAL      : {n_cols}")

if n_cols != 31 or n_miss_final != 0:
    print(f"\n*** AVISO: se esperaban 31 columnas y 0 ausentes.")
    print(f"    Columnas encontradas : {n_cols}")
    print(f"    Ausentes encontrados : {n_miss_final}")
    print(f"    Columnas: {all_features}")
    answer = input("\n¿Continuar de todas formas? [s/N]: ").strip().lower()
    if answer != 's':
        print("Abortado por el usuario.")
        sys.exit(0)
else:
    print(f"\n    ✓ 31 columnas, 0 valores ausentes.")


# ══════════════════════════════════════════════════════════════════════════
# 4. NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════
print("\n[3/5] Normalización con StandardScaler...")
X = X_df.values.astype(float)
scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X)
print(f"    Media global   : {X_scaled.mean():.6f}  (esperado ≈ 0)")
print(f"    Std global     : {X_scaled.std():.6f}   (esperado ≈ 1)")


# ══════════════════════════════════════════════════════════════════════════
# 5. SUBMUESTREO ESTRATIFICADO (estrategia: n=2000, random_state=42)
# ══════════════════════════════════════════════════════════════════════════
print("\n[4/5] Submuestreo estratificado por es_moroso (n=2000, seed=42)...")
y = df['es_moroso'].values
N_SAMPLE = 2000
rng = np.random.default_rng(42)

idx_morosos    = np.where(y == 1)[0]
idx_no_morosos = np.where(y == 0)[0]
prop_morosos   = len(idx_morosos) / len(y)
n_mor_sample   = round(N_SAMPLE * prop_morosos)
n_nomo_sample  = N_SAMPLE - n_mor_sample

sel_mor  = rng.choice(idx_morosos,    size=n_mor_sample,  replace=False)
sel_nomo = rng.choice(idx_no_morosos, size=n_nomo_sample, replace=False)
sample_idx = np.concatenate([sel_mor, sel_nomo])
rng.shuffle(sample_idx)

X_sample  = X_scaled[sample_idx]
y_sample  = y[sample_idx]
prop_muestra = float(y_sample.mean())

print(f"    Puntos seleccionados : {len(sample_idx)}")
print(f"    Proporción morosos   : {prop_muestra:.4f}  (original: {prop_morosos:.4f})")


# ══════════════════════════════════════════════════════════════════════════
# 6. ESTIMACIÓN DE thresh (percentil 50 de distancias en mini-muestra)
# ══════════════════════════════════════════════════════════════════════════
print("\n    Estimando thresh con mini-muestra de 300 pts...")
n_mini   = min(300, len(X_sample))
mini_idx = rng.choice(len(X_sample), size=n_mini, replace=False)
X_mini   = X_sample[mini_idx]
dists    = pairwise_distances(X_mini, metric='euclidean')
tril_i, tril_j = np.tril_indices_from(dists, k=-1)
thresh   = float(np.percentile(dists[tril_i, tril_j], 50))
print(f"    thresh = p50 de {n_mini} pts = {thresh:.4f}")
print(f"    (Recorta H0 con muerte > thresh; conserva rasgos persistentes)")


# ══════════════════════════════════════════════════════════════════════════
# 7. HOMOLOGÍA PERSISTENTE CON RIPSER
# ══════════════════════════════════════════════════════════════════════════
print("\n[5/5] Calculando homología persistente (ripser)...")
print(f"    maxdim=1 | métrica=euclidean | thresh={thresh:.4f}")
t0     = time.time()
result = ripser(X_sample, maxdim=1, metric='euclidean', thresh=thresh)
t_hom  = time.time() - t0
print(f"    Tiempo: {t_hom:.1f} s")

dgms = result['dgms']
h0   = dgms[0]   # shape (n, 2): columnas [birth, death]
h1   = dgms[1]   # shape (m, 2)


# ══════════════════════════════════════════════════════════════════════════
# 8. DIAGRAMA DE PERSISTENCIA
# ══════════════════════════════════════════════════════════════════════════
print("\nGenerando diagrama de persistencia...")

# Nivel visual del eje "infinito" (por encima de todos los puntos finitos)
y_max_finite = thresh
if len(h1) > 0:
    h1_fin = h1[h1[:, 1] != np.inf]
    if len(h1_fin) > 0:
        y_max_finite = max(y_max_finite, h1_fin[:, 1].max())
y_inf_level = y_max_finite * 1.09

# ── Separar finitos e infinitos ──
h0_fin = h0[h0[:, 1] != np.inf].copy()
h0_inf = h0[h0[:, 1] == np.inf].copy()
h1_fin = h1[h1[:, 1] != np.inf].copy() if len(h1) > 0 else np.empty((0, 2))
h1_inf = h1[h1[:, 1] == np.inf].copy() if len(h1) > 0 else np.empty((0, 2))

fig, ax = plt.subplots(figsize=(8, 7))

# ── H0 (finitos) ──
if len(h0_fin) > 0:
    ax.scatter(h0_fin[:, 0], h0_fin[:, 1],
               c='steelblue', marker='o', alpha=0.6, s=28,
               label=r'$H_0$ (comp. conexas)', zorder=3)

# ── H0 (infinitos → línea ∞) ──
if len(h0_inf) > 0:
    ax.scatter(h0_inf[:, 0], np.full(len(h0_inf), y_inf_level),
               c='steelblue', marker='o', alpha=0.6, s=28, zorder=3)

# ── H1 (finitos) ──
if len(h1_fin) > 0:
    ax.scatter(h1_fin[:, 0], h1_fin[:, 1],
               c='darkorange', marker='^', alpha=0.6, s=50,
               label=r'$H_1$ (huecos 1D)', zorder=4)

# ── H1 (infinitos → línea ∞) ──
if len(h1_inf) > 0:
    ax.scatter(h1_inf[:, 0], np.full(len(h1_inf), y_inf_level),
               c='darkorange', marker='^', alpha=0.6, s=50, zorder=4)

# ── Diagonal y = x ──
x_diag = np.array([0, thresh])
ax.plot(x_diag, x_diag, '--', color='lightgray', linewidth=1.2, zorder=1)

# ── Línea de infinito ──
ax.axhline(y=y_inf_level, linestyle='--', color='silver', linewidth=0.9, zorder=1)
ax.text(thresh * 0.985, y_inf_level + y_max_finite * 0.01,
        r'$\infty$', ha='right', va='bottom', fontsize=12, color='gray')

# ── Título principal + subtítulo ──
fig.suptitle('Diagrama de persistencia del dataset de morosidad',
             fontsize=13, fontweight='bold', y=0.995)
ax.set_title(
    f'n = {N_SAMPLE} pts · submuestreo estratificado por es_moroso · '
    f'thresh = p50 dist. ({thresh:.3f})',
    fontsize=8.5, color='dimgray', pad=6
)

ax.set_xlabel(r'Nacimiento ($\varepsilon$)', fontsize=12)
ax.set_ylabel(r'Muerte ($\varepsilon$)',     fontsize=12)

ax.set_xlim(left=-0.02 * thresh)
ax.set_ylim(bottom=-0.02 * thresh, top=y_inf_level + y_max_finite * 0.06)

if len(h1_fin) > 0 or len(h1_inf) > 0:
    ax.legend(loc='lower right', fontsize=10, framealpha=0.9)
else:
    ax.legend(loc='lower right', fontsize=10, framealpha=0.9)

ax.grid(True, alpha=0.22)
plt.tight_layout(rect=[0, 0, 1, 0.97])

pdf_path = OUT_DIR / "persistencia_morosidad.pdf"
png_path = OUT_DIR / "persistencia_morosidad.png"
plt.savefig(pdf_path, dpi=300, bbox_inches='tight')
plt.savefig(png_path, dpi=300, bbox_inches='tight')
print(f"    Guardado: {pdf_path.name}")
print(f"    Guardado: {png_path.name}")
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# 9. RESUMEN CONSOLA
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("RESUMEN")
print("=" * 65)
print(f"  Puntos submuestreados        : {N_SAMPLE}")
print(f"  Proporción morosos en muestra: {prop_muestra:.4f}  ({prop_muestra*100:.2f} %)")
print(f"  Tiempo cálculo homología     : {t_hom:.2f} s")
print(f"  Rasgos H0 detectados         : {len(h0)}")
print(f"  Rasgos H1 detectados         : {len(h1)}")

h1_finitos = h1[h1[:, 1] != np.inf] if len(h1) > 0 else np.empty((0, 2))
if len(h1_finitos) > 0:
    persist_h1 = h1_finitos[:, 1] - h1_finitos[:, 0]
    top5_idx   = np.argsort(persist_h1)[::-1][:5]
    print(f"\n  Top-5 rasgos H1 por persistencia (Death − Birth):")
    for rank, i in enumerate(top5_idx, 1):
        b, d = h1_finitos[i]
        p = d - b
        print(f"    {rank}. Birth={b:.4f}  Death={d:.4f}  Persistencia={p:.4f}")
elif len(h1) > 0:
    print(f"\n  Todos los rasgos H1 son infinitos (sobreviven al filtro thresh={thresh:.4f}).")
    print(f"  Birth de los rasgos H1 infinitos: {h1[:, 0].tolist()}")
else:
    print(f"\n  No se detectaron rasgos H1.")

print("=" * 65)
print(f"\nArchivos generados en {OUT_DIR.name}/:")
print(f"  - persistencia_morosidad.pdf")
print(f"  - persistencia_morosidad.png")
