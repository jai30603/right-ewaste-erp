// Shared JavaScript Logic for Right Ewaste ERP V5.0

// Sidebar toggle for mobile
function toggleSidebar() {
    var sidebar = document.querySelector('.erp-sidebar');
    var overlay = document.getElementById('sidebarOverlay');
    if (sidebar && overlay) {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
    }
}

function closeSidebar() {
    var sidebar = document.querySelector('.erp-sidebar');
    var overlay = document.getElementById('sidebarOverlay');
    if (sidebar && overlay) {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Smart Back Navigation
function navigateBack(fallbackUrl) {
    if (document.referrer && document.referrer.indexOf(window.location.host) !== -1) {
        window.history.back();
    } else if (fallbackUrl) {
        window.location.href = fallbackUrl;
    } else {
        window.location.href = '/';
    }
}

// Theme handling
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var icon = document.getElementById('darkModeIcon');
    if (icon) icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    localStorage.setItem('erpTheme', theme);
}

function toggleDarkMode() {
    var current = document.documentElement.getAttribute('data-theme');
    applyTheme(current === 'dark' ? 'light' : 'dark');
}

(function () {
    var saved = localStorage.getItem('erpTheme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
})();

document.addEventListener('DOMContentLoaded', function () {
    var saved = localStorage.getItem('erpTheme') || 'light';
    applyTheme(saved);

    // Close sidebar on mobile navigation
    var navLinks = document.querySelectorAll('.sidebar-nav a, .module-submenu a');
    navLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth < 992) { closeSidebar(); }
        });
    });

    // Auto-dismiss alert messages after 5 seconds
    var alerts = document.querySelectorAll('.flash-container .alert');
    alerts.forEach(function(alertEl) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // PWA Service Worker Registration
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function() {
            navigator.serviceWorker.register('/sw.js', { scope: '/' })
                .then(function(reg) {
                    console.log('[PWA] Service Worker registered cleanly, scope:', reg.scope);
                })
                .catch(function(err) {
                    console.warn('[PWA] Service Worker registration failed:', err);
                });
        });
    }

    // Network Online / Offline Status Detection
    function updateOnlineStatus() {
        if (!navigator.onLine) {
            showNetworkToast('You are working offline. Cached records are available.', 'warning');
        }
    }
    window.addEventListener('online', function() { showNetworkToast('Network connection restored.', 'success'); });
    window.addEventListener('offline', updateOnlineStatus);

    // Mobile Camera capture handler for image inputs
    var imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    imageInputs.forEach(function(input) {
        if (!input.hasAttribute('capture') && /Android|iPhone|iPad/i.test(navigator.userAgent)) {
            input.setAttribute('capture', 'environment');
        }
    });
});

// PWA Deferred Install Prompt Handler
var deferredPWAInstallPrompt = null;
window.addEventListener('beforeinstallprompt', function(e) {
    e.preventDefault();
    deferredPWAInstallPrompt = e;
    var btn = document.getElementById('pwaInstallBtn');
    if (btn) { btn.classList.remove('d-none'); }
});

function installPWA() {
    if (deferredPWAInstallPrompt) {
        deferredPWAInstallPrompt.prompt();
        deferredPWAInstallPrompt.userChoice.then(function(choiceResult) {
            if (choiceResult.outcome === 'accepted') {
                console.log('[PWA] User accepted the installation prompt');
            }
            deferredPWAInstallPrompt = null;
            var btn = document.getElementById('pwaInstallBtn');
            if (btn) { btn.classList.add('d-none'); }
        });
    }
}

// Toast notification helper for Network & PWA alerts
function showNetworkToast(message, type) {
    var container = document.querySelector('.flash-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'flash-container';
        document.body.appendChild(container);
    }
    var toast = document.createElement('div');
    toast.className = 'alert alert-' + (type || 'info') + ' alert-dismissible fade show mb-2 shadow-sm';
    toast.innerHTML = (type === 'success' ? '✅ ' : '⚠️ ') + message +
        '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
    container.appendChild(toast);
    setTimeout(function() {
        if (toast.parentNode) { toast.parentNode.removeChild(toast); }
    }, 4000);
}
