// Settings page JavaScript

// Default settings
const DEFAULT_SETTINGS = {
    netbox_url: 'https://netbox-prprd.gi-nw.viasat.io',
    netbox_token: '',
    netbox_verify_ssl: false,
    default_username: '',
    default_password: '',
    netpalm_url: 'http://netpalm-controller:9000',
    netpalm_api_key: '2a84465a-cf38-46b2-9d86-b84Q7d57f288',
    cache_ttl: 300
};

$(document).ready(function() {
    loadSettings();

    // Save settings form submit
    $('#settings-form').submit(function(e) {
        e.preventDefault();
        saveSettings();
    });

    // Reset to defaults
    $('#reset-btn').click(function() {
        if (confirm('Are you sure you want to reset all settings to defaults?')) {
            resetToDefaults();
        }
    });

    // Clear all data
    $('#clear-all-btn').click(function() {
        if (confirm('This will clear all settings and cached data. Are you sure?')) {
            clearAllData();
        }
    });
});

function loadSettings() {
    // Get settings from localStorage
    const settings = getSettings();

    // Populate form
    $('#netbox-url').val(settings.netbox_url);
    $('#netbox-token').val(settings.netbox_token);
    $('#netbox-verify-ssl').prop('checked', settings.netbox_verify_ssl);
    $('#default-username').val(settings.default_username);
    $('#default-password').val(settings.default_password);
    $('#netpalm-url').val(settings.netpalm_url);
    $('#netpalm-api-key').val(settings.netpalm_api_key);
    $('#cache-ttl').val(settings.cache_ttl);

    updateStatus(settings);
}

function saveSettings() {
    const settings = {
        netbox_url: $('#netbox-url').val().trim(),
        netbox_token: $('#netbox-token').val().trim(),
        netbox_verify_ssl: $('#netbox-verify-ssl').is(':checked'),
        default_username: $('#default-username').val().trim(),
        default_password: $('#default-password').val().trim(),
        netpalm_url: $('#netpalm-url').val().trim(),
        netpalm_api_key: $('#netpalm-api-key').val().trim(),
        cache_ttl: parseInt($('#cache-ttl').val())
    };

    // Validate
    if (!settings.netbox_url) {
        alert('Netbox URL is required');
        return;
    }

    if (!settings.netpalm_url) {
        alert('Netpalm URL is required');
        return;
    }

    if (settings.cache_ttl < 60 || settings.cache_ttl > 3600) {
        alert('Cache TTL must be between 60 and 3600 seconds');
        return;
    }

    // Save to localStorage
    localStorage.setItem('netpalm_gui_settings', JSON.stringify(settings));

    // Show success message
    showNotification('Settings saved successfully!', 'success');

    updateStatus(settings);
}

function getSettings() {
    const stored = localStorage.getItem('netpalm_gui_settings');
    if (stored) {
        try {
            return JSON.parse(stored);
        } catch (e) {
            console.error('Error parsing stored settings:', e);
            return DEFAULT_SETTINGS;
        }
    }
    return DEFAULT_SETTINGS;
}

function resetToDefaults() {
    // Set form to defaults
    $('#netbox-url').val(DEFAULT_SETTINGS.netbox_url);
    $('#netbox-token').val(DEFAULT_SETTINGS.netbox_token);
    $('#netbox-verify-ssl').prop('checked', DEFAULT_SETTINGS.netbox_verify_ssl);
    $('#default-username').val(DEFAULT_SETTINGS.default_username);
    $('#default-password').val(DEFAULT_SETTINGS.default_password);
    $('#netpalm-url').val(DEFAULT_SETTINGS.netpalm_url);
    $('#netpalm-api-key').val(DEFAULT_SETTINGS.netpalm_api_key);
    $('#cache-ttl').val(DEFAULT_SETTINGS.cache_ttl);

    // Save defaults
    localStorage.setItem('netpalm_gui_settings', JSON.stringify(DEFAULT_SETTINGS));

    showNotification('Settings reset to defaults', 'info');
    updateStatus(DEFAULT_SETTINGS);
}

function clearAllData() {
    // Clear all localStorage
    localStorage.clear();

    // Reset form
    resetToDefaults();

    showNotification('All data cleared successfully', 'warning');
}

function updateStatus(settings) {
    const statusEl = $('#settings-status');
    statusEl.empty();

    let configured = true;
    let issues = [];

    if (!settings.netbox_token) {
        issues.push('Netbox token not set');
        configured = false;
    }

    if (!settings.default_username) {
        issues.push('Default credentials not set');
    }

    if (configured && issues.length === 0) {
        statusEl.html('<span class="badge bg-success">Fully Configured</span>');
    } else if (configured) {
        statusEl.html('<span class="badge bg-warning">Partially Configured</span>');
        issues.forEach(function(issue) {
            statusEl.append(`<br><small class="text-muted">- ${issue}</small>`);
        });
    } else {
        statusEl.html('<span class="badge bg-danger">Not Configured</span>');
        issues.forEach(function(issue) {
            statusEl.append(`<br><small class="text-muted">- ${issue}</small>`);
        });
    }
}

function showNotification(message, type) {
    // Create Bootstrap alert
    const alertClass = type === 'success' ? 'alert-success' :
                      type === 'warning' ? 'alert-warning' :
                      type === 'info' ? 'alert-info' : 'alert-danger';

    const alert = $(`
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3" role="alert" style="z-index: 9999; min-width: 300px;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);

    $('body').append(alert);

    // Auto-dismiss after 3 seconds
    setTimeout(function() {
        alert.alert('close');
    }, 3000);
}

// Export getSettings for use in other pages
window.getAppSettings = getSettings;
