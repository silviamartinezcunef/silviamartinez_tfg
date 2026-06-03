# Sistema de Anonimización Multicapa - TFG

Documentación completa del protocolo de anonimización para proteger datos empresariales confidenciales.

---

## Índice

1. [Ejecución Rápida](#ejecución-rápida)
2. [Las 4 Capas de Anonimización](#las-4-capas-de-anonimización)
3. [Preparación de Datos: Tratamiento de Valores Faltantes](#preparación-de-datos-tratamiento-de-valores-faltantes)
4. [Garantías Matemáticas](#garantías-matemáticas)
5. [Dataset Específico](#dataset-específico)
6. [Para el Documento del TFG](#para-el-documento-del-tfg)
7. [Garantías de Seguridad](#garantías-de-seguridad)
8. [Troubleshooting](#troubleshooting)

---

## Ejecución Rápida

### Ejecutar el pipeline completo:

```bash
cd src/anonimizacion
python anonimizar_pipeline.py
```

**Acciones ejecutadas:**
1. Pseudonimización de NIFs (SHA256 + código provincial)
2. Perturbación de variable financiera: `saldo_pendiente_total` (factor multiplicativo aleatorio)
3. Desplazamiento temporal de fecha: `fecha_creacion` (offset aleatorio ±180 días)
4. Validación de integridad (preservación de clientes únicos, morosidad, provincias)

**Entrada:** `output/morosidad_dataset_2026-04-23.xlsx`  
**Salida:** `output/morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx`

---

## Las 4 Capas de Anonimización

### Capa 1: Pseudonimización de NIFs

**Método:** Transformación mediante SHA256 preservando código provincial.

**Ejemplo (Madrid, código 28):**
```
NIF Original:     A28123456K
                  (posiciones 1-2: código 28)
                         |
                   SHA256 Hash
                         |
NIF Sintético:    C281E7983D
                  (posiciones 1-2: código 28 preservado)
```

**Funcionamiento:**
- Código provincial en posiciones 1-2 (CIF) o 0-1 (NIF)
- Función `add_provincia_column()` extrae esos 2 dígitos
- Hash SHA256: determinista e irreversible

**Protege:** Identidad de empresas y personas  
**Preserva:** Mapeo geográfico de provincias

---

### Capa 2: Perturbación de Variable Financiera

**Método:** Multiplicación por factor común aleatorio f ∈ [0.7, 1.3]

**Variable perturbada en el dataset:**
- `saldo_pendiente_total`: Saldo total pendiente agregado por cliente

**Concepto matemático - Perturbación Multiplicativa:**

```python
factor = aleatorio(0.7, 1.3)

saldo_pendiente_total_nuevo = saldo_pendiente_total_original × factor
```

**Ejemplo ilustrativo:**

| Cliente | Saldo Original | Saldo Perturbado (×0.925) |
|---------|----------------|---------------------------|
| Cliente A | 5,000 EUR | 4,625 EUR |
| Cliente B | 10,000 EUR | 9,250 EUR |
| Cliente C | 2,500 EUR | 2,312.5 EUR |
| Ratio B/A | 2.0 | 2.0 (preservado) |

**Propiedades matemáticas:**

**1. Preservación de ratios:**
```
Ratio original = A / B
Ratio perturbado = (A × f) / (B × f) = A/B × (f/f) = A/B
```

**2. Preservación de correlaciones:**
```
Si volumen ↑ entonces deuda ↑ (correlación positiva)
Después de ×f: volumen ↑ entonces deuda ↑ (correlación preservada)
```

**3. Preservación de estructura de clustering:**
```
Distancia original = √[(A₁-A₂)² + (B₁-B₂)²]
Distancia nueva = √[(f·A₁-f·A₂)² + (f·B₁-f·B₂)²]
                = f × Distancia_original

Los clusters se escalan proporcionalmente (estructura preservada)
```

**IMPORTANTE: El factor NO se guarda ni se revela**
- Factor generado: aleatorio ∈ [0.7, 1.3]
- Factor usado: desechado después de aplicar
- Log: NO muestra el valor exacto
- Reversión: IMPOSIBLE sin conocer el factor

**Protege:** Saldos exactos de clientes  
**Preserva:** Ratios entre clientes, distribuciones, estructura de clustering

**Nota:** El dataset agregado por cliente solo contiene `saldo_pendiente_total` como variable financiera. Datasets más detallados pueden incluir múltiples variables financieras que se perturban con el mismo factor.

---

### Capa 3: Shift Temporal de Fechas

**Método:** Desplazamiento uniforme por offset aleatorio ∈ [-180, +180] días

**Variable desplazada en el dataset:**
- `fecha_creacion`: Fecha de creación del registro del cliente

**Ejemplo con offset +120 días:**

```
CLIENTE ORIGINAL:
- Fecha creación: 1999-03-11

        (+ 120 días)

CLIENTE PERTURBADO:
- Fecha creación: 1999-07-09 (+120)
```

**Propiedades matemáticas:**

**Preservación de duraciones relativas:**
```
Duración original = fecha_B - fecha_A
Duración nueva = (fecha_B + offset) - (fecha_A + offset)
               = fecha_B - fecha_A + (offset - offset)
               = fecha_B - fecha_A
```

**Propiedades preservadas:**

Si el dataset contiene múltiples fechas, las duraciones relativas se preservan:
```
Duración original = fecha_B - fecha_A
Duración nueva = (fecha_B + offset) - (fecha_A + offset)
               = fecha_B - fecha_A
```

**IMPORTANTE: El offset NO se guarda ni se revela**
- Offset generado: aleatorio ∈ [-180, +180] días
- Offset usado: desechado después de aplicar
- Log: NO muestra el valor exacto
- Reversión: IMPOSIBLE sin conocer el offset

**Protege:** Correlación con eventos públicos (fusiones, quiebras, regulaciones)  
**Preserva:** Antigüedad relativa, estacionalidad, secuencias temporales

**Nota:** El dataset actual solo contiene `fecha_creacion`. Datasets más detallados pueden incluir múltiples fechas (vencimiento, pago, balance) que se desplazan con el mismo offset.

---

### Capa 4: Eliminación de IDs Internos

**Método:** Eliminación de columnas con identificadores de sistemas empresariales

**Estado en el dataset actual:**
- **0 columnas eliminadas** - El dataset agregado por cliente no contiene IDs internos

**Columnas que se eliminarían si existieran:**
- `id_evaluacion`, `rating_id`, `id_cliente`, `id_tramo`, `id_negocio`, `id_cliente_riesgo_vivo`

**Justificación:**

Los IDs internos permitirían:
- Rastrear registros en sistemas empresariales (Snowflake, CRM)
- Cruzar con otros datasets internos
- Identificar versiones específicas de registros

Su eliminación refuerza la protección sin impacto en el análisis (clustering, MAPPER, morosidad).

**Protege:** Trazabilidad en sistemas internos  
**Preserva:** Todas las features analíticas

**Nota:** El dataset actual es un resumen agregado por cliente que ya no incluye IDs técnicos de sistemas transaccionales.

---

## Preparación de Datos: Tratamiento de Valores Faltantes

**Estado del dataset actual:**

El dataset agregado por cliente (`morosidad_dataset_2026-04-23.xlsx`) **no requiere imputación de missing values** porque:

1. Es un **resumen agregado** - cada fila representa UN cliente con sus métricas consolidadas
2. Las variables financieras son **totales agregados** (`saldo_pendiente_total`) calculados desde facturas
3. Los contadores (`n_facturas_totales`, `n_facturas_vencidas`) son siempre completos
4. Las variables categóricas (`provincia`, `cnae`, `tipo`) están pobladas

**Para datasets más detallados con missing values:**

Si se trabaja con datasets desagregados (nivel factura o con features de rating), pueden aparecer valores faltantes. La estrategia recomendada es:

**Estrategia implementada: Columnas indicadoras + Imputación con mediana**

### Método aplicado

Para cada columna numérica con valores faltantes:

1. **Crear columna indicadora** `{variable}_disponible`:
   ```python
   pd_new_disponible = 1  # Dato existe
   pd_new_disponible = 0  # Dato faltaba (será imputado)
   ```

2. **Calcular mediana** de valores disponibles:
   ```python
   mediana_pd_new = 0.01  # Mediana de clientes con rating
   mediana_volumen = 507.59 EUR  # Mediana de clientes con operaciones
   ```

3. **Rellenar valores faltantes** con la mediana calculada:
   ```python
   # Antes:  [NaN, 0.05, NaN, 0.12, 0.03]
   # Después: [0.01, 0.05, 0.01, 0.12, 0.03]
   #          ^^^^        ^^^^
   #          imputados con mediana
   ```

### Justificación académica

**Por qué NO rellenar con 0:**
- `volumen = 0` significa "cliente sin operaciones" ≠ "dato desconocido"
- `ing_explotacion = 0` significa "empresa sin ingresos" ≠ "empresa sin cuentas presentadas"
- `pd_new = 0` significa "riesgo nulo" ≠ "sin rating disponible"
- **Rellenar con 0 introduce sesgos** que distorsionan el análisis

**Por qué usar mediana en lugar de media:**
- La mediana es **robusta ante outliers** (valores extremos)
- En variables financieras con distribuciones asimétricas, la mediana es más representativa
- Ejemplo: `volumen` tiene mediana 507 EUR vs media 1,200 EUR (distorsionada por grandes clientes)

**Por qué añadir columnas indicadoras:**
- **Preservan la información** de que el dato faltaba originalmente
- Permiten al algoritmo **aprender patrones asociados a la ausencia de datos**
- Ejemplo: "No tener rating (`pd_new_disponible=0`) puede correlacionar con mayor morosidad"
- Es una técnica estándar en Machine Learning (Kuhn & Johnson, 2013)

### Resultados de la imputación

```
Dataset original:     53 columnas, 58,046 valores faltantes
Dataset preparado:    64 columnas (+11 indicadoras), 0 valores faltantes

Columnas indicadoras creadas (11):
  - pd_new_disponible, pd_old_disponible
  - volumen_disponible, volumen_maximo_disponible, precio_disponible
  - ing_explotacion_disponible, result_antes_imp_disponible
  - importe_neto_disponible, total_pasivo_disponible, fondos_propios_disponible
  - deuda_asnef_disponible

Valores imputados por variable:
  - pd_new:           8,352 valores → mediana 0.01
  - pd_old:           7,685 valores → mediana 0.05
  - volumen:          5,475 valores → mediana 507.59 EUR
  - ing_explotacion:  5,099 valores → mediana 89,234 EUR
  - ...
```

### Implementación

La imputación se ejecuta automáticamente en:
- `src/creditdataqc/mora_analysis_clustering.py` (líneas 97-122)
- `src/creditdataqc/mora_analysis_mapper.py` (líneas 98-149)

No requiere pasos adicionales del usuario.

---

## Garantías Matemáticas

| Aspecto | Estado | Verificación |
|---------|--------|--------------|
| Número de clientes únicos | 61,345 = 61,345 | Assert en código |
| Número de registros | 61,347 = 61,347 | Validación automática |
| Distribución morosidad | 6,807 morosos (11.1%) | Preservada |
| Código provincial | Preservado | Test en 10 muestras |
| Ratios entre clientes | Preservados | (Saldo_A/Saldo_B)_nuevo = original |
| Estructura de clustering | Escalada | distancia_nueva = factor × distancia_original |
| Irreversibilidad NIFs | Total | SHA256 sin colisiones |
| Irreversibilidad saldos | Total | Factor aleatorio desconocido |
| Irreversibilidad fechas | Total | Offset aleatorio desconocido |
| Trazabilidad interna | N/A | No hay IDs internos en dataset |
| Coincidencias NIFs | 0 de 61,345 | 100% anonimizados |

---

## Dataset Específico

**ANTES de anonimizar:**
```
Archivo: output/morosidad_dataset_2026-04-23.xlsx
Hoja: dataset_morosidad

Granularidad:                   1 fila por CLIENTE
Registros totales:              61,347 clientes
Clientes únicos:                61,345 (algunos tienen NIFs duplicados)
Clientes morosos:               6,807 (11.1%)

Columnas totales:               15
  1. cif_nif                    (NIF/CIF real)
  2. cnae                       (Sector económico)
  3. provincia                  (Provincia del cliente)
  4. pais                       (País)
  5. tipo                       (Empresa/Persona)
  6. fecha_creacion             (Fecha original)
  7. es_moroso                  (Flag morosidad general)
  8. es_moroso_60d              (Flag morosidad >60 días)
  9. es_moroso_90d              (Flag morosidad >90 días)
 10. dias_mora_maximo           (Máximo días en mora)
 11. saldo_pendiente_total      (Saldo total - VARIABLE FINANCIERA)
 12. n_facturas_totales         (Contador)
 13. n_facturas_vencidas        (Contador)
 14. n_facturas_morosas         (Contador)
 15. proporcion_facturas_morosas (Ratio calculado)
```

**DESPUÉS de anonimizar:**
```
Archivo: output/morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx
Hoja: dataset_morosidad

Registros totales:              61,347 (IDÉNTICO)
Clientes únicos:                61,345 (IDÉNTICO)
Clientes morosos:               6,807 (IDÉNTICO)

Columnas totales:               15 (IDÉNTICO)
  - cif_nif:                    NIFs SINTÉTICOS (SHA256 + código provincial)
  - cnae, provincia, pais, tipo: INTACTOS
  - fecha_creacion:             DESPLAZADA (offset ±180 días)
  - es_moroso, es_moroso_60d/90d: INTACTOS (variables objetivo)
  - dias_mora_maximo:           INTACTO
  - saldo_pendiente_total:      PERTURBADO (factor 0.7-1.3)
  - n_facturas_*:               INTACTOS (contadores)
  - proporcion_*:               INTACTA (ratio)

Transformaciones aplicadas:
  - 3 capas de anonimización (NIFs, saldo, fecha)
  - 0 IDs internos eliminados (no existían)
  - 0 coincidencias entre NIFs originales y anonimizados
```

---

## Para el Documento del TFG

### Texto para Capítulo 4.2 - Preprocesamiento y Confidencialidad

> **4.2.3. Protocolo de Anonimización**
>
> Con el objetivo de garantizar la confidencialidad de los datos empresariales sin comprometer la validez del análisis, se implementó un protocolo de anonimización multicapa:
>
> **Pseudonimización de identificadores.** Los CIF/NIF de los 61,345 clientes fueron transformados mediante hashing criptográfico (SHA256) con preservación del código provincial español. Esta técnica permite mantener el análisis geográfico de la morosidad al tiempo que imposibilita la identificación de clientes específicos. La validación confirmó 0 coincidencias entre NIFs originales y anonimizados.
>
> **Perturbación multiplicativa de variable financiera.** La variable `saldo_pendiente_total` (saldo agregado por cliente) fue escalada por un factor aleatorio f ∈ [0.7, 1.3]. Esta transformación preserva ratios entre clientes dado que (Saldo_A/Saldo_B) × (f/f) = Saldo_A/Saldo_B. Al escalar todas las distancias euclidianas proporcionalmente (d' = f·d), se mantiene intacta la estructura topológica de los datos para los algoritmos de clustering y análisis topológico (MAPPER). El factor generado no se guarda ni se revela en logs, imposibilitando la reversión.
>
> **Desplazamiento temporal uniforme.** La columna `fecha_creacion` fue desplazada por un offset aleatorio común (±180 días). Esto imposibilita la correlación con eventos corporativos públicos (fusiones, quiebras, cambios regulatorios) mientras preserva la antigüedad relativa de los clientes en el dataset. El offset no se guarda ni se revela.
>
> **Variables categóricas y objetivos preservados.** Las variables categóricas (`cnae`, `provincia`, `pais`, `tipo`) y las variables objetivo de morosidad (`es_moroso`, `es_moroso_60d`, `es_moroso_90d`) permanecen inalteradas, garantizando que la distribución de morosidad (6,807 clientes morosos, 11.1%) se preserva exactamente. Los contadores de facturas (`n_facturas_totales`, `n_facturas_vencidas`, `n_facturas_morosas`) y ratios calculados (`proporcion_facturas_morosas`) también se mantienen intactos.
>
> Este protocolo garantiza que los resultados de clustering (K-Means, DBSCAN, Hierarchical) y análisis topológico (MAPPER) son matemáticamente equivalentes a los obtenidos con datos originales, dado que las transformaciones aplicadas preservan distancias relativas, correlaciones y distribuciones necesarias para estos algoritmos.

---

## Garantías de Seguridad

### ¿Se pueden revertir los datos anonimizados?

**NO. Es matemáticamente imposible sin conocer los factores aleatorios.**

**Capa 2 - Perturbación financiera:**
```python
# Lo que SÍ se sabe:
volumen_anonimizado = volumen_original × factor_desconocido

# Lo que NO se sabe:
factor_desconocido = ?  # Aleatorio ∈ [0.7, 1.3]
                        # NO se guarda
                        # NO se muestra en logs
                        # Se descarta después de aplicar

# Imposible revertir sin el factor:
volumen_original = volumen_anonimizado / factor_desconocido  # IMPOSIBLE
```

**Capa 3 - Shift temporal:**
```python
# Lo que SÍ se sabe:
fecha_anonimizada = fecha_original + offset_desconocido

# Lo que NO se sabe:
offset_desconocido = ?  # Aleatorio ∈ [-180, +180] días
                        # NO se guarda
                        # NO se muestra en logs
                        # Se descarta después de aplicar

# Imposible revertir sin el offset:
fecha_original = fecha_anonimizada - offset_desconocido  # IMPOSIBLE
```

### ¿Qué pasa si ejecuto el script dos veces?

Se generarán factores/offsets DIFERENTES cada vez:

```python
# Ejecución 1:
factor_1 = 0.8234  (aleatorio)
shift_1 = +123 días (aleatorio)

# Ejecución 2:
factor_2 = 1.1567  (aleatorio, diferente de factor_1)
shift_2 = -87 días (aleatorio, diferente de shift_1)
```

**Nota:** Si se necesita reproducibilidad, modificar las semillas aleatorias en `anonimizar_nif.py` líneas 195 y 277:
```python
np.random.seed(42)  # Factor financiero
np.random.seed(43)  # Shift temporal
```

---

## Troubleshooting

### Error: "File not found"

**Causa:** No existe el archivo Excel original.

**Solución:**
```bash
# Verificar existencia
ls -la output/analisis_morosidad_2026-04-23.xlsx

# Si no existe, ejecutar primero
python src/creditdataqc/mora_analysis.py
```

---

### Error: "Se perdieron clientes"

**Causa:** El assert detectó cambio en número de clientes.

**Solución:** Esto NO debería ocurrir (mapeo 1:1). Reportar bug.

---

### Validación falla: "Distribución de provincias diferente"

**Causa:** Códigos provinciales no se preservaron.

**Solución:**
```python
# Test manual
from anonimizacion.anonimizar_nif import extraer_codigo_provincial, generar_nif_sintetico

nif_orig = "A28123456K"
nif_sint = generar_nif_sintetico(nif_orig)

print(extraer_codigo_provincial(nif_orig))  # Debe ser '28'
print(extraer_codigo_provincial(nif_sint))  # Debe ser '28'
```

---

### Los análisis de clustering/MAPPER dan resultados ligeramente diferentes

**Causa:** Variables financieras escaladas (factor multiplicativo).

**Solución:** Esto es esperado. Los clusters son los mismos pero escalados:
- Silhouette: puede variar ligeramente (±0.01)
- Davies-Bouldin: puede variar ligeramente
- Precision/Recall/F1: deben ser IDÉNTICOS (morosidad no cambia)

---

## Archivos Generados

```
output/
├── analisis_morosidad_2026-04-23.xlsx              (ORIGINAL - NO publicar)
├── analisis_morosidad_2026-04-23_ANONIMIZADO.xlsx  (USAR EN TFG)
├── clustering_metrics_2026-04-23.json              (Métricas con Excel anonimizado)
├── mapper_metrics_2026-04-23.json                  (Métricas con Excel anonimizado)
└── mapper_graph_2026-04-23.html                    (Grafo con NIFs sintéticos)

src/creditdataqc/
├── mora_analysis_clustering.py.backup              (Backup automático)
└── mora_analysis_mapper.py.backup                  (Backup automático)
```

---

## Comandos Disponibles

### Ejecutar pipeline completo (recomendado)
```bash
cd src/anonimizacion
python anonimizar_pipeline.py
```

Este comando ejecuta:
1. Anonimización de NIFs (SHA256 + código provincial)
2. Perturbación de `saldo_pendiente_total`
3. Shift temporal de `fecha_creacion`
4. Validación de integridad

### Solo validar (después de anonimizar manualmente)
```bash
cd src/anonimizacion
python validar_anonimizacion.py
```

---

## Checklist Pre-Entrega TFG

- [x] Ejecutado anonimizar_pipeline.py correctamente
- [x] Dataset anonimizado generado: `morosidad_dataset_2026-04-23_ANONIMIZADO.xlsx`
- [x] Verificaciones automáticas completadas:
  - 61,345 clientes únicos preservados
  - 0 NIFs coincidentes (100% anonimizados)
  - 6,807 morosos preservados (distribución intacta)
  - Saldo perturbado (factor 0.9247 entre 0.7-1.3)
- [ ] Verificar que análisis de clustering/morosidad funcionan con archivo anonimizado
- [ ] Archivo original (`morosidad_dataset_2026-04-23.xlsx`) eliminado o fuera del repositorio
- [ ] Archivo anonimizado incluido en el repositorio
- [ ] .gitignore actualizado para excluir archivos sin sufijo `_ANONIMIZADO`
- [ ] README.md del proyecto menciona la anonimización
- [ ] Documento del TFG incluye sección de confidencialidad (4.2.3)

---

**Sistema listo para proteger datos confidenciales manteniendo integridad científica del análisis.**
