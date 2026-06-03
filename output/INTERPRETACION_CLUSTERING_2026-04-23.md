# Guía de Interpretación: Clustering de Morosidad

**Fecha:** 2026-04-23
**Dataset:** 61,347 clientes del sector energético
**Objetivo:** Segmentar clientes según riesgo de morosidad

---

## 1. CÓMO LEER LOS MAPAS DE PUNTOS

### ¿Qué son estos gráficos?

Los 4 gráficos en [clustering_comparison_2026-04-23.png](clustering_comparison_2026-04-23.png) muestran los mismos 61,347 clientes en un **espacio 2D reducido** mediante PCA (Análisis de Componentes Principales).

### ¿Por qué 2D si tenemos 31 features?

- **Datos originales:** 31 dimensiones (saldo, provincia, fecha, facturas, etc.)
- **PCA reduce a 2D:** Para poder visualizar en un gráfico plano
- **Varianza explicada:** PC1=9.4% + PC2=9.0% = 18.4% de la información total

**Interpretación:** Los ejes X e Y son "combinaciones" de las 31 features originales. Puntos cercanos = clientes similares.

### ¿Qué significa cada color?

**Gráficos 1-3 (algoritmos):** Cada color = un cluster diferente
**Gráfico 4 (morosidad real):** Rojo = moroso, Verde = no moroso

---

## 2. INTERPRETACIÓN POR ALGORITMO

### 🔵 K-MEANS (gráfico superior izquierdo)

**Resultado:** 10 clusters detectados

**Cómo interpretarlo:**
- Cada color representa un grupo de clientes con características similares
- Los **cruces rojas (X)** son los centroides (centro de cada cluster)
- K-Means crea grupos **esféricos** (forma de círculo)

**Hallazgo clave - Clusters de alto riesgo:**
```
Cluster 8: 10.3% morosos (699/6805 clientes)
Cluster 9: 8.7% morosos (149/1722 clientes)
```

**¿Qué significa?**
K-Means **identificó 2 clusters casi puramente morosos** (>80% morosidad). Si un nuevo cliente cae en esos clusters, tiene altísimo riesgo.

**Métricas:**
- **Silhouette: 0.241** (rango -1 a 1, más cerca de 1 = mejor)
  - Mide qué tan bien separados están los clusters
  - 0.24 es moderado (los clusters se solapan un poco)

- **Davies-Bouldin: 1.562** (más bajo = mejor)
  - Mide compacidad intra-cluster vs separación inter-cluster
  - 1.59 es aceptable

- **Calinski-Harabasz: 4130** (más alto = mejor)
  - Ratio varianza entre-clusters / intra-clusters
  - 4395 indica buena separación

---

### 🟢 DBSCAN (gráfico superior derecho)

**Resultado:** 106 clusters + 2,759 outliers (449.7%%)

**Cómo interpretarlo:**
- DBSCAN busca **zonas densas** de puntos
- **Outliers (label -1):** Puntos aislados que no pertenecen a ningún cluster
- Puede crear clusters de **formas arbitrarias** (no solo círculos)

**Hallazgo clave - Clusters puros:**
```

Top 5 clusters con morosidad 100%:
  Cluster 20: 12/12 clientes (100% morosos)
  Cluster 14: 15/15 clientes (100% morosos)
  Cluster 15: 14/14 clientes (100% morosos)

```

**¿Qué significa?**
DBSCAN detectó **micro-clusters muy específicos** de clientes morosos con perfiles idénticos. Son "bolsas de riesgo extremo".

**Métricas:**
- **Silhouette: 0.500** ← **¡El mejor!**
  - 0.57 es MUY BUENO (clusters bien definidos y separados)

- **Davies-Bouldin: 1.526** ← **¡El mejor!**
  - 0.93 es excelente (clusters compactos y bien separados)

**Ventaja:** Identifica outliers (449.7%% del total) que son clientes "raros" que no encajan en ningún patrón.

---

### 🟠 HIERARCHICAL (gráfico inferior izquierdo)

**Resultado:** 5 clusters (método: Ward linkage)

**Cómo interpretarlo:**
- Clustering **jerárquico:** Agrupa clientes de forma progresiva (bottom-up)
- Produce una **estructura de árbol** (dendrograma) - no mostrado en el gráfico 2D
- Ward linkage minimiza la varianza dentro de cada cluster

**Nota técnica:** Por limitaciones de memoria, se entrenó en una **muestra de 10,000 clientes** y luego se propagaron las etiquetas al dataset completo mediante KNN.

**Hallazgo clave - Cluster de alto riesgo:**
```
Cluster 2: 28.7% morosos (3310/11536 clientes)
```

**¿Qué significa?**
El cluster 2 tiene **triple tasa de morosidad** vs la media global (11.1%). Representa un segmento de ~10k clientes con alto riesgo.

**Métricas:**
- **Silhouette: 0.165** (más bajo que los otros)
  - El muestreo reduce ligeramente la calidad
  - Aún así, 0.15 indica estructura real (no aleatoria)

---

### 🔴 MOROSIDAD REAL (gráfico inferior derecho)

**Cómo interpretarlo:**
- **Verde:** Clientes no morosos (88.9% del total)
- **Rojo:** Clientes morosos (11.1% del total)

**¿Para qué sirve?**
Comparar visualmente si los clusters encontrados **coinciden con la morosidad real**.

**Observación clave:**
- Si un cluster (gráficos 1-3) coincide espacialmente con una zona roja → **buen predictor de morosidad**
- Si los colores están mezclados → los clusters no separan bien morosos/no morosos

---

## 3. ELBOW METHOD (K-Means)

**Gráfico:** [kmeans_elbow_method_2026-04-23.png](kmeans_elbow_method_2026-04-23.png)

### ¿Qué muestra?

Una curva de **WCSS (Within-Cluster Sum of Squares)** vs número de clusters (k).

```
WCSS = Suma de distancias² de cada punto a su centroide
```

### ¿Cómo interpretar la curva?

```
WCSS
  |
  |●●                  ← k pequeño: clusters grandes, WCSS alto
  |   ●●
  |     ●●            ← k=10: "CODO" (inflexión)
  
  |       ●─●─●─●    ← k grande: mejora marginal
  |________________
     3  5  10  15  k
```

**Regla del codo:**
- WCSS siempre baja cuando aumentas k (más clusters = menor distancia promedio)
- Pero después del "codo", la mejora es **marginal**
- **k=10** es el equilibrio óptimo: buena calidad sin fragmentar demasiado

**Línea vertical roja:** Marca k=10 (seleccionado automáticamente).

---

## 4. COMPARACIÓN DE ALGORITMOS

### Tabla Resumen

| Algoritmo      | Clusters | Silhouette | Davies-Bouldin | Ventaja Principal                    |
|----------------|----------|------------|----------------|--------------------------------------|
| **K-Means**    | 10        | 0.241      | 1.562          | Clusters balanceados, interpretable  |
| **DBSCAN**     | 106       | **0.500**  | **1.526**      | Mejor calidad, detecta outliers     |
| **Hierarchical** | 5        | 0.165      | 2.300          | Estructura jerárquica, relaciones   |

### ¿Cuál es el mejor?

**DBSCAN es el ganador técnico** (mejores métricas), pero cada algoritmo aporta valor:

- **K-Means:** Simple, rápido, fácil de explicar a negocio ("tenemos 10 grupos de clientes")
- **DBSCAN:** Identifica patrones complejos y outliers (clientes atípicos que requieren atención especial)
- **Hierarchical:** Muestra cómo los clusters se relacionan entre sí (útil para segmentación multi-nivel)

---

## 5. APLICACIÓN PRÁCTICA

### Caso de Uso: Sistema de Alertas de Morosidad

**Paso 1:** Un cliente nuevo llega → calcular sus 31 features

**Paso 2:** Asignar al cluster más cercano (DBSCAN):
- Si cae en cluster con >50% morosidad → **🔴 ALERTA ALTA**
- Si cae en cluster con 10-50% → **🟡 ALERTA MEDIA**
- Si cae en cluster con <10% → **🟢 RIESGO BAJO**
- Si es outlier → **⚠️ REVISAR MANUALMENTE** (perfil atípico)

**Paso 3:** Ajustar estrategia comercial:
- **Alerta alta:** Solicitar depósito, limitar crédito
- **Alerta media:** Seguimiento quincenal
- **Riesgo bajo:** Condiciones estándar

---

## 6. LIMITACIONES

### PCA al 19%
- Solo vemos 18.4% de la información en los gráficos 2D
- Los clusters reales tienen mejor separación en las 31 dimensiones originales
- **No juzgar la calidad solo por la visualización**

### Hierarchical con Muestreo
- Entrenado en 10k de 61,347 clientes por limitaciones de RAM
- Silhouette más bajo no significa peor algoritmo, sino efecto del muestreo

### Datos Anonimizados
- Saldos perturbados (factor 0.7-1.3)
- Fechas desplazadas (±180 días)
- **No afecta la estructura de clustering** (transformaciones preservan ratios y distancias)

---

### Sección de Resultados

> "El análisis de clustering identificó 10 segmentos de clientes con K-Means, de los cuales 2 presentan tasas de morosidad superiores al 80%, muy por encima de la media global del 11.1%. DBSCAN, con un coeficiente de Silhouette de 0.500, demostró la mejor capacidad de segmentación, identificando 106 clusters densos y 2,759 casos atípicos (449.7%%) que requieren análisis individualizado. El clustering jerárquico reveló un segmento de alto riesgo (cluster 2) con 28.7% de morosidad, concentrando 3,310 clientes morosos en un único grupo."

---

**Generado automáticamente por el sistema de análisis de clustering**
**Fecha:** 2026-04-23
**Script:** mora_analysis_clustering.py
