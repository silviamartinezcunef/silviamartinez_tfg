"""
Entry point for the package.

Ejecuta el análisis de morosidad comparando la fórmula BC contra
el sistema Neuron Pro.
"""

import sys
from pathlib import Path
import pandas as pd

from creditdataqc.config._config import AppConfig
from creditdataqc._log import get_logger
from creditdataqc.mora_analysis import run_morosidad_analysis

logger = get_logger(__name__)


def main():
    """
    Punto de entrada principal del análisis de morosidad.
    """
    try:
        logger.info("Iniciando creditdataqc")
        logger.info(f"Configuración: {AppConfig.run.env}")

        # Ejecutar análisis de morosidad
        # Por defecto analiza todos los clientes, ajusta limit_clientes para testing
        # reportdate = bday-1 (día hábil anterior a hoy)
        # reportdate = (pd.Timestamp.today() - pd.tseries.offsets.BDay(1)).strftime('%Y-%m-%d')
        reportdate = '2026-04-23'  # Fecha fija para testing

        df_final, stats = run_morosidad_analysis(
            reportdate=reportdate,
            max_deuda=2000,
            max_dias=60,
            max_periodos=3,
            limit_clientes=None 
        )

        logger.info("Análisis completado exitosamente")
        return 0

    except Exception as e:
        logger.error(f"Error en ejecución: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
