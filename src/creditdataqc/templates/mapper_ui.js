/**
 * MAPPER Interactive UI - JavaScript Template
 *
 * Este archivo contiene toda la funcionalidad interactiva del grafo MAPPER.
 * Es inyectado dinámicamente en el HTML generado por kmapper.
 *
 * Funcionalidades:
 * - Panel modal con detalles de nodos
 * - Interpretación automática de perfiles de riesgo
 * - Event listeners para clicks y hover en nodos
 * - Búsqueda robusta de elementos SVG
 *
 * Placeholders que Python reemplaza:
 * - {{NODOS_INFO_PLACEHOLDER}} → JSON con información de todos los nodos
 */

// ============================================================================
// DATOS: Información de cada nodo (inyectado por Python)
// ============================================================================
const nodosInfo = {{NODOS_INFO_PLACEHOLDER}};

// ============================================================================
// UI: Crear panel modal y overlay
// ============================================================================

// Agregar estilos CSS para scrollbars personalizados
const styleHTML = `
<style>
    /* Estilos para el scrollbar en la lista de clientes */
    [id^="lista-clientes-"] {
        scrollbar-width: thin;
        scrollbar-color: #3498db #ecf0f1;
    }

    [id^="lista-clientes-"]::-webkit-scrollbar {
        width: 12px;
    }

    [id^="lista-clientes-"]::-webkit-scrollbar-track {
        background: #ecf0f1;
        border-radius: 10px;
    }

    [id^="lista-clientes-"]::-webkit-scrollbar-thumb {
        background: #3498db;
        border-radius: 10px;
        border: 2px solid #ecf0f1;
    }

    [id^="lista-clientes-"]::-webkit-scrollbar-thumb:hover {
        background: #2980b9;
    }

    /* Estilos para el contenedor del panel */
    #panel-contenido::-webkit-scrollbar {
        width: 10px;
    }

    #panel-contenido::-webkit-scrollbar-track {
        background: #f1f1f1;
    }

    #panel-contenido::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 5px;
    }

    #panel-contenido::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
</style>
`;

const panelHTML = `
<div id="panel-detalles" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
     background: white; border: 3px solid #3498db; border-radius: 15px;
     padding: 0; width: 900px; max-width: 95vw; max-height: 85vh; overflow: hidden;
     box-shadow: 0 10px 40px rgba(0,0,0,0.3); z-index: 10000; display: none;
     font-family: 'Segoe UI', Arial, sans-serif;">

    <div id="panel-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
         color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h2 style="margin: 0; font-size: 22px; font-weight: 600;">🔍 Análisis del Nodo</h2>
            <p style="margin: 5px 0 0 0; font-size: 13px; opacity: 0.9;">Clientes con características similares</p>
        </div>
        <button onclick="document.getElementById('panel-detalles').style.display='none'"
                style="background: rgba(255,255,255,0.2); color: white; border: none; border-radius: 50%;
                width: 35px; height: 35px; cursor: pointer; font-size: 20px; font-weight: bold;
                transition: all 0.3s;">✕</button>
    </div>

    <div id="panel-contenido" style="padding: 20px; overflow-y: auto; max-height: calc(85vh - 100px); overflow-x: hidden;"></div>
</div>

<div id="panel-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%;
     background: rgba(0,0,0,0.5); z-index: 9999; display: none;"
     onclick="document.getElementById('panel-detalles').style.display='none'; this.style.display='none';"></div>
`;

// Insertar estilos y panel en el documento
document.head.insertAdjacentHTML('beforeend', styleHTML);
document.body.insertAdjacentHTML('beforeend', panelHTML);

// ============================================================================
// LÓGICA DE NEGOCIO: Interpretar perfil de riesgo
// ============================================================================

/**
 * Analiza las características de un cluster y genera razones interpretables.
 *
 * @param {Object} stats - Estadísticas del cluster (promedio, min, max de features)
 * @param {number} morosidadPct - Porcentaje de clientes morosos en el cluster
 * @returns {Array<string>} Lista de razones con emojis e interpretación
 */
function interpretarPerfil(stats, morosidadPct) {
    const razones = [];

    // Interpretar PD (Probability of Default)
    if (stats.pd_new && stats.pd_new.promedio !== undefined) {
        const pd = stats.pd_new.promedio;
        const pdPct = (pd * 100).toFixed(2);
        if (pd > 0.05) {
            razones.push("🔴 <strong>Riesgo crediticio alto</strong>: PD promedio de " + pdPct + "% (>5%)");
        } else if (pd > 0.02) {
            razones.push("🟡 <strong>Riesgo crediticio moderado</strong>: PD promedio de " + pdPct + "% (2-5%)");
        } else {
            razones.push("🟢 <strong>Riesgo crediticio bajo</strong>: PD promedio de " + pdPct + "% (<2%)");
        }
    }

    // Interpretar volumen de negocio
    if (stats.volumen && stats.volumen.promedio !== undefined) {
        const vol = stats.volumen.promedio;
        const volStr = vol.toLocaleString('es-ES', {maximumFractionDigits: 0});
        if (vol < 5000) {
            razones.push("⚠️ <strong>Actividad muy baja</strong>: Volumen promedio " + volStr + " €/año");
        } else if (vol < 50000) {
            razones.push("📊 <strong>Actividad moderada</strong>: Volumen promedio " + volStr + " €/año");
        } else {
            razones.push("💼 <strong>Alta actividad comercial</strong>: Volumen promedio " + volStr + " €/año");
        }
    }

    // Interpretar deuda ASNEF
    if (stats.deuda_asnef && stats.deuda_asnef.promedio !== undefined) {
        const deuda = stats.deuda_asnef.promedio;
        const deudaStr = deuda.toLocaleString('es-ES', {maximumFractionDigits: 0});
        if (deuda > 5000) {
            razones.push("🚨 <strong>Deuda registrada alta</strong>: Promedio " + deudaStr + " € en ASNEF");
        } else if (deuda > 1000) {
            razones.push("⚠️ <strong>Deuda registrada moderada</strong>: Promedio " + deudaStr + " € en ASNEF");
        } else if (deuda > 0) {
            razones.push("ℹ️ <strong>Deuda registrada mínima</strong>: Promedio " + deudaStr + " € en ASNEF");
        } else {
            razones.push("✅ <strong>Sin deuda registrada</strong>: 0 € en ASNEF");
        }
    }

    // Interpretar límite de crédito
    if (stats.limite_total_concedido && stats.limite_total_concedido.promedio !== undefined) {
        const limite = stats.limite_total_concedido.promedio;
        const limiteStr = limite.toLocaleString('es-ES', {maximumFractionDigits: 0});
        if (limite < 5000) {
            razones.push("🔒 <strong>Límite restringido</strong>: Promedio " + limiteStr + " € (<5k)");
        } else if (limite < 50000) {
            razones.push("💳 <strong>Límite estándar</strong>: Promedio " + limiteStr + " € (5-50k)");
        } else {
            razones.push("💎 <strong>Límite amplio</strong>: Promedio " + limiteStr + " € (>50k)");
        }
    }

    // Interpretar tasa de morosidad del cluster
    if (morosidadPct > 25) {
        razones.push("🔴💓 <strong>Cluster de muy alto riesgo</strong>: " + morosidadPct.toFixed(1) + "% de morosos");
    } else if (morosidadPct > 15) {
        razones.push("🔴 <strong>Cluster de alto riesgo</strong>: " + morosidadPct.toFixed(1) + "% de morosos");
    } else if (morosidadPct > 5) {
        razones.push("🟡 <strong>Zona de vigilancia</strong>: " + morosidadPct.toFixed(1) + "% de morosos");
    } else if (morosidadPct > 0) {
        razones.push("🟢 <strong>Cluster sano</strong>: Solo " + morosidadPct.toFixed(1) + "% de morosos");
    } else {
        razones.push("🟢 <strong>Cluster sin morosos</strong>: 0% de morosidad");
    }

    return razones;
}

// ============================================================================
// GENERAR CONTENIDO: HTML dinámico del panel modal
// ============================================================================

/**
 * Genera y muestra el panel modal con detalles completos de un nodo.
 *
 * @param {string} nodeId - ID del nodo clickeado
 */
function mostrarDetallesNodo(nodeId) {
    const info = nodosInfo[nodeId];
    if (!info) return;

    const panel = document.getElementById('panel-detalles');
    const overlay = document.getElementById('panel-overlay');
    const contenido = document.getElementById('panel-contenido');

    // Color según tasa de morosidad
    const colorMora = info.morosidad_pct > 10 ? '#e74c3c' : info.morosidad_pct > 5 ? '#f39c12' : '#27ae60';

    // Interpretar perfil del cluster
    const razones = interpretarPerfil(info.stats, info.morosidad_pct);

    // Generar HTML completo
    let html = `
        <!-- Resumen del nodo -->
        <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
             border-radius: 10px; padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">IDENTIFICADOR</div>
                    <div style="font-size: 24px; font-weight: bold; color: #2c3e50;">Nodo ${nodeId}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">CLIENTES</div>
                    <div style="font-size: 32px; font-weight: bold; color: #3498db;">${info.n_clientes}</div>
                </div>
            </div>
            <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid rgba(255,255,255,0.5);">
                <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 5px;">TASA DE MOROSIDAD</div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="flex: 1; background: #ecf0f1; border-radius: 10px; height: 20px; overflow: hidden;">
                        <div style="background: ${colorMora}; height: 100%; width: ${info.morosidad_pct}%;
                             transition: width 0.5s ease;"></div>
                    </div>
                    <div style="font-size: 24px; font-weight: bold; color: ${colorMora};">
                        ${info.morosidad_pct.toFixed(1)}%
                    </div>
                </div>
            </div>
        </div>

        <!-- Por qué están agrupados -->
        <h3 style="color: #2c3e50; margin: 25px 0 15px 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px;"> </span> ¿Por qué están en el mismo grupo?
        </h3>
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px; padding: 15px; margin-bottom: 20px;">
            <p style="margin: 0 0 10px 0; color: #856404; font-size: 14px; line-height: 1.6;">
                Estos clientes comparten características similares que los hacen un perfil homogéneo:
            </p>
            ${razones.map(r => '<div style="margin: 8px 0; padding: 8px; background: white; border-radius: 5px; font-size: 13px;">' + r + '</div>').join('')}
        </div>

        <!-- Características numéricas -->
        <h3 style="color: #2c3e50; margin: 25px 0 15px 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px;">📊</span> Valores Promedio
        </h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
    `;

    // Mapeo de nombres técnicos a labels amigables
    const featureLabels = {
        'pd_new': ['PD ACTUAL', '%', 100],
        'pd_old': ['PD ANTERIOR', '%', 100],
        'volumen': ['VOLUMEN', '€', 1],
        'volumen_maximo': ['VOLUMEN MÁXIMO', '€', 1],
        'precio': ['PRECIO', '€', 1],
        'limite_total_concedido': ['LÍMITE CRÉDITO', '€', 1],
        'limite_disponible_ge': ['LÍMITE DISPONIBLE', '€', 1],
        'deuda_asnef': ['DEUDA ASNEF', '€', 1],
        'asnef': ['ASNEF FLAG', '', 1],
        'concurso': ['CONCURSO', '', 1],
        'burofax': ['BUROFAX', '', 1],
        'gastos_financieros': ['GASTOS FINANCIEROS', '€', 1],
        'ing_explotacion': ['ING. EXPLOTACIÓN', '€', 1],
        'result_antes_imp': ['RESULTADO', '€', 1],
        'importe_neto': ['IMPORTE NETO', '€', 1],
        'total_pasivo': ['PASIVO TOTAL', '€', 1],
        'fondos_propios': ['FONDOS PROPIOS', '€', 1],
        'riesgo_vivo_power': ['RIESGO POWER', '€', 1],
        'riesgo_vivo_gas': ['RIESGO GAS', '€', 1],
        'volumen_riesgo': ['VOLUMEN RIESGO', '€', 1],
        'riesgo_vivo_power_falcon': ['RIESGO FALCON', '€', 1],
        'riesgo_vivo_eficiencia': ['RIESGO EFICIENCIA', '€', 1]
    };

    // Generar tarjetas dinámicamente para cada feature
    for (const [featureName, stat] of Object.entries(info.stats)) {
        const [label, unit, multiplier] = featureLabels[featureName] || [featureName.toUpperCase(), '', 1];
        const promedio = stat.promedio * multiplier;
        const min = stat.min * multiplier;
        const max = stat.max * multiplier;

        const valorDisplay = unit === '€'
            ? promedio.toLocaleString('es-ES', {maximumFractionDigits: 0}) + ' ' + unit
            : unit === '%'
            ? promedio.toFixed(2) + unit
            : promedio.toFixed(2);

        const rangoDisplay = unit === '€'
            ? min.toLocaleString('es-ES', {maximumFractionDigits: 0}) + ' - ' + max.toLocaleString('es-ES', {maximumFractionDigits: 0}) + ' ' + unit
            : unit === '%'
            ? min.toFixed(2) + '% - ' + max.toFixed(2) + '%'
            : min.toFixed(2) + ' - ' + max.toFixed(2);

        html += `
            <div style="background: #f8f9fa; border: 2px solid #e9ecef; border-radius: 10px; padding: 15px;">
                <div style="color: #6c757d; font-size: 12px; font-weight: 600; margin-bottom: 5px;">${label}</div>
                <div style="font-size: 20px; font-weight: bold; color: #495057;">${valorDisplay}</div>
                <div style="color: #6c757d; font-size: 11px; margin-top: 5px;">Rango: ${rangoDisplay}</div>
            </div>`;
    }

    html += `</div>`;

    // Lista de clientes con botones de acción
    html += `
        <h3 style="color: #2c3e50; margin: 25px 0 15px 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px;">👥</span> Lista de Clientes (${info.n_clientes})
        </h3>

        <!-- Botones de acción -->
        <div style="margin-bottom: 15px; display: flex; gap: 10px;">
            <button onclick="toggleListaClientes('${nodeId}')"
                    id="btn-toggle-${nodeId}"
                    style="flex: 1; background: #3498db; color: white; border: none; padding: 12px 20px;
                           border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px;
                           transition: background 0.3s;"
                    onmouseover="this.style.background='#2980b9'"
                    onmouseout="this.style.background='#3498db'">
                ▼ MOSTRAR LISTA COMPLETA (${info.n_clientes} clientes)
            </button>
            <button onclick="descargarClientesCSV('${nodeId}')"
                    style="background: #27ae60; color: white; border: none; padding: 12px 20px;
                           border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px;
                           transition: background 0.3s;"
                    onmouseover="this.style.background='#229954'"
                    onmouseout="this.style.background='#27ae60'">
                📥 DESCARGAR CSV
            </button>
        </div>

        <div id="lista-clientes-${nodeId}" style="display: none; background: #f8f9fa; border: 2px solid #3498db; border-radius: 10px; padding: 15px; max-height: 400px; overflow-y: scroll; overflow-x: hidden; -webkit-overflow-scrolling: touch; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);">
    `;

    info.clientes.forEach((cliente, idx) => {
        html += `
            <div style="padding: 10px; margin: 5px 0; background: white; border-radius: 5px;
                 border-left: 3px solid #3498db; display: flex; align-items: center; gap: 10px;">
                <span style="background: #3498db; color: white; border-radius: 50%;
                     width: 24px; height: 24px; display: inline-flex; align-items: center;
                     justify-content: center; font-size: 11px; font-weight: bold;">${idx + 1}</span>
                <span style="font-family: monospace; font-size: 13px;">${cliente}</span>
            </div>`;
    });

    html += `
        </div>

        <!-- Indicador de scroll -->
        <div id="scroll-indicator-${nodeId}" style="display: none; margin-top: 10px; padding: 12px; background: #e3f2fd; border-left: 4px solid #2196f3; border-radius: 5px; font-size: 12px; color: #1565c0; text-align: center;">
            ⬆️ Usa la rueda del ratón o la barra de scroll para ver todos los ${info.n_clientes} clientes ⬇️
        </div>
    `;

    contenido.innerHTML = html;
    panel.style.display = 'block';
    overlay.style.display = 'block';
}

// ============================================================================
// EVENT LISTENERS: Manejo de clicks en nodos del grafo SVG
// ============================================================================

/**
 * Configura event listeners en todos los nodos del grafo MAPPER.
 * Usa múltiples estrategias de búsqueda para compatibilidad con diferentes versiones de kmapper.
 */
function setupNodeClicks() {
    // Buscar nodos SVG con múltiples selectores (kmapper puede usar diferentes estructuras)
    let circles = document.querySelectorAll('path.circle');

    if (circles.length === 0) {
        circles = document.querySelectorAll('.node');
    }

    if (circles.length === 0) {
        circles = document.querySelectorAll('svg circle');
    }

    console.log(`Mapper: Encontrados ${circles.length} nodos`);

    if (circles.length === 0) {
        console.warn('Mapper: No se encontraron círculos. Reintentando en 2 segundos...');
        setTimeout(setupNodeClicks, 2000);
        return;
    }

    // Agregar event listeners a cada nodo
    circles.forEach((circle, idx) => {
        circle.style.cursor = 'pointer';
        circle.style.transition = 'all 0.2s';

        // Debug: agregar atributo data
        circle.setAttribute('data-node-index', idx);

        // Hover: resaltar nodo
        circle.addEventListener('mouseenter', () => {
            circle.style.strokeWidth = '4px';
            circle.style.stroke = '#3498db';
            circle.style.filter = 'brightness(1.2)';
        });

        circle.addEventListener('mouseleave', () => {
            circle.style.strokeWidth = '1.5px';
            circle.style.stroke = '';
            circle.style.filter = '';
        });

        // Click: mostrar panel con detalles
        circle.addEventListener('click', (e) => {
            e.stopPropagation();

            // Buscar el ID del nodo en el DOM (método robusto)
            let nodeElement = circle;
            let nodeId = null;

            while (nodeElement && nodeElement.tagName !== 'svg') {
                if (nodeElement.classList && nodeElement.classList.contains('node') && nodeElement.id) {
                    // Formato del ID: "node-cube0_cluster0" → extraer "cube0_cluster0"
                    const match = nodeElement.id.match(/^node-(.+)$/);
                    if (match) {
                        nodeId = match[1];
                        break;
                    }
                }
                // Fallback: usar D3.js __data__ si está disponible
                if (nodeElement.__data__ && nodeElement.__data__.name) {
                    nodeId = nodeElement.__data__.name;
                    break;
                }
                nodeElement = nodeElement.parentElement;
            }

            console.log(`Mapper: Click detectado - NodeID: ${nodeId}, Elemento:`, circle.tagName);

            if (nodeId && nodosInfo[nodeId]) {
                console.log(`Mapper: Abriendo panel para nodo ${nodeId} con ${nodosInfo[nodeId].n_clientes} clientes`);
                mostrarDetallesNodo(nodeId);
            } else {
                console.error(`Mapper: No se encontró información para nodeId: ${nodeId}`);
                console.error(`Mapper: NodeIds disponibles:`, Object.keys(nodosInfo).slice(0, 10));
                console.error(`Mapper: Estructura del elemento:`, {
                    tag: circle.tagName,
                    class: circle.className,
                    id: circle.id,
                    parentId: circle.parentElement?.id,
                    parentClass: circle.parentElement?.className
                });
            }
        });
    });

    console.log('Mapper: Event listeners agregados a todos los nodos');
}

// ============================================================================
// NUEVAS FUNCIONES: Expandir lista y descargar CSV
// ============================================================================

/**
 * Expande o colapsa la lista completa de clientes de un nodo.
 * @param {string} nodeId - ID del nodo
 */
function toggleListaClientes(nodeId) {
    const lista = document.getElementById('lista-clientes-' + nodeId);
    const btn = document.getElementById('btn-toggle-' + nodeId);
    const indicator = document.getElementById('scroll-indicator-' + nodeId);
    const info = nodosInfo[nodeId];

    if (!lista || !btn || !info) return;

    if (lista.style.display === 'none') {
        lista.style.display = 'block';
        btn.innerHTML = '▲ OCULTAR LISTA COMPLETA';

        // Mostrar indicador de scroll si hay muchos clientes
        if (indicator && info.n_clientes > 10) {
            indicator.style.display = 'block';
        }

        // Hacer scroll suave hacia la lista
        setTimeout(() => {
            lista.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    } else {
        lista.style.display = 'none';
        btn.innerHTML = '▼ MOSTRAR LISTA COMPLETA (' + info.n_clientes + ' clientes)';

        // Ocultar indicador
        if (indicator) {
            indicator.style.display = 'none';
        }
    }
}

/**
 * Descarga la lista de clientes del nodo en formato CSV.
 * @param {string} nodeId - ID del nodo
 */
function descargarClientesCSV(nodeId) {
    const info = nodosInfo[nodeId];

    if (!info || !info.clientes) {
        alert('No hay datos disponibles para descargar');
        return;
    }

    // Crear encabezados CSV
    let csv = 'Nodo,CIF/NIF,Tasa Morosidad del Nodo (%),N° Clientes en Nodo\n';

    // Añadir filas de datos
    info.clientes.forEach(function(cliente) {
        csv += nodeId + ',';
        csv += '"' + cliente + '",';
        csv += info.morosidad_pct.toFixed(2) + ',';
        csv += info.n_clientes + '\n';
    });

    // Crear blob y descargar
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', 'nodo_' + nodeId.replace(/[^a-zA-Z0-9]/g, '_') + '_clientes.csv');
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    console.log('CSV descargado: nodo_' + nodeId + '_clientes.csv (' + info.clientes.length + ' clientes)');
}

// ============================================================================
// INICIALIZACIÓN: Ejecutar cuando el DOM esté listo
// ============================================================================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(setupNodeClicks, 1000);
    });
} else {
    setTimeout(setupNodeClicks, 1000);
}
