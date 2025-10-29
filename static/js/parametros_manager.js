/**
 * Gestor de Parámetros Proporcionales
 * 
 * Este módulo maneja la conversión entre píxeles y milímetros
 * usando una fuente única de verdad (píxeles) y escalado dinámico.
 */

class ParametrosManager {
  constructor() {
    this.junta = null;
    this.parametros_proporcionales = null;
    this.px_mm = 1.0;
  }

  /**
   * Inicializa el manager con los datos de la junta
   * @param {Object} junta - Datos de la junta
   */
  inicializar(junta) {
    this.junta = junta;
    this.parametros_proporcionales = junta.parametros_proporcionales || null;
    this.px_mm = junta.px_mm || 1.0;
    
    console.log('[ParametrosManager] Inicializado:', {
      parametrizado: junta.parametrizado,
      px_mm: this.px_mm,
      parametros_count: this.parametros_proporcionales ? Object.keys(this.parametros_proporcionales).length : 0
    });
  }

  /**
   * Verifica si la junta está parametrizada
   * @returns {boolean}
   */
  estaParametrizada() {
    return this.junta && this.junta.parametrizado && this.parametros_proporcionales;
  }

  /**
   * Obtiene un valor en milímetros (calculado dinámicamente)
   * @param {string} nombre - Nombre del parámetro (ej: 'ancho_junta', 'alto_junta')
   * @returns {number} Valor en milímetros
   */
  get_valor(nombre) {
    if (!this.estaParametrizada()) {
      console.warn(`[ParametrosManager] Junta no parametrizada, no se puede obtener ${nombre}`);
      return 0;
    }

    const nombrePx = `${nombre}_px`;
    const valorPx = this.parametros_proporcionales[nombrePx];
    
    if (valorPx === undefined) {
      console.warn(`[ParametrosManager] Parámetro ${nombrePx} no encontrado`);
      return 0;
    }

    const valorMm = valorPx / this.px_mm;
    console.log(`[ParametrosManager] get_valor(${nombre}): ${valorPx}px / ${this.px_mm} = ${valorMm.toFixed(3)}mm`);
    
    return valorMm;
  }

  /**
   * Establece un valor en milímetros (recalcula px_mm y actualiza todos los valores)
   * @param {string} nombre - Nombre del parámetro
   * @param {number} valorMm - Nuevo valor en milímetros
   */
  set_valor(nombre, valorMm) {
    if (!this.estaParametrizada()) {
      console.warn(`[ParametrosManager] Junta no parametrizada, no se puede establecer ${nombre}`);
      return;
    }

    const nombrePx = `${nombre}_px`;
    const valorPx = this.parametros_proporcionales[nombrePx];
    
    if (valorPx === undefined) {
      console.warn(`[ParametrosManager] Parámetro ${nombrePx} no encontrado`);
      return;
    }

    // Calcular nuevo px_mm basado en este parámetro
    const nuevoPxMm = valorPx / valorMm;
    
    console.log(`[ParametrosManager] set_valor(${nombre}, ${valorMm}mm):`);
    console.log(`  Valor original: ${valorPx}px`);
    console.log(`  Nuevo px_mm: ${nuevoPxMm.toFixed(6)}`);
    console.log(`  px_mm anterior: ${this.px_mm.toFixed(6)}`);

    // Actualizar px_mm
    this.px_mm = nuevoPxMm;
    this.junta.px_mm = nuevoPxMm;

    // Recalcular y actualizar todos los valores en el frontend
    this.actualizarTodosLosValores();
  }

  /**
   * Actualiza todos los valores en el frontend basándose en los píxeles y px_mm actual
   */
  actualizarTodosLosValores() {
    if (!this.estaParametrizada()) return;

    console.log('[ParametrosManager] Actualizando todos los valores en frontend...');

    // Lista de parámetros a actualizar
    const parametros = [
      'ancho_junta',
      'alto_junta', 
      'diametro_cilindro',
      'distancia_extremos',
      'area_junta',
      'perimetro_junta'
    ];

    parametros.forEach(param => {
      const valorMm = this.get_valor(param);
      this.actualizarCampoFrontend(param, valorMm);
    });

    // Actualizar coordenadas de muescas
    this.actualizarCoordenadasMuescas();
  }

  /**
   * Actualiza un campo específico en el frontend
   * @param {string} nombre - Nombre del parámetro
   * @param {number} valorMm - Valor en milímetros
   */
  actualizarCampoFrontend(nombre, valorMm) {
    const mapeoCampos = {
      'ancho_junta': 'anchoJunta',
      'alto_junta': 'altoJunta',
      'diametro_cilindro': 'diametroCilindro',
      'distancia_extremos': 'distanciaCilindrosExtremos',
      'area_junta': 'areaJunta',
      'perimetro_junta': 'perimetroJunta'
    };

    const idCampo = mapeoCampos[nombre];
    if (idCampo) {
      const elemento = document.getElementById(idCampo);
      if (elemento) {
        elemento.value = valorMm.toFixed(2);
        console.log(`[ParametrosManager] Actualizado ${idCampo}: ${valorMm.toFixed(2)}mm`);
      }
    }
  }

  /**
   * Actualiza las coordenadas de las muescas
   */
  actualizarCoordenadasMuescas() {
    if (!this.estaParametrizada() || !this.junta.centros_muescas) return;

    console.log('[ParametrosManager] Actualizando coordenadas de muescas...');

    this.junta.centros_muescas.forEach((muesca, index) => {
      if (muesca.centro_px) {
        // Convertir coordenadas de píxeles a mm
        const xMm = muesca.centro_px[0] / this.px_mm;
        const yMm = muesca.centro_px[1] / this.px_mm;
        
        // Actualizar en la estructura de datos
        muesca.centro_mm = [xMm, yMm];
        
        console.log(`[ParametrosManager] Muesca ${index + 1}: ${muesca.centro_px[0]},${muesca.centro_px[1]}px → ${xMm.toFixed(2)},${yMm.toFixed(2)}mm`);
      }
    });

    // Actualizar campos de la primera muesca en el frontend
    if (this.junta.centros_muescas.length > 0) {
      const primeraMuesca = this.junta.centros_muescas[0];
      if (primeraMuesca.centro_mm) {
        const muescaX = document.getElementById('muescaX');
        const muescaY = document.getElementById('muescaY');
        
        if (muescaX) muescaX.value = primeraMuesca.centro_mm[0].toFixed(2);
        if (muescaY) muescaY.value = primeraMuesca.centro_mm[1].toFixed(2);
      }
    }
  }

  /**
   * Obtiene las coordenadas de las muescas en mm (calculadas dinámicamente)
   * @returns {Array} Array de coordenadas [x, y] en mm
   */
  getCoordenadasMuescas() {
    if (!this.estaParametrizada() || !this.junta.centros_muescas) return [];

    return this.junta.centros_muescas.map(muesca => {
      if (muesca.centro_px) {
        return [
          muesca.centro_px[0] / this.px_mm,
          muesca.centro_px[1] / this.px_mm
        ];
      } else if (muesca.centro_mm) {
        return muesca.centro_mm;
      }
      return [0, 0];
    });
  }

  /**
   * Obtiene las dimensiones del ROI en mm (calculadas dinámicamente)
   * @returns {Object} {width_mm, height_mm}
   */
  getDimensionesROI() {
    if (!this.estaParametrizada()) {
      return { width_mm: 0, height_mm: 0 };
    }

    return {
      width_mm: Math.round(this.get_valor('ancho_junta')),
      height_mm: Math.round(this.get_valor('alto_junta'))
    };
  }

  /**
   * Guarda los parámetros proporcionales después de la parametrización
   * @param {Object} analisis - Resultado del análisis de imagen
   */
  guardarParametrosProporcionales(analisis) {
    console.log('[ParametrosManager] guardarParametrosProporcionales llamada con:', analisis);
    
    if (!analisis || !analisis.contorno_principal) {
      console.error('[ParametrosManager] Análisis inválido para guardar parámetros');
      return;
    }

    const contorno = analisis.contorno_principal;
    const lineaReferencia = analisis.linea_referencia;
    
    // Calcular parámetros proporcionales (en píxeles)
    this.parametros_proporcionales = {
      // Dimensiones principales
      ancho_junta_px: contorno.bbox_width_px || 0,
      alto_junta_px: contorno.bbox_height_px || 0,
      area_junta_px: contorno.area_px || 0,
      perimetro_junta_px: contorno.perimetro_px || 0,
      
      // Distancia entre extremos (puede ser 0 si no hay línea de referencia)
      distancia_extremos_px: lineaReferencia?.distancia_px || 0,
      
      // Diámetro promedio de cilindros (puede ser 0 si no hay agujeros)
      diametro_cilindro_px: this.calcularDiametroPromedio(analisis.agujeros || [])
    };

    // Solo establecer px_mm inicial si es la primera parametrización (no hay parámetros guardados)
    // Si ya hay parametros_proporcionales guardados, significa que ya se parametrizó antes
    if (!this.junta.parametros_proporcionales) {
      // Primera parametrización - establecer px_mm inicial a 1.0
      this.px_mm = 1.0;
      this.junta.px_mm = 1.0;
      console.log('[ParametrosManager] Primera parametrización - estableciendo px_mm inicial: 1.0');
    } else {
      // Ya hay parámetros guardados - preservar el px_mm existente
      if (this.junta.px_mm && this.junta.px_mm > 0) {
        this.px_mm = this.junta.px_mm;
        console.log('[ParametrosManager] Preservando px_mm existente:', this.px_mm);
      } else {
        // Si por alguna razón no hay px_mm guardado, usar 1.0 por defecto
        this.px_mm = 1.0;
        this.junta.px_mm = 1.0;
        console.log('[ParametrosManager] px_mm no encontrado, usando valor por defecto: 1.0');
      }
    }
    
    this.junta.parametrizado = true;
    this.junta.parametros_proporcionales = this.parametros_proporcionales;

    console.log('[ParametrosManager] Parámetros proporcionales guardados:', this.parametros_proporcionales);
    
    // Habilitar controles de edición
    this.habilitarControlesEdicion();
  }

  /**
   * Habilita todos los controles de edición
   */
  habilitarControlesEdicion() {
    console.log('[ParametrosManager] Habilitando controles de edición...');
    
    // Habilitar campos de medidas
    const camposMedidas = [
      'anchoJunta', 'altoJunta', 'diametroCilindro', 'distanciaCilindrosExtremos'
    ];
    
    camposMedidas.forEach(id => {
      const campo = document.getElementById(id);
      if (campo) {
        campo.disabled = false;
        campo.style.background = 'var(--bg-primary)';
        console.log(`[ParametrosManager] ✓ Habilitado campo: ${id}`);
      } else {
        console.warn(`[ParametrosManager] ⚠️ Campo no encontrado: ${id}`);
      }
    });
    
    // Habilitar campos de muescas
    const camposMuescas = [
      'cantidadMuescas', 'muescaX', 'muescaY', 'muescasVertical'
    ];
    
    camposMuescas.forEach(id => {
      const campo = document.getElementById(id);
      if (campo) {
        campo.disabled = false;
        campo.style.background = 'var(--bg-primary)';
      }
    });
    
    // Habilitar campos de textos
    const camposTextos = [
      'illinoisX', 'illinoisY', 'illinoisVertical',
      'codigoX', 'codigoY', 'codigoVertical',
      'loteX', 'loteY', 'loteVertical'
    ];
    
    camposTextos.forEach(id => {
      const campo = document.getElementById(id);
      if (campo) {
        campo.disabled = false;
        campo.style.background = 'var(--bg-primary)';
      }
    });
    
    // Habilitar botón Guardar
    const btnGuardar = document.getElementById('btnGuardar');
    if (btnGuardar) {
      btnGuardar.disabled = false;
      btnGuardar.style.opacity = '1';
    }
    
    console.log('[ParametrosManager] ✓ Controles de edición habilitados');
  }

  /**
   * Deshabilita todos los controles de edición (excepto nombre, imagen y parametrizar)
   */
  deshabilitarControlesEdicion() {
    console.log('[ParametrosManager] Deshabilitando controles de edición...');
    
    // Deshabilitar campos de medidas
    const camposMedidas = [
      'anchoJunta', 'altoJunta', 'diametroCilindro', 'distanciaCilindrosExtremos'
    ];
    
    camposMedidas.forEach(id => {
      const campo = document.getElementById(id);
      if (campo) {
        campo.disabled = true;
        campo.style.background = 'var(--bg-secondary)';
        campo.value = '';
      }
    });
    
    // Deshabilitar campos de muescas
    const camposMuescas = [
      'cantidadMuescas', 'muescaX', 'muescaY', 'muescasVertical'
    ];
    
    camposMuescas.forEach(id => {
      const campo = document.getElementById(id);
      if (campo) {
        campo.disabled = true;
        campo.style.background = 'var(--bg-secondary)';
        if (id !== 'muescasVertical') {
          campo.value = '';
        } else {
          campo.checked = false;
        }
      }
    });
    
    // Deshabilitar campos de textos
    const camposTextos = [
      'illinoisX', 'illinoisY', 'illinoisVertical',
      'codigoX', 'codigoY', 'codigoVertical',
      'loteX', 'loteY', 'loteVertical'
    ];
    
    camposTextos.forEach(id => {
      const campo = document.getElementById(id);
      if (campo) {
        campo.disabled = true;
        campo.style.background = 'var(--bg-secondary)';
        if (id.includes('Vertical')) {
          campo.checked = false;
        } else {
          campo.value = '';
        }
      }
    });
    
    // Deshabilitar botón Guardar
    const btnGuardar = document.getElementById('btnGuardar');
    if (btnGuardar) {
      btnGuardar.disabled = true;
      btnGuardar.style.opacity = '0.5';
    }
    
    // Ocultar sección de parámetros
    const seccionParametros = document.getElementById('seccion-parametros');
    if (seccionParametros) {
      seccionParametros.style.display = 'none';
    }
    
    console.log('[ParametrosManager] ✓ Controles de edición deshabilitados');
  }

  /**
   * Calcula el diámetro promedio de los agujeros grandes
   * @param {Array} agujeros - Lista de agujeros
   * @returns {number} Diámetro promedio en píxeles
   */
  calcularDiametroPromedio(agujeros) {
    const agujerosGrandes = agujeros.filter(a => a.clasificacion === 'Redondo Grande');
    
    if (agujerosGrandes.length === 0) return 0;

    let sumaDiametros = 0;
    for (const agujero of agujerosGrandes) {
      const radio = Math.sqrt(agujero.area_px / Math.PI);
      const diametro = 2 * radio;
      sumaDiametros += diametro;
    }

    return sumaDiametros / agujerosGrandes.length;
  }
}

// Instancia global del manager
window.parametrosManager = new ParametrosManager();
