#!/usr/bin/env python3
"""
Boxplots comparativos morosos vs no morosos — Sección 4.3 EDA (TFG)

Decisiones de escala por variable:
  - saldo_pendiente_total   → log puro, filtro > 0 (excluye ceros y negativos).
                               Razón: el usuario pide explícitamente filtrar negativos
                               (sobrepagos) y anotar la exclusión. Con 11 k filas
                               positivas restantes la figura es legible.
  - n_facturas_totales      → log puro, filtro > 0 (solo 3 426 ceros, ~5,6 %).
  - n_facturas_vencidas     → symlog (linthresh=1): 76 % son ceros (no morosos).
                               Filtrar > 0 eliminaría casi todos los no morosos.
  - n_facturas_morosas      → symlog: todos los no morosos tienen 0 por definición.
  - proporcion_facturas_mor → lineal (0–1), sin filtro.
  - dias_mora_maximo        → symlog: todos los no morosos tienen 0 por definición.

Salida: output/boxplots_morosidad.pdf  y  output/boxplots_morosidad.png
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Carga ──────────────────────────────────────────────────────────────────────
DATA_PATH = "output/morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx"
df = pd.read_excel(DATA_PATH, sheet_name="dataset_morosidad")
N_TOTAL = len(df)

# ── Variables y configuración ─────────────────────────────────────────────────
# (col, ylabel_base, scale)
VARS = [
    ("saldo_pendiente_total",       "Saldo pendiente (EUR)",       "log"),
    ("n_facturas_totales",          "Núm. facturas totales",       "log"),
    ("n_facturas_vencidas",         "Núm. facturas vencidas",      "symlog"),
    ("n_facturas_morosas",          "Núm. facturas morosas",       "symlog"),
    ("proporcion_facturas_morosas", "Proporción facturas morosas", "linear"),
    ("dias_mora_maximo",            "Días de mora máximo",         "symlog"),
]

COLOR_FALSE = "#7aab7a"   # verde apagado — no moroso
COLOR_TRUE  = "#c47a7a"   # rojo apagado  — moroso

FLIER_PROPS   = dict(marker="o", markersize=2, alpha=0.3,
                     markerfacecolor="#888888", markeredgewidth=0,
                     linestyle="none")
MEDIAN_PROPS  = dict(color="black", linewidth=1.5)
WHISKER_PROPS = dict(linewidth=0.8, color="#444444")
CAP_PROPS     = dict(linewidth=0.8, color="#444444")

# ── Figura ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(14, 8))
axes = axes.flatten()

dropped_info: dict[str, int] = {}

for ax, (col, ylabel_base, scale) in zip(axes, VARS):

    # Filtrado previo para escala log (elimina ceros y negativos)
    if scale == "log":
        df_sub = df[df[col] > 0]
        dropped_info[col] = N_TOTAL - len(df_sub)
    else:
        df_sub = df
        dropped_info[col] = 0

    data_false = df_sub.loc[df_sub["es_moroso"] == False, col].dropna().values
    data_true  = df_sub.loc[df_sub["es_moroso"] == True,  col].dropna().values

    bp = ax.boxplot(
        [data_false, data_true],
        positions=[1, 2],
        widths=0.5,
        patch_artist=True,
        flierprops=FLIER_PROPS,
        medianprops=MEDIAN_PROPS,
        whiskerprops=WHISKER_PROPS,
        capprops=CAP_PROPS,
        showfliers=True,
    )

    for patch, color in zip(bp["boxes"], [COLOR_FALSE, COLOR_TRUE]):
        patch.set_facecolor(color)
        patch.set_alpha(0.85)

    # Escala Y y etiqueta
    if scale == "log":
        ax.set_yscale("log")
        ylabel_full = f"{ylabel_base} (escala log)"
    elif scale == "symlog":
        ax.set_yscale("symlog", linthresh=1)
        ylabel_full = f"{ylabel_base} (escala symlog)"
    else:
        ylabel_full = ylabel_base

    ax.set_ylabel(ylabel_full, fontsize=8.5)

    # Eje X
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["No moroso", "Moroso"], fontsize=9)
    ax.set_xlabel("")
    ax.tick_params(axis="y", labelsize=8)

    # Título en fuente monoespaciada
    title = col
    if col == "saldo_pendiente_total":
        title += "\n(excl. valores ≤ 0)"
    ax.set_title(title, fontfamily="monospace", fontsize=9, pad=5)

    ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.5)

fig.suptitle(
    "Distribución de variables numéricas por grupo de morosidad",
    fontsize=12,
    y=1.01,
)
plt.tight_layout()

# ── Guardar ────────────────────────────────────────────────────────────────────
fig.savefig("output/boxplots_morosidad.pdf", dpi=300, bbox_inches="tight")
fig.savefig("output/boxplots_morosidad.png", dpi=300, bbox_inches="tight")
print("Guardado: output/boxplots_morosidad.pdf  y  output/boxplots_morosidad.png\n")

# ── Resumen por consola ────────────────────────────────────────────────────────
SEP = "=" * 68

print(SEP)
print("FILAS DESCARTADAS POR FILTRO log (> 0)")
print(SEP)
for col, n in dropped_info.items():
    if n > 0:
        pct = 100 * n / N_TOTAL
        print(f"  {col:<35s}: {n:>6,} filas ({pct:.2f} %)")
    else:
        print(f"  {col:<35s}: sin filtrado")

print(f"\n{SEP}")
print("PERCENTILES P25 / P50 / P75 POR VARIABLE Y GRUPO")
print(SEP)

for col, _, scale in VARS:
    df_sub = df[df[col] > 0] if scale == "log" else df
    print(f"\n  {col}")
    for label, flag in [("No moroso", False), ("Moroso", True)]:
        vals = df_sub.loc[df_sub["es_moroso"] == flag, col].dropna()
        if len(vals) == 0:
            print(f"    {label:<12s}: sin datos tras filtrado")
            continue
        p25, p50, p75 = np.percentile(vals, [25, 50, 75])
        print(
            f"    {label:<12s}: "
            f"P25={p25:>12.4f}  P50={p50:>12.4f}  P75={p75:>12.4f}  "
            f"(n={len(vals):,})"
        )
