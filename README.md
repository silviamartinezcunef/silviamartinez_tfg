# Análisis Topológico de Datos Aplicado a la Detección de Morosidad

**Trabajo de Fin de Grado - Ingeniería Matemática**  
**Autora:** Silvia Martínez  
**Universidad:** CUNEF Universidad  

## Descripción del Proyecto

Este repositorio contiene el código completo del TFG que compara **métodos tradicionales de clustering** (K-Means, DBSCAN, Hierarchical) con técnicas avanzadas de **Análisis Topológico de Datos (TDA)**, específicamente el algoritmo **MAPPER**, aplicados a la detección y segmentación de clientes morosos en el sector energético.

El análisis trabaja con un dataset real anonimizado de **61,347 clientes**, incluyendo variables financieras, geográficas y temporales. El objetivo es identificar patrones de morosidad y segmentar clientes según su riesgo crediticio.

## Estructura del Repositorio

```
clusteringVSmapper/
├── src/
│   ├── anonimizacion/              # Pipeline de anonimización de datos
│   │   ├── anonimizar_nif.py       # Pseudonimización de NIFs (SHA-256)
│   │   ├── anonimizar_pipeline.py  # Pipeline completo de anonimización
│   │   └── validar_anonimizacion.py # Validación de integridad post-anonimización
│   │
│   └── creditdataqc/               # Módulo principal de análisis
│       ├── boxplots_eda.py         # Análisis exploratorio con boxplots (Sección 4.3)
│       ├── persistencia_homologica.py  # Diagramas de persistencia (Sección 4.5)
│       ├── mora_analysis_clustering.py # Clustering tradicional (K-Means, DBSCAN, Hierarchical)
│       ├── comparar_metodos.py     # Comparación cuantitativa Clustering vs MAPPER
│       ├── mapper_grafo_estatico.py # Implementación MAPPER con grafo interactivo
│       ├── graficos_clustering.py  # Visualizaciones PCA de clusters
│       ├── elbow_k30.py            # Método del codo para selección de k
│       └── templates/
│           └── mapper_ui.js        # Interfaz JavaScript para grafo MAPPER interactivo
│
└── output/                         # Resultados y visualizaciones
    ├── morosidad_dataset_*_ANONIMIZADO.xlsx  # Dataset anonimizado
    ├── boxplots_morosidad.pdf      # Boxplots comparativos morosos vs no morosos
    ├── persistencia_morosidad.pdf  # Diagrama de persistencia homológica
    ├── clustering_comparison_*.png # Comparación visual de algoritmos
    ├── kmeans_elbow_method_*.png   # Gráfico del método del codo
    ├── clustering_metrics_*.json   # Métricas cuantitativas clustering
    ├── mapper_metrics_*.json       # Métricas cuantitativas MAPPER
    ├── informe_comparativo_*.xlsx  # Informe comparativo completo
    └── mapper_graph_interactive.html # Grafo MAPPER interactivo con visualización de clientes
```

## Funcionalidades Principales

### 1. Pipeline de Anonimización (`src/anonimizacion/`)

Protección de datos sensibles mediante:
- **Pseudonimización de NIFs/CIFs:** Hashing SHA-256 + código provincial
- **Perturbación de saldos:** Factor aleatorio (0.7-1.3)
- **Desplazamiento temporal:** ±180 días en fechas
- **Validación automática:** Verificación de integridad estadística

**Ejecución:**
```bash
python src/anonimizacion/anonimizar_pipeline.py
```

### 2. Análisis Exploratorio de Datos (EDA)

#### Boxplots Comparativos (`boxplots_eda.py`)
Visualización de 6 variables financieras clave comparando morosos vs no morosos:
- Saldo pendiente total (escala log)
- Número de facturas totales/vencidas/morosas
- Proporción de facturas morosas
- Días de mora máximo

**Ejecución:**
```bash
python src/creditdataqc/boxplots_eda.py
```

### 3. Clustering Tradicional (`mora_analysis_clustering.py`)

Implementación de 3 algoritmos de clustering con métricas de validación:

#### K-Means
- **Método:** Particional basado en centroides (Lloyd, 1982)
- **Selección de k:** Método del codo (k=10 óptimo)
- **Resultado:** 10 clusters, Silhouette=0.24
- **Hallazgo:** 2 clusters con >80% morosidad

#### DBSCAN
- **Método:** Basado en densidad (Ester et al., 1996)
- **Parámetros:** eps=2.0, min_samples=10
- **Resultado:** 152 clusters + 5.2% outliers
- **Hallazgo:** Silhouette=0.57 (mejor calidad)

#### Hierarchical/Agglomerative
- **Método:** Jerárquico con Ward linkage
- **Configuración:** 5 clusters, muestreo de 10k clientes
- **Resultado:** Cluster de alto riesgo con 34% morosidad

**Características:**
- Preprocesamiento: 31 features (numéricas, temporales, categóricas con one-hot encoding)
- Normalización: StandardScaler (z-score)
- Métricas: Silhouette, Davies-Bouldin, Calinski-Harabasz
- Análisis de morosidad por cluster
- Visualización PCA 2D

**Ejecución:**
```bash
python src/creditdataqc/mora_analysis_clustering.py
```

### 4. Análisis Topológico de Datos (TDA)

#### Persistencia Homológica (`persistencia_homologica.py`)
Cálculo de características topológicas mediante complejos de Vietoris-Rips:
- **H0:** Componentes conexas (clusters naturales)
- **H1:** Huecos 1-dimensionales (ciclos en los datos)
- **Submuestreo:** 2000 clientes estratificados (limitación computacional)
- **Librería:** `ripser` (Python)

**Ejecución:**
```bash
python src/creditdataqc/persistencia_homologica.py
```

#### MAPPER (`mapper_grafo_estatico.py`)
Construcción de grafo topológico interactivo:
- **Lens function:** PCA a 2 dimensiones
- **Cubrimiento:** n_cubes=15, overlap=30%
- **Clustering interno:** DBSCAN por cubo
- **Visualización:** Grafo HTML interactivo con D3.js
- **Características del grafo:**
  - Nodos coloreados por tasa de morosidad
  - Tamaño proporcional a número de clientes
  - Modal interactivo con lista completa de clientes por nodo
  - Descarga CSV de clientes por nodo
  - Scroll optimizado para listas largas

**Ejecución:**
```bash
python src/creditdataqc/mapper_grafo_estatico.py
```

### 5. Comparación Cuantitativa (`comparar_metodos.py`)

Informe comparativo exhaustivo entre Clustering Tradicional y MAPPER:
- **Métricas de calidad:** Silhouette, Davies-Bouldin, Calinski-Harabasz
- **Capacidad predictiva:** Precision, Recall, F1-Score por algoritmo
- **Análisis cualitativo:** Ventajas/desventajas de cada enfoque
- **Recomendaciones:** Guía de uso según caso de aplicación
- **Top clusters:** Identificación de segmentos de alto riesgo con features característicos

**Output:** Archivo Excel multi-hoja con:
1. Resumen ejecutivo
2. Comparación cuantitativa
3. Análisis cualitativo
4. Recomendaciones de uso
5-7. Top 3 clusters de alto riesgo por algoritmo

**Ejecución:**
```bash
python src/creditdataqc/comparar_metodos.py
```

## Requisitos del Sistema

### Dependencias Python
```
pandas >= 1.5.0
numpy >= 1.23.0
scikit-learn >= 1.2.0
matplotlib >= 3.6.0
seaborn >= 0.12.0
openpyxl >= 3.0.0
ripser >= 0.6.0
kmapper >= 2.0.0
networkx >= 2.8
```

### Instalación
```bash
pip install pandas numpy scikit-learn matplotlib seaborn openpyxl ripser kmapper networkx
```

## Resultados Principales

### Comparación de Algoritmos

| Algoritmo      | Clusters | Silhouette | Davies-Bouldin | F1-Score | Ventaja Principal |
|----------------|----------|------------|----------------|----------|-------------------|
| **K-Means**    | 10       | 0.240      | 1.590          | 0.XXX    | Rápido, interpretable |
| **DBSCAN**     | 152      | **0.570**  | **0.930**      | 0.XXX    | Mejor calidad, detecta outliers |
| **Hierarchical** | 5      | 0.150      | 2.100          | 0.XXX    | Estructura jerárquica |
| **MAPPER**     | ~80 nodos| N/A        | N/A            | 0.XXX    | Visualización topológica |

### Hallazgos Clave
1. **K-Means:** Identificó 2 clusters con >80% morosidad (clusters 8 y 9)
2. **DBSCAN:** Detectó 5.2% outliers (clientes atípicos) con 152 micro-clusters
3. **Hierarchical:** Cluster 2 con 34% morosidad (triple de la media global 11.1%)
4. **MAPPER:** Reveló caminos de transición gradual entre clientes sanos y morosos

## Aplicación Práctica

### Sistema de Alertas de Morosidad
1. **Cálculo de features:** Preprocesar nuevo cliente (31 features)
2. **Asignación a cluster:** Usar modelo DBSCAN (mejor Silhouette)
3. **Nivel de alerta:**
   - 🔴 **Alta:** Tasa morosidad cluster >50%
   - 🟡 **Media:** Tasa 10-50%
   - 🟢 **Baja:** Tasa <10%
   - ⚠️ **Outlier:** Revisar manualmente (perfil atípico)
4. **Acción comercial:** Ajustar límite de crédito, frecuencia de seguimiento

## Limitaciones

1. **Visualización PCA:** Solo 19% varianza explicada en 2D (los clusters reales son mejores en 31D)
2. **Hierarchical con muestreo:** Entrenado en 10k de 61k clientes por limitaciones de RAM
3. **Persistencia homológica:** Submuestreo a 2k clientes (Vietoris-Rips O(n³) inviable en dataset completo)
4. **Datos anonimizados:** Perturbaciones no afectan estructura de clustering pero impiden reproducir valores exactos

## Referencias Teóricas

- **K-Means:** Lloyd, S. (1982). *Least squares quantization in PCM.*
- **DBSCAN:** Ester, M., et al. (1996). *A density-based algorithm for discovering clusters in large spatial databases with noise.*
- **Hierarchical:** Ward, J. H. (1963). *Hierarchical grouping to optimize an objective function.*
- **TDA/MAPPER:** Singh, G., Mémoli, F., & Carlsson, G. (2007). *Topological methods for the analysis of high dimensional data sets and 3D object recognition.*
- **Persistent Homology:** Edelsbrunner, H., & Harer, J. (2008). *Persistent homology — a survey.*

## Contacto

**Silvia Martínez**  
Ingeniería Matemática, CUNEF Universidad  
Repositorio: [github.com/silviamartinezcunef/silviamartinez_tfg](https://github.com/silviamartinezcunef/silviamartinez_tfg)

---

**Nota:** Este proyecto utiliza datos reales anonimizados del sector energético español. Todos los NIFs/CIFs están pseudonimizados mediante SHA-256 y los valores financieros perturbados para proteger la confidencialidad.
