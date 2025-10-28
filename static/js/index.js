/* ============================================================
   COMAU-VISION - Navegación Principal (Index)
   ============================================================ */

(function() {
  'use strict';

  /* ============================================================
     CONFIGURACIÓN
     ============================================================ */
  const PAGE_MAP = {
    control: '/templates/control.html',
    configuracion: '/templates/configuracion.html'
  };

  const DEFAULT_PAGE = 'control';

  /* ============================================================
     ELEMENTOS DEL DOM
     ============================================================ */
  let leftFrame = null;
  let navButtons = [];

  /* ============================================================
     AJUSTE DE ALTURA DE IFRAMES
     ============================================================ */
  function adjustFrameHeights() {
    const frames = document.querySelectorAll('.panel-frame');
    const headerHeight = 64; // var(--header-height)
    const availableHeight = window.innerHeight - headerHeight;
    
    frames.forEach(frame => {
      frame.style.height = availableHeight + 'px';
    });
  }

  /* ============================================================
     NAVEGACIÓN
     ============================================================ */
  function navigateTo(page) {
    const targetUrl = PAGE_MAP[page] || PAGE_MAP[DEFAULT_PAGE];
    
    if (!leftFrame) {
      console.error('[index] Left frame not found');
      return;
    }

    // Cambiar la página solo si es diferente
    const currentPath = leftFrame.contentWindow?.location?.pathname || '';
    if (currentPath !== targetUrl) {
      leftFrame.src = targetUrl;
    }

    // Actualizar estado visual de botones
    updateNavButtons(page);

    // Actualizar hash en URL
    if (location.hash.replace('#', '') !== page) {
      history.replaceState(null, '', '#' + page);
    }
  }

  function updateNavButtons(activePage) {
    navButtons.forEach(btn => {
      const isActive = btn.dataset.page === activePage;
      btn.classList.toggle('active', isActive);
      if (isActive) {
        btn.setAttribute('aria-current', 'page');
      } else {
        btn.removeAttribute('aria-current');
      }
    });
  }

  /* ============================================================
     COMUNICACIÓN ENTRE IFRAMES
     ============================================================ */
  function setupMessageBridge() {
    // Escuchar mensajes de los iframes hijos
    window.addEventListener('message', (event) => {
      // Reenviar mensajes entre iframes hermanos
      const leftFrame = document.getElementById('leftFrame');
      const rightFrame = document.getElementById('rightFrame');
      
      if (event.data.type === 'ANALYSIS_READY' || event.data.type === 'ANALYSIS_SUCCESS' || event.data.type === 'ANALYSIS_FAILED' || event.data.type === 'TRAJECTORY_DATA') {
        // Mensaje del dashboard → control
        if (leftFrame && leftFrame.contentWindow) {
          leftFrame.contentWindow.postMessage(event.data, '*');
          console.log(`[index] Reenviando mensaje ${event.data.type} al control`);
        }
      }
      
      if (event.data.type === 'JUNTA_CHANGED') {
        // Mensaje del control → dashboard
        if (rightFrame && rightFrame.contentWindow) {
          rightFrame.contentWindow.postMessage(event.data, '*');
          console.log('[index] Reenviando mensaje JUNTA_CHANGED al dashboard');
        }
      }
      
      if (event.data.type === 'NAVIGATE_TO_DASHBOARD') {
        // Mensaje desde database.html → navegar al dashboard
        console.log('[index] Navegando al dashboard con junta:', event.data.juntaId);
        navigateTo('control');
        
        // Notificar al dashboard que hay una nueva junta seleccionada
        setTimeout(() => {
          if (rightFrame && rightFrame.contentWindow) {
            rightFrame.contentWindow.postMessage({ type: 'JUNTA_SELECTED', juntaId: event.data.juntaId }, '*');
          }
        }, 500);
      }
    });
  }

  /* ============================================================
     INICIALIZACIÓN
     ============================================================ */
  function init() {
    // Obtener referencias del DOM
    leftFrame = document.getElementById('leftFrame');
    navButtons = Array.from(document.querySelectorAll('.nav-btn'));

    // Validar elementos
    if (!leftFrame) {
      console.error('[index] Left frame element not found');
      return;
    }

    // Event listeners para botones de navegación
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const page = btn.dataset.page;
        if (page) {
          navigateTo(page);
        }
      });
    });

    // Navegación inicial basada en hash
    const initialPage = (location.hash || '#' + DEFAULT_PAGE).slice(1);
    navigateTo(initialPage);

    // Listener para cambios en hash
    window.addEventListener('hashchange', () => {
      const page = (location.hash || '#' + DEFAULT_PAGE).slice(1);
      navigateTo(page);
    });

    // Configurar puente de mensajes entre iframes
    setupMessageBridge();

    // Ajustar altura de frames
    adjustFrameHeights();
    window.addEventListener('resize', adjustFrameHeights);

    console.log('[index] Navigation system initialized');
  }

  /* ============================================================
     EJECUTAR AL CARGAR
     ============================================================ */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

