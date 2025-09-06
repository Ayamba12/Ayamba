/**
 * Awinso Hair Care - Production JavaScript
 * Optimized for performance, accessibility, and cross-browser compatibility
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    // Initialize all components
    initServiceCards();
    initAdminTabs();
    initAutoDismissAlerts();
    initFormValidation();
    initTooltips();
    initModals();
    initAccessibilityFeatures();

    console.log('Awinso Hair Care - JavaScript initialized successfully');
});

/**
 * Initialize service card functionality
 */
function initServiceCards() {
    const serviceTitles = document.querySelectorAll('.service-title');
    
    serviceTitles.forEach(title => {
        // Add ARIA attributes for accessibility
        title.setAttribute('role', 'button');
        title.setAttribute('aria-expanded', 'false');
        
        title.addEventListener('click', function(e) {
            e.preventDefault();
            const icon = this.querySelector('i.fa-chevron-down, i.fa-chevron-up');
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            
            // Toggle icon
            if (icon) {
                if (isExpanded) {
                    icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
                } else {
                    icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
                }
            }
            
            // Update ARIA attribute
            this.setAttribute('aria-expanded', (!isExpanded).toString());
        });

        // Keyboard support
        title.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });
}

/**
 * Initialize admin dashboard tabs
 */
function initAdminTabs() {
    const triggerTabList = document.querySelectorAll('#adminTabs button[data-bs-toggle="tab"]');
    
    if (triggerTabList.length > 0 && typeof bootstrap !== 'undefined') {
        triggerTabList.forEach(triggerEl => {
            triggerEl.addEventListener('click', function(e) {
                e.preventDefault();
                const tab = new bootstrap.Tab(this);
                tab.show();
                
                // Store active tab in localStorage
                try {
                    localStorage.setItem('activeAdminTab', this.id);
                } catch (e) {
                    console.warn('Could not store tab state:', e);
                }
            });
        });

        // Restore active tab from localStorage
        try {
            const activeTabId = localStorage.getItem('activeAdminTab');
            if (activeTabId) {
                const activeTab = document.getElementById(activeTabId);
                if (activeTab) {
                    const tab = new bootstrap.Tab(activeTab);
                    tab.show();
                }
            }
        } catch (e) {
            console.warn('Could not restore tab state:', e);
        }
    }
}

/**
 * Initialize auto-dismiss alerts
 */
function initAutoDismissAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    
    if (alerts.length > 0 && typeof bootstrap !== 'undefined') {
        alerts.forEach(alert => {
            const timeout = alert.dataset.dismissTimeout || 5000;
            
            setTimeout(() => {
                try {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                } catch (e) {
                    alert.style.opacity = '0';
                    alert.style.transition = 'opacity 0.5s ease';
                    setTimeout(() => alert.remove(), 500);
                }
            }, parseInt(timeout));
        });
    }
}

/**
 * Initialize form validation
 */
function initFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
                
                // Focus on first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
            
            form.classList.add('was-validated');
        }, false);
    });
}

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(
        document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );
    
    if (tooltipTriggerList.length > 0 && typeof bootstrap !== 'undefined') {
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl, {
                trigger: 'hover focus'
            });
        });
    }
}

/**
 * Initialize modal functionality
 */
function initModals() {
    const modals = document.querySelectorAll('.modal');
    
    modals.forEach(modal => {
        modal.addEventListener('shown.bs.modal', function() {
            // Focus on first input in modal
            const input = this.querySelector('input, select, textarea');
            if (input) input.focus();
        });
    });
}

/**
 * Initialize accessibility features
 */
function initAccessibilityFeatures() {
    // Skip to content functionality
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Skip to main content';
    document.body.insertBefore(skipLink, document.body.firstChild);
    
    // Add main content ID if it doesn't exist
    const mainContent = document.querySelector('main') || document.querySelector('.main-content');
    if (mainContent && !mainContent.id) {
        mainContent.id = 'main-content';
    }
    
    // External link indicators
    document.querySelectorAll('a[href^="http"]').forEach(link => {
        if (link.hostname !== window.location.hostname) {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
            
            const indicator = document.createElement('span');
            indicator.className = 'sr-only';
            indicator.textContent = '(opens in new tab)';
            link.appendChild(indicator);
        }
    });
    
    // Lazy loading for images
    if ('loading' in HTMLImageElement.prototype) {
        document.querySelectorAll('img[loading="lazy"]').forEach(img => {
            // Native lazy loading supported
            img.addEventListener('load', function() {
                this.classList.add('loaded');
            });
        });
    } else {
        // Fallback for browsers without native lazy loading
        // You might want to add a polyfill here
    }
}

/**
 * Debounce function for performance optimization
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function() {
        const context = this, args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

/**
 * Throttle function for performance optimization
 */
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Error handling utility
 */
function handleError(error, context = '') {
    console.error(`Error${context ? ' in ' + context : ''}:`, error);
    
    // You might want to send errors to a logging service here
    if (typeof Sentry !== 'undefined') {
        Sentry.captureException(error);
    }
}

/**
 * Performance monitoring
 */
if ('performance' in window) {
    // Measure page load time
    window.addEventListener('load', function() {
        const navigation = performance.getEntriesByType('navigation')[0];
        if (navigation) {
            const loadTime = navigation.loadEventEnd - navigation.navigationStart;
            console.log(`Page loaded in ${loadTime}ms`);
            
            // Send to analytics if needed
            if (typeof gtag !== 'undefined') {
                gtag('event', 'timing_complete', {
                    'name': 'page_load',
                    'value': Math.round(loadTime),
                    'event_category': 'Load Time'
                });
            }
        }
    });
}

/**
 * Service Worker Registration (if needed)
 */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js')
            .then(function(registration) {
                console.log('SW registered: ', registration);
            })
            .catch(function(registrationError) {
                console.log('SW registration failed: ', registrationError);
            });
    });
}

// Export functions for use in other modules (if using modules)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initServiceCards,
        initAdminTabs,
        initAutoDismissAlerts,
        initFormValidation,
        initTooltips,
        initModals,
        initAccessibilityFeatures,
        debounce,
        throttle,
        handleError
    };
}