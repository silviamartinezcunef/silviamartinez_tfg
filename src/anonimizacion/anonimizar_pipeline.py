#!/usr/bin/env python
"""
Pipeline completo de anonimización para TFG.

Ejecuta en secuencia:
1. Anonimización de NIFs
2. Validación de integridad
3. Actualización de rutas en scripts

Uso:
    python anonimizar_pipeline.py
"""

import sys
from pathlib import Path

# Añadir src al path y la propia carpeta anonimizacion
sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from creditdataqc._log import get_logger
from anonimizar_nif import anonimizar_excel_morosidad
from validar_anonimizacion import validar_anonimizacion

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parents[2]  # src/anonimizacion/ → raíz
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"
SRC_DIR = PROJECT_ROOT / "src" / "creditdataqc"


def main():
    """
    Ejecuta pipeline completo de anonimización.
    """
    logger.info("="*70)
    logger.info("PIPELINE DE ANONIMIZACIÓN PARA TFG")
    logger.info("="*70)

    # Configuración
    fecha = '2026-04-23'
    input_file = DATA_OUTPUT_DIR / f"morosidad_dataset_{fecha}.xlsx"
    output_file = DATA_OUTPUT_DIR / f"morosidad_dataset_{fecha}_ANONIMIZADO.xlsx"

    # Paso 0: Verificar existencia del archivo original
    logger.info(f"\n[Paso 0/3] Verificando archivos de entrada...")
    if not input_file.exists():
        logger.error(f"❌ Archivo no encontrado: {input_file}")
        logger.info(f"Archivos disponibles en {DATA_OUTPUT_DIR}:")
        for f in DATA_OUTPUT_DIR.glob("morosidad_dataset_*.xlsx"):
            logger.info(f"  - {f.name}")
        return 1

    logger.info(f"✓ Archivo de entrada: {input_file.name}")

    # Paso 1: Anonimización
    logger.info(f"\n[Paso 1/3] Anonimizando NIFs...")
    logger.info("-" * 70)
    try:
        df_anonimizado = anonimizar_excel_morosidad(
            input_file=input_file,
            output_file=output_file,
            guardar_mapeo=False  # No guardar mapeo por seguridad
        )
        logger.info("✓ Anonimización completada")
    except Exception as e:
        logger.error(f"❌ Error durante anonimización: {e}", exc_info=True)
        return 1

    # Paso 2: Validación
    logger.info(f"\n[Paso 2/3] Validando integridad...")
    logger.info("-" * 70)
    try:
        exito_validacion = validar_anonimizacion(input_file, output_file)
        if not exito_validacion:
            logger.error("❌ Validación falló - revisar errores arriba")
            return 1
        logger.info("✓ Validación completada")
    except Exception as e:
        logger.error(f"❌ Error durante validación: {e}", exc_info=True)
        return 1

    # Paso 3: Resumen final
    logger.info(f"\n[Paso 3/3] Resumen")
    logger.info("-" * 70)
    logger.info(f"Archivo anonimizado: {output_file.name}")
    logger.info(f"Clientes únicos: {df_anonimizado['cif_nif'].nunique()}")
    logger.info(f"Total registros: {len(df_anonimizado)}")
    logger.info(f"NIFs pseudonimizados: Sí (SHA256)")
    logger.info(f"Códigos provinciales preservados: Sí")

    # Instrucciones finales
    logger.info("\n" + "="*70)
    logger.info("PIPELINE COMPLETADO EXITOSAMENTE")
    logger.info("="*70)
    logger.info("\nPROXIMOS PASOS:")
    logger.info("\n1. Ejecutar análisis con datos anonimizados:")
    logger.info("   python src/creditdataqc/mora_analysis_clustering.py")
    logger.info("   python src/creditdataqc/mora_analysis_mapper.py")
    logger.info("   python src/creditdataqc/comparar_metodos.py")
    logger.info("\n2. Verificar que los resultados son idénticos a los originales")
    logger.info("\n3. (Opcional) Eliminar archivo original:")
    logger.info(f"   del {input_file.name}")

    logger.info("\nIMPORTANTE PARA EL TFG:")
    logger.info("   - Usar SOLO archivos con sufijo '_ANONIMIZADO'")
    logger.info("   - NO incluir archivos 'MAPEO_CONFIDENCIAL_*' en el repositorio")
    logger.info("   - Verificar que no quedan NIFs reales en logs o notebooks")

    logger.info("\nDocumentación completa: README.md")

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
