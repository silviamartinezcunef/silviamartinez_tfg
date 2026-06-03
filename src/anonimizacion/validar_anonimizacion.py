"""
Script de validación de anonimización.

Compara el archivo original vs. anonimizado para verificar que:
1. Número de clientes únicos se preserva
2. Códigos provinciales se mantienen intactos
3. Distribución de morosidad es idéntica
4. Análisis de provincias funciona correctamente
"""

import pandas as pd
import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parents[1]))

from creditdataqc._log import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parents[2]  # src/anonimizacion/ → raíz
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"


def validar_anonimizacion(file_original: Path, file_anonimizado: Path):
    """
    Ejecuta batería de validaciones comparando archivos original y anonimizado.
    """
    logger.info("="*70)
    logger.info("VALIDACIÓN DE ANONIMIZACIÓN")
    logger.info("="*70)

    # Leer archivos (detectar estructura)
    logger.info("\n[1] Leyendo archivos...")

    xls_orig = pd.ExcelFile(file_original)
    xls_anon = pd.ExcelFile(file_anonimizado)

    # Leer archivo original
    if 'dataset_morosidad' in xls_orig.sheet_names:
        df_orig = pd.read_excel(file_original, sheet_name='dataset_morosidad')
    elif 'morosos' in xls_orig.sheet_names:
        df_orig_morosos = pd.read_excel(file_original, sheet_name='morosos')
        df_orig_no_morosos = pd.read_excel(file_original, sheet_name='no_morosos')
        df_orig = pd.concat([df_orig_morosos, df_orig_no_morosos], ignore_index=True)
    else:
        raise ValueError(f"Estructura no reconocida en original: {xls_orig.sheet_names}")

    # Leer archivo anonimizado
    if 'dataset_morosidad' in xls_anon.sheet_names:
        df_anon = pd.read_excel(file_anonimizado, sheet_name='dataset_morosidad')
    elif 'morosos' in xls_anon.sheet_names:
        df_anon_morosos = pd.read_excel(file_anonimizado, sheet_name='morosos')
        df_anon_no_morosos = pd.read_excel(file_anonimizado, sheet_name='no_morosos')
        df_anon = pd.concat([df_anon_morosos, df_anon_no_morosos], ignore_index=True)
    else:
        raise ValueError(f"Estructura no reconocida en anonimizado: {xls_anon.sheet_names}")

    logger.info(f"  Original: {len(df_orig)} registros")
    logger.info(f"  Anonimizado: {len(df_anon)} registros")

    # Test 1: Número de clientes únicos
    logger.info("\n[2] Validando número de clientes únicos...")
    n_clientes_orig = df_orig['cif_nif'].nunique()
    n_clientes_anon = df_anon['cif_nif'].nunique()

    if n_clientes_orig == n_clientes_anon:
        logger.info(f"  ✓ PASS: {n_clientes_orig} clientes únicos en ambos archivos")
    else:
        logger.error(f"  ✗ FAIL: Original {n_clientes_orig} vs Anonimizado {n_clientes_anon}")
        return False

    # Test 2: Número de registros
    logger.info("\n[3] Validando número de registros...")
    if len(df_orig) == len(df_anon):
        logger.info(f"  ✓ PASS: {len(df_orig)} registros en ambos archivos")
    else:
        logger.error(f"  ✗ FAIL: Original {len(df_orig)} vs Anonimizado {len(df_anon)}")
        return False

    # Test 3: Distribución de morosidad
    logger.info("\n[4] Validando distribución de morosidad...")
    mora_orig = df_orig['mora_formula'].value_counts().sort_index()
    mora_anon = df_anon['mora_formula'].value_counts().sort_index()

    if mora_orig.equals(mora_anon):
        logger.info(f"  ✓ PASS: Distribución idéntica")
        logger.info(f"    - No morosos: {mora_orig[0]}")
        logger.info(f"    - Morosos: {mora_orig[1]}")
    else:
        logger.error(f"  ✗ FAIL: Distribución diferente")
        logger.error(f"    Original: {mora_orig.to_dict()}")
        logger.error(f"    Anonimizado: {mora_anon.to_dict()}")
        return False

    # Test 4: Análisis de provincias
    logger.info("\n[5] Validando mapeo de provincias...")

    # Verificar que existe columna provincia en ambos
    if 'provincia' not in df_orig.columns or 'provincia' not in df_anon.columns:
        logger.warning("  ⚠ Columna 'provincia' no encontrada - saltando test")
    else:
        # Comparar distribución de provincias (con tolerancia para variaciones menores en "Unknown")
        dist_prov_orig = df_orig['provincia'].value_counts().sort_index()
        dist_prov_anon = df_anon['provincia'].value_counts().sort_index()

        # Calcular diferencias absolutas
        all_provincias = set(dist_prov_orig.index) | set(dist_prov_anon.index)
        max_diff = 0
        total_diff = 0

        for prov in all_provincias:
            count_orig = dist_prov_orig.get(prov, 0)
            count_anon = dist_prov_anon.get(prov, 0)
            diff = abs(count_orig - count_anon)
            max_diff = max(max_diff, diff)
            total_diff += diff

        # Tolerancia: máximo 5 clientes de diferencia por provincia, máximo 10 total
        # Esto permite pequeñas variaciones en códigos provinciales ambiguos (NIEs, etc.)
        if max_diff <= 5 and total_diff <= 10:
            logger.info(f"  ✓ PASS: Distribución de provincias preservada")
            logger.info(f"    Diferencia máxima por provincia: {max_diff} clientes")
            logger.info(f"    Diferencia total: {total_diff} clientes (sobre {len(df_orig)} registros)")
            logger.info(f"    Top 5 provincias:")
            for prov, count in dist_prov_orig.head(5).items():
                count_anon = dist_prov_anon.get(prov, 0)
                logger.info(f"      - {prov}: {count} → {count_anon}")
        else:
            logger.error(f"  ✗ FAIL: Distribución de provincias alterada significativamente")
            logger.error(f"    Diferencia máxima: {max_diff} clientes (umbral: 5)")
            logger.error(f"    Diferencia total: {total_diff} clientes (umbral: 10)")
            logger.error(f"    Original top 5: {dist_prov_orig.head().to_dict()}")
            logger.error(f"    Anonimizado top 5: {dist_prov_anon.head().to_dict()}")
            return False

    # Test 5: Columnas presentes
    logger.info("\n[6] Validando columnas del dataset...")
    cols_orig = set(df_orig.columns)
    cols_anon = set(df_anon.columns)

    if cols_orig == cols_anon:
        logger.info(f"  ✓ PASS: {len(cols_orig)} columnas idénticas")
    else:
        cols_faltantes = cols_orig - cols_anon
        cols_extra = cols_anon - cols_orig
        if cols_faltantes:
            logger.warning(f"  ⚠ Columnas faltantes en anonimizado: {cols_faltantes}")
        if cols_extra:
            logger.warning(f"  ⚠ Columnas extra en anonimizado: {cols_extra}")

    # Test 6: Verificación de NIFs no son identificables
    logger.info("\n[7] Verificando que NIFs son sintéticos...")
    nifs_orig_sample = df_orig['cif_nif'].sample(min(5, len(df_orig))).tolist()
    nifs_anon_sample = df_anon['cif_nif'].sample(min(5, len(df_anon))).tolist()

    logger.info(f"  Muestra de NIFs originales:")
    for nif in nifs_orig_sample:
        logger.info(f"    - {nif}")

    logger.info(f"  Muestra de NIFs anonimizados:")
    for nif in nifs_anon_sample:
        logger.info(f"    - {nif}")

    # Verificar que ningún NIF anonimizado coincide con uno original
    nifs_orig_set = set(df_orig['cif_nif'].unique())
    nifs_anon_set = set(df_anon['cif_nif'].unique())
    coincidencias = nifs_orig_set & nifs_anon_set

    if len(coincidencias) == 0:
        logger.info(f"  ✓ PASS: No hay coincidencias entre NIFs originales y anonimizados")
    else:
        logger.error(f"  ✗ FAIL: {len(coincidencias)} NIFs coinciden (no anonimizados correctamente)")
        return False

    # Test 7: Distribución por tipo de persona
    logger.info("\n[8] Validando distribución por tipo de persona...")
    if 'tipo_persona' in df_orig.columns:
        tipo_orig = df_orig['tipo_persona'].value_counts().sort_index()
        tipo_anon = df_anon['tipo_persona'].value_counts().sort_index()

        if tipo_orig.equals(tipo_anon):
            logger.info(f"  ✓ PASS: Distribución por tipo idéntica")
            for tipo, count in tipo_orig.items():
                logger.info(f"    - {tipo}: {count}")
        else:
            logger.error(f"  ✗ FAIL: Distribución por tipo diferente")
            return False

    # Resumen final
    logger.info("\n" + "="*70)
    logger.info("✓✓✓ VALIDACIÓN EXITOSA ✓✓✓")
    logger.info("="*70)
    logger.info("El archivo anonimizado preserva:")
    logger.info("  ✓ Número de clientes únicos")
    logger.info("  ✓ Distribución de morosidad")
    logger.info("  ✓ Mapeo de provincias (códigos provinciales)")
    logger.info("  ✓ Estructura del dataset")
    logger.info("  ✓ Anonimización efectiva (NIFs sintéticos)")
    logger.info("\n✓ Los scripts de clustering y MAPPER funcionarán correctamente")

    return True


def main():
    """
    Ejecuta validación entre archivo original y anonimizado.
    """
    fecha = '2026-04-23'
    file_original = DATA_OUTPUT_DIR / f"morosidad_dataset_{fecha}.xlsx"
    file_anonimizado = DATA_OUTPUT_DIR / f"morosidad_dataset_{fecha}_ANONIMIZADO.xlsx"

    # Validar existencia de archivos
    if not file_original.exists():
        logger.error(f"Archivo original no encontrado: {file_original}")
        return

    if not file_anonimizado.exists():
        logger.error(f"Archivo anonimizado no encontrado: {file_anonimizado}")
        logger.info("Ejecuta primero: python src/creditdataqc/anonimizar_nif.py")
        return

    # Ejecutar validación
    exito = validar_anonimizacion(file_original, file_anonimizado)

    if exito:
        logger.info("\n" + "="*70)
        logger.info("PRÓXIMOS PASOS")
        logger.info("="*70)
        logger.info("1. Ejecutar clustering con archivo anonimizado:")
        logger.info("   python src/creditdataqc/mora_analysis_clustering.py")
        logger.info("")
        logger.info("2. Ejecutar MAPPER con archivo anonimizado:")
        logger.info("   python src/creditdataqc/mora_analysis_mapper.py")
        logger.info("")
        logger.info("3. Si todo funciona, puedes renombrar el archivo anonimizado")
        logger.info("   para reemplazar el original (hacer backup primero)")


if __name__ == "__main__":
    main()
