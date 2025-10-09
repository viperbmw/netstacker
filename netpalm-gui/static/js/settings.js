// Settings page JavaScript

// Default settings
const DEFAULT_SETTINGS = {
    netbox_url: 'https://netbox-prprd.gi-nw.viasat.io',
    netbox_token: '',
    netbox_verify_ssl: false,
    netbox_filters: [],
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

    // Add filter button
    $('#add-filter-btn').click(function() {
        addFilterRow();
    });

    // Test Netbox connection button
    $('#test-netbox-btn').click(function() {
        testNetboxConnection();
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

    // Load filters
    loadFilters(settings.netbox_filters || []);

    updateStatus(settings);
}

function saveSettings() {
    // Collect filters
    const filters = [];
    $('.netbox-filter-row').each(function() {
        const key = $(this).find('.filter-key').val().trim();
        const value = $(this).find('.filter-value').val().trim();
        if (key && value) {
            filters.push({ key: key, value: value });
        }
    });

    const settings = {
        netbox_url: $('#netbox-url').val().trim(),
        netbox_token: $('#netbox-token').val().trim(),
        netbox_verify_ssl: $('#netbox-verify-ssl').is(':checked'),
        netbox_filters: filters,
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

    // Clear filters
    loadFilters([]);

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

// Filter management functions
function loadFilters(filters) {
    const container = $('#netbox-filters-container');
    container.empty();

    if (filters.length === 0) {
        // Add one empty filter by default
        addFilterRow();
    } else {
        filters.forEach(function(filter) {
            addFilterRow(filter.key, filter.value);
        });
    }
}

function addFilterRow(key = '', value = '') {
    const container = $('#netbox-filters-container');
    const rowId = 'filter-row-' + Date.now();

    const row = $(`
        <div class="row mb-2 netbox-filter-row" id="${rowId}">
            <div class="col-md-5">
                <input type="text" class="form-control form-control-sm filter-key" placeholder="Filter key (e.g., tag)" value="${key}">
            </div>
            <div class="col-md-5">
                <input type="text" class="form-control form-control-sm filter-value" placeholder="Filter value (e.g., production)" value="${value}">
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-sm btn-outline-danger remove-filter-btn w-100" data-row-id="${rowId}">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `);

    container.append(row);

    // Attach remove handler
    row.find('.remove-filter-btn').on('click', function() {
        const rowIdToRemove = $(this).data('row-id');
        $('#' + rowIdToRemove).remove();

        // If no filters left, add one empty
        if ($('.netbox-filter-row').length === 0) {
            addFilterRow();
        }
    });
}

function testNetboxConnection() {
    const btn = $('#test-netbox-btn');
    const resultDiv = $('#netbox-test-result');

    // Get current values from form
    const netboxUrl = $('#netbox-url').val().trim();
    const netboxToken = $('#netbox-token').val().trim();
    const verifySSL = $('#netbox-verify-ssl').is(':checked');

    // Collect current filters from the form
    const filters = [];
    $('.netbox-filter-row').each(function() {
        const key = $(this).find('.filter-key').val().trim();
        const value = $(this).find('.filter-value').val().trim();
        if (key && value) {
            filters.push({ key: key, value: value });
        }
    });

    if (!netboxUrl) {
        resultDiv.html('<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> Please enter a Netbox URL first</div>').show();
        return;
    }

    // Disable button and show loading
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Testing...');

    let loadingMsg = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Connecting to Netbox...';
    if (filters.length > 0) {
        loadingMsg += '<br><small class="text-muted">Testing with ' + filters.length + ' filter(s)</small>';
    }
    loadingMsg += '</div>';
    resultDiv.html(loadingMsg).show();

    // Send test request
    $.ajax({
        url: '/api/test-netbox',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            netbox_url: netboxUrl,
            netbox_token: netboxToken,
            verify_ssl: verifySSL,
            filters: filters
        }),
        timeout: 35000  // Increased to 35 seconds
    })
    .done(function(data) {
        if (data.success) {
            resultDiv.html(`
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i> <strong>Connection Successful!</strong><br>
                    <small>Found ${data.device_count} devices in Netbox</small><br>
                    <small class="text-muted">Response time: ${data.response_time || 'N/A'}</small>
                </div>
                <details class="mt-2">
                    <summary class="text-muted small" style="cursor: pointer;">
                        <i class="fas fa-info-circle"></i> Show API Details
                    </summary>
                    <div class="card card-body bg-light mt-2">
                        <p class="mb-1"><strong>API URL:</strong></p>
                        <code class="small">${data.api_url || 'N/A'}</code>
                        <p class="mb-1 mt-2"><strong>SSL Verification:</strong> ${data.verify_ssl ? 'Enabled' : 'Disabled'}</p>
                        <p class="mb-0"><strong>Using Token:</strong> ${data.has_token ? 'Yes' : 'No (Public access)'}</p>
                    </div>
                </details>
            `);
        } else {
            resultDiv.html(`
                <div class="alert alert-danger">
                    <i class="fas fa-times-circle"></i> <strong>Connection Failed</strong><br>
                    <small>${data.error || 'Unknown error'}</small>
                </div>
                <details class="mt-2">
                    <summary class="text-muted small" style="cursor: pointer;">
                        <i class="fas fa-info-circle"></i> Show Debug Details
                    </summary>
                    <div class="card card-body bg-light mt-2">
                        <p class="mb-1"><strong>API URL:</strong></p>
                        <code class="small">${data.api_url || 'N/A'}</code>
                        ${data.status_code ? '<p class="mb-1 mt-2"><strong>HTTP Status:</strong> ' + data.status_code + '</p>' : ''}
                        ${data.details ? '<p class="mb-0 mt-2"><strong>Technical Details:</strong><br><small>' + data.details + '</small></p>' : ''}
                    </div>
                </details>
            `);
        }
    })
    .fail(function(xhr) {
        let errorMsg = 'Connection failed';
        let apiUrl = netboxUrl + '/api/dcim/devices/?brief=true&limit=10';
        let details = '';

        if (xhr.responseJSON) {
            errorMsg = xhr.responseJSON.error || errorMsg;
            apiUrl = xhr.responseJSON.api_url || apiUrl;
            details = xhr.responseJSON.details || '';
        } else if (xhr.statusText) {
            errorMsg = xhr.statusText;
        }

        resultDiv.html(`
            <div class="alert alert-danger">
                <i class="fas fa-times-circle"></i> <strong>Connection Failed</strong><br>
                <small>${errorMsg}</small>
            </div>
            <details class="mt-2">
                <summary class="text-muted small" style="cursor: pointer;">
                    <i class="fas fa-info-circle"></i> Show Debug Details
                </summary>
                <div class="card card-body bg-light mt-2">
                    <p class="mb-1"><strong>API URL:</strong></p>
                    <code class="small">${apiUrl}</code>
                    ${details ? '<p class="mb-0 mt-2"><strong>Technical Details:</strong><br><small>' + details + '</small></p>' : ''}
                </div>
            </details>
        `);
    })
    .always(function() {
        btn.prop('disabled', false).html('<i class="fas fa-plug"></i> Test Netbox Connection');
    });
}

// Export getSettings for use in other pages
window.getAppSettings = getSettings;
