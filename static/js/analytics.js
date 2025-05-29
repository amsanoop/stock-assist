let startTime = new Date();
let lastInteractionTime = new Date();
let totalTimeSpent = 0;
let isPageActive = true;

document.addEventListener('click', function() {
    lastInteractionTime = new Date();
    if (typeof gtag === 'function') {
        gtag('event', 'user_interaction', {
            'event_category': 'engagement',
            'event_label': 'click',
            'page_location': window.location.href,
            'page_title': document.title
        });
    }
});

let maxScrollDepth = 0;
window.addEventListener('scroll', function() {
    lastInteractionTime = new Date();
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrollDepth = Math.round((scrollTop / scrollHeight) * 100);
    
    if (scrollDepth > maxScrollDepth) {
        maxScrollDepth = scrollDepth;
        if (maxScrollDepth % 25 === 0 && typeof gtag === 'function') {
            gtag('event', 'scroll_depth', {
                'event_category': 'engagement',
                'event_label': 'scroll',
                'value': maxScrollDepth,
                'page_location': window.location.href,
                'page_title': document.title
            });
        }
    }
});

document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'hidden') {
        isPageActive = false;
        const timeSpent = Math.round((new Date() - lastInteractionTime) / 1000);
        totalTimeSpent += timeSpent;
        
        if (typeof gtag === 'function') {
            gtag('event', 'page_visibility', {
                'event_category': 'engagement',
                'event_label': 'hidden',
                'value': timeSpent,
                'page_location': window.location.href,
                'page_title': document.title
            });
        }
    } else {
        isPageActive = true;
        lastInteractionTime = new Date();
        
        if (typeof gtag === 'function') {
            gtag('event', 'page_visibility', {
                'event_category': 'engagement',
                'event_label': 'visible',
                'page_location': window.location.href,
                'page_title': document.title
            });
        }
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            if (typeof gtag === 'function') {
                gtag('event', 'form_submit', {
                    'event_category': 'engagement',
                    'event_label': form.id || form.action,
                    'page_location': window.location.href,
                    'page_title': document.title
                });
            }
        });
        
        const formFields = form.querySelectorAll('input, select, textarea');
        formFields.forEach(function(field) {
            field.addEventListener('focus', function() {
                if (typeof gtag === 'function') {
                    gtag('event', 'form_field_focus', {
                        'event_category': 'engagement',
                        'event_label': field.name || field.id,
                        'page_location': window.location.href,
                        'page_title': document.title
                    });
                }
            });
        });
    });
    
    const buttons = document.querySelectorAll('button, .btn, .button, [role="button"]');
    buttons.forEach(function(button) {
        button.addEventListener('click', function() {
            if (typeof gtag === 'function') {
                gtag('event', 'button_click', {
                    'event_category': 'engagement',
                    'event_label': button.textContent.trim() || button.id || 'unknown',
                    'page_location': window.location.href,
                    'page_title': document.title
                });
            }
        });
    });
    
    const links = document.querySelectorAll('a');
    links.forEach(function(link) {
        link.addEventListener('click', function() {
            if (typeof gtag === 'function') {
                gtag('event', 'link_click', {
                    'event_category': 'engagement',
                    'event_label': link.textContent.trim() || link.href || 'unknown',
                    'page_location': window.location.href,
                    'page_title': document.title
                });
            }
        });
    });
});

window.addEventListener('beforeunload', function() {
    if (isPageActive) {
        const timeSpent = Math.round((new Date() - lastInteractionTime) / 1000);
        totalTimeSpent += timeSpent;
    }
    
    const totalSessionTime = Math.round((new Date() - startTime) / 1000);
    
    if (typeof gtag === 'function') {
        gtag('event', 'page_exit', {
            'event_category': 'engagement',
            'event_label': 'exit',
            'time_on_page': totalSessionTime,
            'active_time': totalTimeSpent,
            'max_scroll_depth': maxScrollDepth,
            'page_location': window.location.href,
            'page_title': document.title,
            'transport_type': 'beacon'
        });
    }
});

window.trackEvent = function(eventName, eventCategory, eventLabel, eventValue) {
    if (typeof gtag === 'function') {
        gtag('event', eventName, {
            'event_category': eventCategory || 'general',
            'event_label': eventLabel || 'none',
            'value': eventValue || 0,
            'page_location': window.location.href,
            'page_title': document.title
        });
    }
};

window.trackFeatureUsage = function(featureName, featureCategory) {
    if (typeof gtag === 'function') {
        gtag('event', 'feature_used', {
            'event_category': featureCategory || 'feature',
            'event_label': featureName,
            'page_location': window.location.href,
            'page_title': document.title
        });
    }
};

window.trackError = function(errorMessage, errorSource) {
    if (typeof gtag === 'function') {
        gtag('event', 'error', {
            'event_category': 'error',
            'event_label': errorSource || 'javascript',
            'description': errorMessage,
            'page_location': window.location.href,
            'page_title': document.title
        });
    }
};

window.addEventListener('error', function(event) {
    window.trackError(event.message, event.filename);
});