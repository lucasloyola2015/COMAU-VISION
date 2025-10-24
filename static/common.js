/* ============================================================
   COMAU-VISION - Utilidades Comunes
   ============================================================ */

(function() {
  'use strict';

  /* ============================================================
     FETCH CON TIMEOUT
     ============================================================ */
  async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  /* ============================================================
     MANEJO DE IMÁGENES
     ============================================================ */
  function setPlaceholder(img) {
    if (!img) return;
    
    img.onerror = null;
    img.src = 'data:image/svg+xml;utf8,' + encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="800" height="400">
        <rect width="100%" height="100%" fill="#0e0e0f"/>
        <rect x="1" y="1" width="798" height="398" fill="none" stroke="#1d1d1f"/>
        <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
              font-family="system-ui, sans-serif" font-size="16" fill="#9a9aa2">
          Sin imagen
        </text>
      </svg>
    `);
  }

  /* ============================================================
     NOTIFICACIONES
     ============================================================ */
  function showNotification(message, type = 'info', duration = 3000) {
    // Remover notificaciones existentes
    const existing = document.querySelectorAll('.notification');
    existing.forEach(n => n.remove());
    
    // Crear notificación
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Estilos inline
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      z-index: 10000;
      max-width: 400px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      animation: slideIn 0.3s ease;
    `;
    
    // Colores según tipo
    const colors = {
      success: 'background: #28a745; color: white;',
      error: 'background: #dc3545; color: white;',
      warning: 'background: #ffc107; color: #212529;',
      info: 'background: #17a2b8; color: white;'
    };
    
    notification.style.cssText += colors[type] || colors.info;
    
    document.body.appendChild(notification);
    
    // Auto-remover
    setTimeout(() => {
      if (notification.parentNode) {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
      }
    }, duration);
  }

  /* ============================================================
     HELPERS DE FORMULARIOS
     ============================================================ */
  function getFormData(formElement) {
    if (!formElement) return {};
    
    const formData = new FormData(formElement);
    const data = {};
    
    for (const [key, value] of formData.entries()) {
      data[key] = value;
    }
    
    return data;
  }

  function setFormData(formElement, data) {
    if (!formElement || !data) return;
    
    Object.keys(data).forEach(key => {
      const input = formElement.elements[key];
      if (input) {
        if (input.type === 'checkbox') {
          input.checked = !!data[key];
        } else {
          input.value = data[key];
        }
      }
    });
  }

  /* ============================================================
     FORMATEO DE DATOS
     ============================================================ */
  function formatDate(date) {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleString('es-AR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined) return '';
    return Number(num).toFixed(decimals);
  }

  /* ============================================================
     DEBOUNCE
     ============================================================ */
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /* ============================================================
     ANIMACIONES CSS
     ============================================================ */
  const styles = document.createElement('style');
  styles.textContent = `
    @keyframes slideIn {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
    
    @keyframes slideOut {
      from {
        transform: translateX(0);
        opacity: 1;
      }
      to {
        transform: translateX(100%);
        opacity: 0;
      }
    }
  `;
  document.head.appendChild(styles);

  /* ============================================================
     HELPERS DE UI
     ============================================================ */
  function setStatusIndicator(elementId, isOn) {
    const element = document.getElementById(elementId);
    if (element) {
      element.classList.toggle('on', !!isOn);
    }
  }

  function setMessage(elementId, text, className = '') {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = text || '';
      element.className = className || '';
    }
  }

  /* ============================================================
     EXPORTAR UTILIDADES
     ============================================================ */
  window.Common = {
    fetchWithTimeout,
    setPlaceholder,
    showNotification,
    getFormData,
    setFormData,
    formatDate,
    formatNumber,
    debounce,
    setStatusIndicator,
    setMessage
  };

  // Compatibilidad con código legacy
  window.fetchWithTimeout = fetchWithTimeout;
  window.setPlaceholder = setPlaceholder;

})();

