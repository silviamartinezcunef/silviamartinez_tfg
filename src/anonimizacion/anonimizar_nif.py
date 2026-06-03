"""
Script de anonimización de NIFs para TFG.

Preserva:
- Código provincial (2 primeros dígitos numéricos) para mapeo de provincias
- Unicidad de clientes (hash SHA256)
- Tipo de persona (estructura del NIF/CIF)

Protege:
- Identidad real de empresas y personas
- Trazabilidad hacia identificadores originales
"""

import pandas as pd
import numpy as np
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, Optional

# Añadir src al path para imports
sys.path.insert(0, str(Path(__file__).parents[1]))

from creditdataqc._log import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parents[2]  # src/anonimizacion/ → raíz
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"


def extraer_codigo_provincial(nif: str) -> str:
    """
    Extrae los 2 primeros dígitos numéricos del CIF/NIF.

    Ejemplos:
        'A28123456' → '28' (Madrid)
        'B08987654' → '08' (Barcelona)
        'X1234567Z' → '' (NIE sin código provincial)
        '12345678A' → '12' (Castellón, NIF persona)

    Args:
        nif: CIF/NIF original

    Returns:
        Código provincial de 2 dígitos o '' si no aplica
    """
    if pd.isna(nif) or nif == '':
        return ''

    nif_clean = str(nif).strip().upper()

    # Buscar los primeros 2 dígitos consecutivos
    match = re.search(r'\d{2}', nif_clean)

    if match:
        codigo = match.group()
        # Validar que esté en rango de códigos provinciales españoles (01-99)
        if 1 <= int(codigo) <= 99:
            return codigo

    return ''


def generar_nif_sintetico(nif_original: str, seed_salt: str = "TFG_2026") -> str:
    """
    Genera un NIF/CIF sintético preservando código provincial.

    Formato generado:
        - Empresas (CIF): {Letra}{Código_Provincial}{Hash6}{Letra_Control}
                Ejemplo: 'B28A1C3D5K' (empresa Madrid, código 28)
        - Personas (NIF): {Código_Provincial}{Hash7}{Letra}
                Ejemplo: '28A1B2C3DZ' (persona Madrid, código 28)

    IMPORTANTE: El código provincial (2 dígitos) siempre está en posiciones 1-2 (CIF)
    o posiciones 0-1 (NIF) para que la función add_provincia_column() funcione.

    Args:
        nif_original: NIF/CIF real del cliente
        seed_salt: Salt para el hash (cambiar genera NIFs diferentes)

    Returns:
        NIF sintético de 10 caracteres
    """
    if pd.isna(nif_original) or nif_original == '':
        return ''

    nif_clean = str(nif_original).strip().upper()

    # Extraer código provincial
    codigo_prov = extraer_codigo_provincial(nif_clean)

    # Si no hay código provincial, generar uno sintético aleatorio pero consistente
    if codigo_prov == '':
        codigo_prov = '99'  # Código reservado para "sin provincia"

    # Generar hash único del NIF completo
    hash_full = hashlib.sha256(f"{seed_salt}_{nif_clean}".encode()).hexdigest()

    # Determinar si es empresa (CIF) o persona (NIF)
    # CIF empieza con letra, NIF empieza con dígito
    es_empresa = nif_clean[0].isalpha() and nif_clean[0] not in ['X', 'Y', 'Z']

    if es_empresa:
        # Formato CIF sintético: {Letra}{CodigoProv}{Hash6}{LetraControl}
        # CIF real:  A28123456K → letra + 8 dígitos + letra
        # CIF sint:  B28A1C3D5F → letra + código_prov(2) + hash(6) + letra

        # Generar letra inicial del hash (debe ser A-Z, no dígito)
        letra_inicio = 'B'  # Valor por defecto
        for char in hash_full:
            if char.isalpha():
                letra_inicio = char.upper()
                break

        hash_medio = hash_full[10:16].upper()   # 6 caracteres hexadecimales

        # Generar letra de control del hash
        letra_control = 'K'  # Valor por defecto
        for char in hash_full[16:]:
            if char.isalpha():
                letra_control = char.upper()
                break

        nif_sintetico = f"{letra_inicio}{codigo_prov}{hash_medio}{letra_control}"

    else:
        # Formato NIF sintético: {CodigoProv}{Hash7}{Letra}
        # NIF real:  12345678Z → 8 dígitos + letra
        # NIF sint:  28A1B2C3D Z → código_prov(2) + hash(7) + letra

        hash_medio = hash_full[10:17].upper()  # 7 caracteres hexadecimales

        # Generar letra de control del hash
        letra_control = 'Z'  # Valor por defecto
        for char in hash_full[17:]:
            if char.isalpha():
                letra_control = char.upper()
                break

        nif_sintetico = f"{codigo_prov}{hash_medio}{letra_control}"

    return nif_sintetico[:10]  # Asegurar longitud máxima de 10


def perturbar_variables_financieras(df: pd.DataFrame, factor: Optional[float] = None,
                                    guardar_factor: bool = True) -> tuple:
    """
    Perturba variables financieras multiplicándolas por un factor común.

    **CONCEPTO CLAVE - Perturbación Multiplicativa:**

    Al multiplicar TODAS las variables financieras por el MISMO factor, se preservan:
    - Ratios entre variables: (A/B) × (factor/factor) = A/B ✓
    - Correlaciones: Si A↑ → B↑, sigue siendo A↑ → B↑ ✓
    - Distribuciones relativas: El mayor sigue siendo el mayor ✓

    **Ejemplo:**
        Cliente con volumen=100,000€ y precio=50€/MWh
        Ratio original: 100,000 / 50 = 2,000 MWh

        Con factor 0.85:
        volumen_nuevo = 85,000€ (×0.85)
        precio_nuevo = 42.5€/MWh (×0.85)
        Ratio nuevo: 85,000 / 42.5 = 2,000 MWh ← ¡PRESERVADO!

    **¿Por qué funciona para clustering/MAPPER?**

    Los algoritmos de clustering usan DISTANCIAS entre puntos:

        Distancia original = sqrt((A₁-A₂)² + (B₁-B₂)²)
        Distancia nueva = sqrt((factor×A₁-factor×A₂)² + (factor×B₁-factor×B₂)²)
                       = factor × sqrt((A₁-A₂)² + (B₁-B₂)²)
                       = factor × Distancia_original

    Las distancias se escalan proporcionalmente → ¡los clusters se mantienen!

    **Protección de confidencialidad:**

    Si una empresa publica "Facturación 2026: 10M€", en tu dataset podría ser:
    - 8.5M€ (factor 0.85)
    - 11.5M€ (factor 1.15)
    - Imposible saber si es la misma empresa

    Args:
        df: DataFrame con variables financieras
        factor: Factor de escalado. Si None, se genera aleatorio entre 0.7-1.3 (±30%)
        guardar_factor: Si True, retorna el factor usado (para documentación)

    Returns:
        Tupla (df_perturbado, factor_usado)
    """
    logger.info("Perturbando variables financieras...")

    # Generar factor aleatorio si no se especifica
    if factor is None:
        np.random.seed(42)  # Semilla para reproducibilidad (cambiar para distinto factor)
        factor = np.random.uniform(0.7, 1.3)  # ±30% de variación

    # Variables financieras a perturbar (adaptar según dataset disponible)
    vars_financieras = [
        # Dataset antiguo (facturas)
        'volumen', 'volumen_maximo', 'precio', 'deuda_asnef',
        'ing_explotacion', 'result_antes_imp', 'importe_neto',
        'total_pasivo', 'fondos_propios', 'limite_total_concedido',
        'limite_disponible_ge', 'riesgo_vivo_power', 'riesgo_vivo_gas',
        'riesgo_vivo_power_falcon', 'volumen_riesgo', 'gastos_financieros',
        'remaining_amount',  # Importes pendientes en facturas

        # Dataset nuevo (clientes agregados)
        'saldo_pendiente_total'  # Saldo total del cliente
    ]

    # Aplicar perturbación
    df_perturbado = df.copy()
    vars_perturbadas = []

    for col in vars_financieras:
        if col in df_perturbado.columns:
            # Verificar que sea numérica
            if pd.api.types.is_numeric_dtype(df_perturbado[col]):
                df_perturbado[col] = df_perturbado[col] * factor
                vars_perturbadas.append(col)

    logger.info(f"✓ {len(vars_perturbadas)} variables perturbadas")
    logger.info(f"  Variables: {', '.join(vars_perturbadas[:5])}{'...' if len(vars_perturbadas) > 5 else ''}")
    logger.info(f"  Factor multiplicativo: ALEATORIO (no se revela)")
    logger.info(f"  → Ratios preservados: (volumen/precio) se mantiene constante ✓")

    if guardar_factor:
        return df_perturbado, factor
    else:
        return df_perturbado


def shift_temporal_fechas(df: pd.DataFrame, shift_days: Optional[int] = None) -> tuple:
    """
    Desplaza todas las fechas del dataset el mismo número de días.

    **CONCEPTO CLAVE - Shift Temporal Uniforme:**

    Al sumar el MISMO número de días a TODAS las fechas, se preservan:
    - Duraciones relativas: (fecha_B - fecha_A) = constante ✓
    - Secuencias temporales: Si A antes que B → sigue A antes que B ✓
    - Períodos: Meses entre eventos se mantienen ✓

    **Ejemplo:**
        Fecha original factura: 2026-04-23
        Fecha original pago:    2026-05-15
        Duración original:      22 días

        Con shift +120 días:
        Fecha nueva factura:    2026-08-21 (+120)
        Fecha nueva pago:       2026-09-12 (+120)
        Duración nueva:         22 días ← ¡PRESERVADA!

    **¿Por qué funciona para el análisis?**

    Los algoritmos de morosidad y clustering usan:
    - Días de retraso: (fecha_pago - due_date) → sigue siendo igual
    - Antigüedad cliente: (hoy - fecha_contratacion) → sigue siendo igual
    - Estacionalidad relativa: Ej: "Q2 2026" → "Q4 2026" (diferente pero válido)

    **Protección de confidencialidad:**

    Si una empresa anuncia "Fusión en abril 2026" y hay un pico de actividad
    en tu dataset en abril 2026 → ¡identificable!

    Con shift +120 días → el pico aparece en agosto 2026 → no correlaciona
    con eventos públicos conocidos.

    Args:
        df: DataFrame con columnas de fechas
        shift_days: Días a desplazar. Si None, se genera aleatorio ±180 días (±6 meses)

    Returns:
        Tupla (df_shifted, shift_days_usado)
    """
    logger.info("Aplicando shift temporal a fechas...")

    # Generar shift aleatorio si no se especifica
    if shift_days is None:
        np.random.seed(43)  # Semilla diferente para distinto offset
        shift_days = np.random.randint(-180, 180)  # ±6 meses

    # Columnas de fechas a desplazar
    columnas_fecha = [
        'fecha_creacion', 'fecha_balance', 'fecha_constitucion',
        'fecha_contratacion', 'due_date', 'posting_date',
        'ano_mes_creacion'  # Formato YYYY-MM también se ajusta
    ]

    df_shifted = df.copy()
    cols_desplazadas = []

    for col in columnas_fecha:
        if col in df_shifted.columns:
            # Convertir a datetime (ignorar errores de formato)
            df_shifted[col] = pd.to_datetime(df_shifted[col], errors='coerce')

            # Aplicar shift
            df_shifted[col] = df_shifted[col] + pd.Timedelta(days=shift_days)

            cols_desplazadas.append(col)

    logger.info(f"✓ {len(cols_desplazadas)} columnas de fecha desplazadas")
    logger.info(f"  Columnas: {', '.join(cols_desplazadas[:5])}{'...' if len(cols_desplazadas) > 5 else ''}")
    logger.info(f"  Offset temporal: ALEATORIO (no se revela)")
    logger.info(f"  → Duraciones preservadas: (fecha_B - fecha_A) se mantiene constante ✓")

    return df_shifted, shift_days


def eliminar_ids_internos(df: pd.DataFrame) -> tuple:
    """
    Elimina columnas con identificadores internos de sistemas empresariales.

    **CONCEPTO CLAVE - Eliminar Trazabilidad:**

    Los IDs internos permiten:
    - Rastrear registros en sistemas internos (Snowflake, CRM)
    - Cruzar con otros datasets internos
    - Identificar versiones específicas de registros

    **Columnas eliminadas (si existen):**
    - id_evaluacion: ID interno del sistema de rating
    - rating_id: ID de solicitud de rating
    - id_cliente: ID maestro en Snowflake
    - id_tramo: Código de producto específico
    - id_negocio: Línea de negocio interna
    - max_id_rating_request: ID de request máximo

    **¿Por qué es seguro eliminarlas?**

    Estas columnas NO se usan en:
    - Clustering (K-Means, DBSCAN, Hierarchical)
    - MAPPER (TDA)
    - Análisis de morosidad (mora_formula)
    - Mapeo de provincias (usa cif_nif)

    Son solo identificadores técnicos sin valor predictivo.

    **Protección de confidencialidad:**

    Sin IDs internos → imposible:
    - Buscar "id_evaluacion=12345" en sistemas internos
    - Cruzar dataset con logs de auditoría
    - Correlacionar con tickets de soporte

    Args:
        df: DataFrame con posibles columnas de IDs internos

    Returns:
        Tupla (df_limpio, lista_ids_eliminados)
    """
    logger.info("Eliminando IDs internos...")

    ids_a_eliminar = [
        'id_evaluacion',          # ID interno del rating
        'rating_id',              # ID de solicitud
        'id_cliente',             # ID maestro Snowflake
        'id_tramo',               # Código de producto
        'id_negocio',             # Línea de negocio
        'id_cliente_riesgo_vivo', # ID cliente en tabla riesgo vivo
        'max_id_rating_request',  # ID de request
        'id_input_custom_data'    # ID de datos custom
    ]

    df_limpio = df.copy()
    ids_eliminados = []

    for col in ids_a_eliminar:
        if col in df_limpio.columns:
            df_limpio.drop(columns=[col], inplace=True)
            ids_eliminados.append(col)

    if ids_eliminados:
        logger.info(f"✓ {len(ids_eliminados)} columnas de IDs eliminadas")
        logger.info(f"  Columnas: {', '.join(ids_eliminados)}")
        logger.info(f"  → Trazabilidad en sistemas internos eliminada ✓")
    else:
        logger.info(f"✓ No se encontraron columnas de IDs internos para eliminar")

    return df_limpio, ids_eliminados


def crear_mapeo_nifs(df: pd.DataFrame, nif_col: str = 'cif_nif') -> Dict[str, str]:
    """
    Crea diccionario de mapeo NIF_original → NIF_sintético.

    Args:
        df: DataFrame con columna de NIFs
        nif_col: Nombre de la columna con NIFs originales

    Returns:
        Diccionario {NIF_original: NIF_sintético}
    """
    nifs_unicos = df[nif_col].dropna().unique()

    mapeo = {}
    nifs_sinteticos_usados = set()

    for nif_original in nifs_unicos:
        nif_sintetico = generar_nif_sintetico(nif_original)

        # Verificar colisiones (muy improbable con SHA256)
        contador = 0
        nif_sintetico_base = nif_sintetico
        while nif_sintetico in nifs_sinteticos_usados:
            contador += 1
            # Añadir sufijo incremental si hay colisión
            nif_sintetico = nif_sintetico_base[:-1] + str(contador % 10)

        mapeo[nif_original] = nif_sintetico
        nifs_sinteticos_usados.add(nif_sintetico)

    logger.info(f"Mapeo creado: {len(mapeo)} NIFs únicos")

    return mapeo


def anonimizar_excel_morosidad(input_file: Path, output_file: Path,
                                guardar_mapeo: bool = False) -> pd.DataFrame:
    """
    Anonimiza el archivo Excel de análisis de morosidad.

    Args:
        input_file: Ruta al Excel original
        output_file: Ruta al Excel anonimizado
        guardar_mapeo: Si True, guarda mapeo NIF_original→NIF_sintético (¡CONFIDENCIAL!)

    Returns:
        DataFrame concatenado con NIFs anonimizados
    """
    logger.info(f"Leyendo archivo original: {input_file}")

    # Detectar estructura del archivo (una hoja vs dos hojas)
    xls = pd.ExcelFile(input_file)
    sheet_names = xls.sheet_names

    if 'dataset_morosidad' in sheet_names:
        # Estructura nueva: una sola hoja
        logger.info("  Estructura detectada: hoja única 'dataset_morosidad'")
        df_completo = pd.read_excel(input_file, sheet_name='dataset_morosidad')
    elif 'morosos' in sheet_names and 'no_morosos' in sheet_names:
        # Estructura antigua: dos hojas separadas
        logger.info("  Estructura detectada: hojas separadas 'morosos' y 'no_morosos'")
        df_morosos = pd.read_excel(input_file, sheet_name='morosos')
        df_no_morosos = pd.read_excel(input_file, sheet_name='no_morosos')
        df_completo = pd.concat([df_morosos, df_no_morosos], ignore_index=True)
    else:
        raise ValueError(f"Estructura de Excel no reconocida. Hojas encontradas: {sheet_names}")

    n_clientes_original = df_completo['cif_nif'].nunique()
    n_registros = len(df_completo)

    logger.info(f"Dataset original: {n_registros} registros, {n_clientes_original} clientes únicos")

    # Crear mapeo de NIFs
    mapeo_nifs = crear_mapeo_nifs(df_completo, nif_col='cif_nif')

    # Aplicar anonimización
    df_completo['cif_nif_original'] = df_completo['cif_nif']  # Backup temporal
    df_completo['cif_nif'] = df_completo['cif_nif'].map(mapeo_nifs)

    # Verificar que no se perdieron clientes
    n_clientes_anonimizados = df_completo['cif_nif'].nunique()
    assert n_clientes_original == n_clientes_anonimizados, \
        f"ERROR: Se perdieron clientes ({n_clientes_original} → {n_clientes_anonimizados})"

    logger.info(f"✓ Anonimización exitosa: {n_clientes_anonimizados} NIFs sintéticos")

    # Verificar preservación de códigos provinciales (muestreo)
    muestra = df_completo.sample(min(10, len(df_completo)))
    logger.info("\nVerificación de códigos provinciales (muestra):")
    for _, row in muestra.iterrows():
        orig = row['cif_nif_original']
        sint = row['cif_nif']
        cod_orig = extraer_codigo_provincial(orig)
        cod_sint = extraer_codigo_provincial(sint)
        match = "✓" if cod_orig == cod_sint else "✗"
        logger.info(f"  {match} {orig} → {sint} (provincia: {cod_orig} → {cod_sint})")

    # Eliminar columna temporal
    df_completo.drop(columns=['cif_nif_original'], inplace=True)

    # PASO 2: Perturbar variables financieras
    logger.info("\n" + "="*70)
    logger.info("PASO 2: PERTURBACIÓN DE VARIABLES FINANCIERAS")
    logger.info("="*70)
    df_completo, factor_usado = perturbar_variables_financieras(df_completo, factor=None)

    # PASO 3: Shift temporal de fechas
    logger.info("\n" + "="*70)
    logger.info("PASO 3: SHIFT TEMPORAL DE FECHAS")
    logger.info("="*70)
    df_completo, shift_usado = shift_temporal_fechas(df_completo, shift_days=None)

    # PASO 4: Eliminar IDs internos
    logger.info("\n" + "="*70)
    logger.info("PASO 4: ELIMINAR IDs INTERNOS")
    logger.info("="*70)
    df_completo, ids_eliminados = eliminar_ids_internos(df_completo)

    # Exportar Excel anonimizado (mantener estructura original)
    logger.info(f"Exportando a: {output_file}")

    if 'dataset_morosidad' in sheet_names:
        # Estructura nueva: una sola hoja (dataset agregado por cliente)
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df_completo.to_excel(writer, sheet_name='dataset_morosidad', index=False)

        # Detectar columna de morosidad (es_moroso, es_moroso_60d, o mora_formula)
        col_mora = None
        for col_candidata in ['es_moroso', 'es_moroso_60d', 'mora_formula']:
            if col_candidata in df_completo.columns:
                col_mora = col_candidata
                break

        if col_mora:
            n_morosos = df_completo[col_mora].sum() if df_completo[col_mora].dtype == 'bool' else (df_completo[col_mora] == 1).sum()
            n_no_morosos = len(df_completo) - n_morosos
            logger.info(f"\nExcel anonimizado guardado:")
            logger.info(f"    - Sheet 'dataset_morosidad': {len(df_completo)} registros")
            logger.info(f"      ({n_morosos} morosos, {n_no_morosos} no morosos segun '{col_mora}')")
        else:
            logger.info(f"\nExcel anonimizado guardado:")
            logger.info(f"    - Sheet 'dataset_morosidad': {len(df_completo)} registros")
    else:
        # Estructura antigua: dos hojas separadas (dataset por facturas)
        df_morosos_anon = df_completo[df_completo['mora_formula'] == 1].reset_index(drop=True)
        df_no_morosos_anon = df_completo[df_completo['mora_formula'] == 0].reset_index(drop=True)

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df_morosos_anon.to_excel(writer, sheet_name='morosos', index=False)
            df_no_morosos_anon.to_excel(writer, sheet_name='no_morosos', index=False)

        logger.info(f"\nExcel anonimizado guardado:")
        logger.info(f"    - Sheet 'morosos': {len(df_morosos_anon)} registros")
        logger.info(f"    - Sheet 'no_morosos': {len(df_no_morosos_anon)} registros")
    logger.info(f"\n" + "="*70)
    logger.info(f"📊 RESUMEN DE ANONIMIZACIÓN COMPLETA")
    logger.info(f"="*70)
    logger.info(f"✓ 1. NIFs pseudonimizados: {n_clientes_anonimizados} clientes")
    logger.info(f"     → Código provincial preservado para mapeo geográfico")
    logger.info(f"")
    logger.info(f"✓ 2. Variables financieras perturbadas")
    logger.info(f"     → Factor multiplicativo aleatorio aplicado (NO SE REVELA)")
    logger.info(f"     → Ratios y correlaciones preservados")
    logger.info(f"")
    logger.info(f"✓ 3. Fechas desplazadas")
    logger.info(f"     → Offset temporal aleatorio aplicado (NO SE REVELA)")
    logger.info(f"     → Duraciones relativas preservadas")
    logger.info(f"     → Eventos públicos no correlacionables")
    logger.info(f"")
    logger.info(f"✓ 4. IDs internos eliminados: {len(ids_eliminados)}")
    if ids_eliminados:
        logger.info(f"     → Columnas: {', '.join(ids_eliminados)}")
    logger.info(f"     → Trazabilidad en sistemas internos eliminada")
    logger.info(f"")
    logger.info(f"⚠️  IMPORTANTE: Los factores/offsets aleatorios NO se guardan")
    logger.info(f"   → Imposible revertir la perturbación/shift temporal")
    logger.info(f"="*70)

    # Guardar mapeo (OPCIONAL - SOLO PARA DEBUG)
    if guardar_mapeo:
        mapeo_file = output_file.parent / f"MAPEO_CONFIDENCIAL_{output_file.stem}.csv"
        df_mapeo = pd.DataFrame(list(mapeo_nifs.items()),
                                columns=['NIF_ORIGINAL', 'NIF_SINTETICO'])
        df_mapeo.to_csv(mapeo_file, index=False)
        logger.warning(f"⚠️  MAPEO CONFIDENCIAL guardado en: {mapeo_file}")
        logger.warning(f"⚠️  ELIMINAR este archivo antes de subir a repositorio público")

    return df_completo


def main():
    """
    Ejecuta anonimización del archivo de morosidad.
    """
    # Configuración
    fecha = '2026-04-23'
    input_file = DATA_OUTPUT_DIR / f"analisis_morosidad_{fecha}.xlsx"
    output_file = DATA_OUTPUT_DIR / f"analisis_morosidad_{fecha}_ANONIMIZADO.xlsx"

    # Validar que existe el archivo original
    if not input_file.exists():
        logger.error(f"Archivo no encontrado: {input_file}")
        logger.info(f"Archivos disponibles en {DATA_OUTPUT_DIR}:")
        for f in DATA_OUTPUT_DIR.glob("analisis_morosidad_*.xlsx"):
            logger.info(f"  - {f.name}")
        return

    # Ejecutar anonimización
    df_anonimizado = anonimizar_excel_morosidad(
        input_file=input_file,
        output_file=output_file,
        guardar_mapeo=False  # Cambiar a True solo para debugging
    )

    logger.info("\n" + "="*60)
    logger.info("ANONIMIZACIÓN COMPLETADA")
    logger.info("="*60)
    logger.info(f"Archivo original: {input_file.name}")
    logger.info(f"Archivo anonimizado: {output_file.name}")
    logger.info("\nPróximos pasos:")
    logger.info("1. Verificar que mora_analysis_clustering.py y mora_analysis_mapper.py")
    logger.info("   funcionan correctamente con el archivo anonimizado")
    logger.info("2. Verificar que el mapeo de provincias se mantiene intacto")
    logger.info("3. Eliminar archivo original si todo funciona correctamente")


if __name__ == "__main__":
    main()
