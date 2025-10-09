$(document).ready(function() {
    loadServiceTemplates();
    loadServiceInstances();

    $('#refresh-templates-btn').on('click', function() {
        loadServiceTemplates();
    });

    $('#refresh-instances-btn').on('click', function() {
        loadServiceInstances();
    });

    $('#create-service-btn').on('click', function() {
        createServiceInstance();
    });
});

function loadServiceTemplates() {
    $('#service-templates-loading').show();
    $('#service-templates-list').hide();
    $('#service-templates-error').hide();

    // Load J2 templates instead of Python services
    $.get('/api/templates')
        .done(function(data) {
            $('#service-templates-loading').hide();
            if (data.success && data.templates && data.templates.length > 0) {
                renderServiceTemplates(data.templates);
                $('#service-templates-list').show();
            } else {
                $('#service-templates-error').html('<i class="fas fa-exclamation-triangle"></i> No config templates found').show();
            }
        })
        .fail(function(xhr) {
            $('#service-templates-loading').hide();
            const errorMsg = xhr.responseJSON?.error || 'Failed to load config templates';
            $('#service-templates-error').text(errorMsg).show();
        });
}

function renderServiceTemplates(templates) {
    const grid = $('#templates-grid');
    grid.empty();

    // Auto-detect template descriptions from name
    templates.forEach(function(template) {
        // Clean up template name for display
        const displayName = template
            .replace('.j2', '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());

        // Determine icon based on template name
        let icon = 'fa-file-code';

        if (template.includes('vlan')) {
            icon = 'fa-network-wired';
        } else if (template.includes('snmp')) {
            icon = 'fa-chart-line';
        } else if (template.includes('interface') || template.includes('int')) {
            icon = 'fa-ethernet';
        } else if (template.includes('remove')) {
            icon = 'fa-trash';
        }

        const card = `
            <div class="col-md-4 col-lg-3 mb-2">
                <div class="card service-template-card" style="cursor: pointer;">
                    <div class="card-body p-2">
                        <div class="d-flex align-items-center">
                            <i class="fas ${icon} text-primary me-2"></i>
                            <div class="flex-grow-1">
                                <div class="fw-bold small">${displayName}</div>
                                <small class="text-muted" style="font-size: 0.75rem;">${template}</small>
                            </div>
                            <button class="btn btn-sm btn-primary create-service-btn" data-template="${template}" title="Use Template">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        grid.append(card);
    });

    $('.create-service-btn').on('click', function(e) {
        e.stopPropagation();
        const templateName = $(this).data('template');
        openCreateServiceModal(templateName);
    });
}

function openCreateServiceModal(templateName) {
    $('#create-service-name').val(templateName);

    const modal = new bootstrap.Modal(document.getElementById('createServiceModal'));
    modal.show();

    // Load devices and all templates for reverse template selection
    Promise.all([
        loadDevicesForService(),
        $.get('/api/templates')
    ])
    .then(function([devices, templatesData]) {
        renderSimpleServiceForm(templateName, devices, templatesData.templates);
    })
    .catch(function(error) {
        console.error('Error loading form data:', error);
        $('#create-service-form-container').html('<div class="alert alert-danger">Error loading form. Please try again.</div>');
    });
}

function renderSimpleServiceForm(templateName, devices, allTemplates) {
    // Build simple template-based form with dynamic variable loading
    const formHtml = `
        <div class="mb-3">
            <label class="form-label">Service Name *</label>
            <input type="text" class="form-control" id="service-name-input"
                   placeholder="e.g., Guest VLAN on Access Switches" required>
            <small class="text-muted">Give this service instance a descriptive name</small>
        </div>

        <div class="mb-3">
            <label class="form-label">Template</label>
            <input type="text" class="form-control" value="${templateName}" readonly>
            <small class="text-muted">The Jinja2 config template to use</small>
        </div>

        <div class="mb-3">
            <label class="form-label">Device *</label>
            <select class="form-select" id="device-select-input" required>
                <option value="">Select device...</option>
                ${devices.map(d => `<option value="${d.name}">${d.display || d.name}</option>`).join('')}
            </select>
            <small class="text-muted">Target device for configuration</small>
        </div>

        <div class="mb-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <label class="form-label mb-0">Template Variables *</label>
                <div id="service-template-vars-toggle"></div>
            </div>
            <div id="service-template-vars-container"></div>
        </div>

        <div class="mb-3">
            <label class="form-label">Reverse Template (Optional)</label>
            <select class="form-select" id="reverse-template-input">
                <option value="">None - manual cleanup required</option>
                ${allTemplates.filter(t => t.includes('remove') || t.includes('delete')).map(t =>
                    `<option value="${t}">${t}</option>`
                ).join('')}
            </select>
            <small class="text-muted">Template to remove the configuration when service is deleted</small>
        </div>

        <div class="mb-3">
            <div class="d-flex justify-content-between align-items-center">
                <label class="form-label mb-0">Credentials</label>
                <button class="btn btn-sm btn-link" type="button" data-bs-toggle="collapse" data-bs-target="#service-credentials-section">
                    <i class="fas fa-chevron-down"></i> <span id="service-cred-status">Using defaults</span>
                </button>
            </div>
            <div class="collapse" id="service-credentials-section">
                <div class="card card-body mt-2">
                    <div class="mb-3">
                        <label for="service-username" class="form-label">Username</label>
                        <input type="text" class="form-control" id="service-username">
                        <small class="form-text text-muted">Leave blank to use default from settings</small>
                    </div>
                    <div class="mb-3">
                        <label for="service-password" class="form-label">Password</label>
                        <input type="password" class="form-control" id="service-password">
                        <small class="form-text text-muted">Leave blank to use default from settings</small>
                    </div>
                </div>
            </div>
        </div>
    `;

    $('#create-service-form-container').html(formHtml);

    // Setup dynamic template variable loading with form/JSON toggle
    setupServiceTemplateVariableToggle(templateName);
}

function setupServiceTemplateVariableToggle(templateName) {
    const container = $('#service-template-vars-container');
    const toggleContainer = $('#service-template-vars-toggle');
    let currentMode = 'form';

    // Create toggle buttons
    const toggleHTML = `
        <div class="btn-group" role="group">
            <input type="radio" class="btn-check" name="service-var-input-mode" id="service-var-mode-form" value="form" checked autocomplete="off">
            <label class="btn btn-outline-primary btn-sm" for="service-var-mode-form">
                <i class="fas fa-list"></i> Form
            </label>

            <input type="radio" class="btn-check" name="service-var-input-mode" id="service-var-mode-json" value="json" autocomplete="off">
            <label class="btn btn-outline-primary btn-sm" for="service-var-mode-json">
                <i class="fas fa-code"></i> JSON
            </label>
        </div>
    `;

    toggleContainer.html(toggleHTML);

    // Load template variables initially in form mode
    loadServiceTemplateVariables(templateName, container, currentMode);

    // Mode toggle handler
    $('input[name="service-var-input-mode"]').change(function() {
        currentMode = $(this).val();
        loadServiceTemplateVariables(templateName, container, currentMode);
    });
}

function loadServiceTemplateVariables(templateName, container, inputMode) {
    container.show();
    container.html('<div class="text-center"><div class="spinner-border spinner-border-sm"></div> Loading variables...</div>');

    $.get('/api/templates/' + encodeURIComponent(templateName) + '/variables')
        .done(function(data) {
            if (data.success && data.variables) {
                if (inputMode === 'form') {
                    renderServiceVariableForm(data.variables, container);
                } else {
                    renderServiceVariableJSON(data.variables, container);
                }
                container.show();
            } else {
                container.html('<div class="alert alert-warning">No variables found in template</div>');
                container.show();
            }
        })
        .fail(function() {
            container.html('<div class="alert alert-danger">Failed to load template variables</div>');
            container.show();
        });
}

function renderServiceVariableForm(variables, container) {
    if (variables.length === 0) {
        container.html('<div class="alert alert-info">This template has no variables</div>');
        return;
    }

    let html = '<div class="service-template-variables-form">';

    variables.forEach(function(variable) {
        const fieldId = 'service-template-var-' + variable;
        const label = variable.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        html += `
            <div class="mb-3">
                <label for="${fieldId}" class="form-label">${label}</label>
                <input type="text" class="form-control service-template-var-input"
                       id="${fieldId}"
                       data-var-name="${variable}"
                       placeholder="Enter ${label.toLowerCase()}">
            </div>
        `;
    });

    html += '</div>';
    container.html(html);
}

function renderServiceVariableJSON(variables, container) {
    if (variables.length === 0) {
        container.html('<div class="alert alert-info">This template has no variables</div>');
        return;
    }

    // Create example JSON object
    const exampleObj = {};
    variables.forEach(function(variable) {
        exampleObj[variable] = '';
    });

    const exampleJSON = JSON.stringify(exampleObj, null, 2);

    const html = `
        <div class="mb-3">
            <textarea class="form-control font-monospace service-template-vars-json" rows="8" placeholder='${exampleJSON}'></textarea>
            <small class="form-text text-muted">Enter variables as JSON object</small>
        </div>
    `;

    container.html(html);
}

function loadDevicesForService() {
    // Get filters from settings
    let filters = [];
    try {
        const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');
        filters = settings.netbox_filters || [];
    } catch (e) {
        console.error('Error reading filters from settings:', e);
    }

    // Make POST request with filters
    return $.ajax({
        url: '/api/devices',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ filters: filters })
    }).then(function(data) {
        if (data.success && data.devices) {
            return data.devices;
        }
        return [];
    }).catch(function() {
        return [];
    });
}

function renderServiceForm(schema, devices) {
    let html = '<div class="service-form">';

    // Add schema description if available
    if (schema.description) {
        html += `<div class="alert alert-info mb-3"><i class="fas fa-info-circle"></i> ${schema.description}</div>`;
    }

    if (schema.properties) {
        Object.keys(schema.properties).forEach(function(fieldName) {
            const field = schema.properties[fieldName];
            const required = schema.required && schema.required.includes(fieldName);
            const fieldId = 'service-field-' + fieldName;
            const label = field.title || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

            // Skip hidden_default fields
            if (field.format === 'hidden_default') {
                return;
            }

            html += `
                <div class="mb-3">
                    <label for="${fieldId}" class="form-label">
                        ${label}
                        ${required ? '<span class="text-danger">*</span>' : ''}
                    </label>
            `;

            // Determine input type based on field type and format
            if (field.format === 'device_select') {
                // Device dropdown
                html += `<select class="form-select service-field" id="${fieldId}" data-field-name="${fieldName}" ${required ? 'required' : ''}>`;
                html += '<option value="">Select a device...</option>';
                if (devices && devices.length > 0) {
                    devices.forEach(function(device) {
                        html += `<option value="${device.name}">${device.display || device.name}</option>`;
                    });
                }
                html += '</select>';
            } else if (field.type === 'integer' || field.type === 'number') {
                const min = field.minimum !== undefined ? `min="${field.minimum}"` : '';
                const max = field.maximum !== undefined ? `max="${field.maximum}"` : '';
                const defaultVal = field.default !== undefined ? `value="${field.default}"` : '';
                html += `<input type="number" class="form-control service-field" id="${fieldId}" data-field-name="${fieldName}" ${min} ${max} ${defaultVal} ${required ? 'required' : ''}>`;
            } else if (field.type === 'boolean') {
                const defaultVal = field.default !== undefined ? field.default : '';
                html += `
                    <select class="form-select service-field" id="${fieldId}" data-field-name="${fieldName}" ${required ? 'required' : ''}>
                        <option value="">Select...</option>
                        <option value="true" ${defaultVal === true ? 'selected' : ''}>True</option>
                        <option value="false" ${defaultVal === false ? 'selected' : ''}>False</option>
                    </select>
                `;
            } else if (field.enum) {
                const defaultVal = field.default || '';
                html += `<select class="form-select service-field" id="${fieldId}" data-field-name="${fieldName}" ${required ? 'required' : ''}>`;
                html += '<option value="">Select...</option>';
                field.enum.forEach(function(option) {
                    const selected = option === defaultVal ? 'selected' : '';
                    html += `<option value="${option}" ${selected}>${option}</option>`;
                });
                html += '</select>';
            } else if (field.type === 'array') {
                // Handle arrays (like interfaces)
                html += `<input type="text" class="form-control service-field" id="${fieldId}" data-field-name="${fieldName}" data-field-type="array" placeholder="Comma-separated values" ${required ? 'required' : ''}>`;
            } else if (field.format === 'password') {
                // Password field
                const defaultVal = field.default !== undefined ? `value="${field.default}"` : '';
                html += `<input type="password" class="form-control service-field" id="${fieldId}" data-field-name="${fieldName}" ${defaultVal} ${required ? 'required' : ''}>`;
            } else {
                // Text field
                const defaultVal = field.default !== undefined ? `value="${field.default}"` : '';
                const minLength = field.minLength !== undefined ? `minlength="${field.minLength}"` : '';
                const maxLength = field.maxLength !== undefined ? `maxlength="${field.maxLength}"` : '';
                html += `<input type="text" class="form-control service-field" id="${fieldId}" data-field-name="${fieldName}" ${defaultVal} ${minLength} ${maxLength} ${required ? 'required' : ''}>`;
            }

            if (field.description) {
                html += `<small class="form-text text-muted">${field.description}</small>`;
            }

            html += '</div>';
        });
    } else {
        // Fallback to JSON input
        html += '<div class="alert alert-info">Please provide service parameters as JSON</div>';
        html += '<textarea class="form-control" id="service-json-payload" rows="10" placeholder="Enter service parameters as JSON"></textarea>';
    }

    html += '</div>';
    $('#create-service-form-container').html(html);
}

function createServiceInstance() {
    // Get values from the simple form
    const serviceName = $('#service-name-input').val();
    const templateName = $('#create-service-name').val();
    const device = $('#device-select-input').val();
    const reverseTemplate = $('#reverse-template-input').val();

    // Validate required fields
    if (!serviceName || !templateName || !device) {
        showStatus('error', { message: 'Please fill in all required fields' });
        return;
    }

    // Get template variables - collect from dynamic form or JSON input
    let variables = {};

    // Check if using JSON mode
    const jsonTextarea = $('.service-template-vars-json');
    if (jsonTextarea.length > 0 && jsonTextarea.val().trim()) {
        try {
            variables = JSON.parse(jsonTextarea.val());
        } catch (e) {
            showStatus('error', { message: 'Invalid JSON in template variables: ' + e.message });
            return;
        }
    } else {
        // Collect from form mode
        const formInputs = $('.service-template-var-input');
        if (formInputs.length > 0) {
            formInputs.each(function() {
                const varName = $(this).data('var-name');
                const value = $(this).val().trim();
                if (value) {
                    // Try to parse as number if possible
                    if (!isNaN(value) && value !== '') {
                        variables[varName] = parseFloat(value);
                    } else {
                        variables[varName] = value;
                    }
                }
            });
        }
    }

    // Validate we have at least some variables
    if (Object.keys(variables).length === 0) {
        showStatus('error', { message: 'Please fill in at least one template variable' });
        return;
    }

    // Get credentials - check for override first
    const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');
    const username = $('#service-username').val() || settings.default_username;
    const password = $('#service-password').val() || settings.default_password;

    // Build payload for new template service API
    const payload = {
        name: serviceName,
        template: templateName,
        variables: variables,
        device: device,
        username: username,
        password: password
    };

    // Add reverse template if specified
    if (reverseTemplate) {
        payload.reverse_template = reverseTemplate;
    }

    $('#create-service-btn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Creating...');

    $.ajax({
        url: '/api/services/instances/create',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload)
    })
    .done(function(data) {
        $('#create-service-btn').prop('disabled', false).html('<i class="fas fa-rocket"></i> Create Service');

        if (data.success) {
            showStatus('success', {
                message: data.message || 'Service instance created successfully!',
                task_id: data.task_id,
                service_id: data.service_id
            });
            bootstrap.Modal.getInstance(document.getElementById('createServiceModal')).hide();
            loadServiceInstances();
        } else {
            showStatus('error', data);
        }
    })
    .fail(function(xhr) {
        $('#create-service-btn').prop('disabled', false).html('<i class="fas fa-rocket"></i> Create Service');
        const errorMsg = xhr.responseJSON?.error || 'Failed to create service instance';
        showStatus('error', { message: errorMsg });
    });
}

function validateServiceInstance(serviceId) {
    // Get default credentials from settings
    const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');

    const payload = {
        username: settings.default_username,
        password: settings.default_password
    };

    // Show loading status
    showStatus('info', { message: 'Validating service configuration...' });

    $.ajax({
        url: '/api/services/instances/' + encodeURIComponent(serviceId) + '/validate',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        timeout: 60000 // 60 second timeout for validation
    })
    .done(function(data) {
        if (data.success) {
            if (data.valid) {
                showStatus('success', {
                    message: data.message || 'Configuration is present on device',
                    task_id: data.task_id
                });
            } else {
                showStatus('warning', {
                    message: data.message || 'Configuration drift detected',
                    details: 'Missing lines: ' + data.missing_lines.join(', ')
                });
            }
            loadServiceInstances(); // Reload to show updated validation status
        } else {
            showStatus('error', data);
        }
    })
    .fail(function(xhr) {
        const errorMsg = xhr.responseJSON?.error || 'Failed to validate service instance';
        showStatus('error', { message: errorMsg });
    });
}

function deleteServiceInstance(serviceId) {
    // Get default credentials from settings for reverse template execution
    const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');

    const payload = {
        username: settings.default_username,
        password: settings.default_password
    };

    $.ajax({
        url: '/api/services/instances/' + encodeURIComponent(serviceId) + '/delete',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload)
    })
    .done(function(data) {
        if (data.success) {
            showStatus('success', {
                message: data.message || 'Service deleted successfully!',
                task_id: data.task_id
            });
            loadServiceInstances();
        } else {
            showStatus('error', data);
        }
    })
    .fail(function(xhr) {
        const errorMsg = xhr.responseJSON?.error || 'Failed to delete service instance';
        showStatus('error', { message: errorMsg });
    });
}

function loadServiceInstances() {
    $('#service-instances-loading').show();
    $('#service-instances-table').hide();
    $('#service-instances-empty').hide();
    $('#service-instances-error').hide();

    $.get('/api/services/instances')
        .done(function(data) {
            $('#service-instances-loading').hide();

            if (data.success && data.instances && data.instances.length > 0) {
                renderServiceInstances(data.instances);
                $('#service-instances-table').show();
            } else {
                $('#service-instances-empty').show();
            }
        })
        .fail(function(xhr) {
            $('#service-instances-loading').hide();
            const errorMsg = xhr.responseJSON?.error || 'Failed to load service instances';
            $('#service-instances-error').text(errorMsg).show();
        });
}

function renderServiceInstances(instances) {
    const tbody = $('#instances-tbody');
    tbody.empty();

    instances.forEach(function(instance) {
        const stateClass = getStateClass(instance.state);
        const stateIcon = getStateIcon(instance.state);

        const row = `
            <tr>
                <td><code>${instance.service_id || 'N/A'}</code></td>
                <td>
                    <strong>${instance.name || 'N/A'}</strong><br>
                    <small class="text-muted"><i class="fas fa-file-code"></i> ${instance.template}</small><br>
                    <small class="text-muted"><i class="fas fa-server"></i> ${instance.device}</small>
                </td>
                <td><span class="badge ${stateClass}">${stateIcon} ${instance.state || 'unknown'}</span></td>
                <td><small>${formatDate(instance.created_at)}</small></td>
                <td><small>${formatDate(instance.updated_at)}</small></td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary view-service-btn" data-service-id="${instance.service_id}" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-outline-success validate-service-btn" data-service-id="${instance.service_id}" title="Validate Config">
                            <i class="fas fa-check-circle"></i>
                        </button>
                        <button class="btn btn-outline-danger delete-service-btn" data-service-id="${instance.service_id}" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        tbody.append(row);
    });

    // Attach event handlers
    $('.view-service-btn').on('click', function() {
        viewServiceDetails($(this).data('service-id'));
    });

    $('.validate-service-btn').on('click', function() {
        validateServiceInstance($(this).data('service-id'));
    });

    $('.delete-service-btn').on('click', function() {
        if (confirm('Are you sure you want to delete this service instance? This will remove the configuration from the device if a reverse template is defined.')) {
            deleteServiceInstance($(this).data('service-id'));
        }
    });
}

function viewServiceDetails(serviceId) {
    $('#service-details-content').html('<div class="text-center"><div class="spinner-border"></div><p>Loading...</p></div>');
    const modal = new bootstrap.Modal(document.getElementById('serviceDetailsModal'));
    modal.show();

    $.get('/api/services/instances/' + encodeURIComponent(serviceId))
        .done(function(data) {
            if (data.success && data.instance) {
                renderServiceDetails(data.instance);
            } else {
                $('#service-details-content').html('<div class="alert alert-danger">Failed to load service details</div>');
            }
        })
        .fail(function() {
            $('#service-details-content').html('<div class="alert alert-danger">Failed to load service details</div>');
        });
}

function renderServiceDetails(instance) {
    const html = `
        <div class="row">
            <div class="col-md-6">
                <h6>Service Information</h6>
                <table class="table table-sm">
                    <tr><th>Service ID:</th><td><code>${instance.service_id || 'N/A'}</code></td></tr>
                    <tr><th>Name:</th><td><strong>${instance.name || 'N/A'}</strong></td></tr>
                    <tr><th>Template:</th><td><code>${instance.template || 'N/A'}</code></td></tr>
                    <tr><th>Reverse Template:</th><td><code>${instance.reverse_template || 'None'}</code></td></tr>
                    <tr><th>Device:</th><td>${instance.device || 'N/A'}</td></tr>
                    <tr><th>State:</th><td><span class="badge ${getStateClass(instance.state)}">${instance.state || 'unknown'}</span></td></tr>
                    <tr><th>Created:</th><td>${formatDate(instance.created_at)}</td></tr>
                    <tr><th>Updated:</th><td>${formatDate(instance.updated_at)}</td></tr>
                    ${instance.task_id ? `<tr><th>Task ID:</th><td><code>${instance.task_id}</code></td></tr>` : ''}
                </table>
            </div>
            <div class="col-md-6">
                <h6>Template Variables</h6>
                <pre class="bg-dark text-light p-3 rounded" style="max-height: 200px; overflow-y: auto;"><code>${JSON.stringify(instance.variables || {}, null, 2)}</code></pre>

                ${instance.rendered_config ? `
                    <h6 class="mt-3">Rendered Configuration</h6>
                    <pre class="bg-dark text-light p-3 rounded" style="max-height: 200px; overflow-y: auto;"><code>${instance.rendered_config}</code></pre>
                ` : ''}
            </div>
        </div>
    `;

    $('#service-details-content').html(html);
}

function serviceAction(serviceId, action) {
    const actionText = action.charAt(0).toUpperCase() + action.slice(1);

    $.ajax({
        url: '/api/services/instances/' + encodeURIComponent(serviceId) + '/' + action,
        method: 'POST'
    })
    .done(function(data) {
        if (data.success) {
            showStatus('success', {
                message: actionText + ' completed successfully!',
                task_id: data.task_id
            });
            if (action === 'delete') {
                loadServiceInstances();
            }
        } else {
            showStatus('error', data);
        }
    })
    .fail(function(xhr) {
        const errorMsg = xhr.responseJSON?.error || actionText + ' failed';
        showStatus('error', { message: errorMsg });
    });
}

function getStateClass(state) {
    switch(state) {
        case 'active': return 'bg-success';
        case 'creating': return 'bg-info';
        case 'updating': return 'bg-warning';
        case 'deleting': return 'bg-warning';
        case 'errored': return 'bg-danger';
        case 'deployed': return 'bg-success';
        case 'deploying': return 'bg-info';
        default: return 'bg-secondary';
    }
}

function getStateIcon(state) {
    switch(state) {
        case 'active': return '<i class="fas fa-check-circle"></i>';
        case 'creating': return '<i class="fas fa-spinner fa-spin"></i>';
        case 'updating': return '<i class="fas fa-sync fa-spin"></i>';
        case 'deleting': return '<i class="fas fa-trash-alt"></i>';
        case 'errored': return '<i class="fas fa-exclamation-triangle"></i>';
        case 'deployed': return '<i class="fas fa-check"></i>';
        case 'deploying': return '<i class="fas fa-spinner fa-spin"></i>';
        default: return '<i class="fas fa-question"></i>';
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function showStatus(type, data) {
    const modal = new bootstrap.Modal(document.getElementById('statusModal'));
    $('#statusModalTitle').text(type === 'success' ? 'Success' : 'Error');

    let html = '';
    if (type === 'success') {
        html = '<div class="alert alert-success"><i class="fas fa-check-circle"></i> ' + (data.message || 'Operation successful') + '</div>';
        if (data.task_id) {
            html += '<p><strong>Task ID:</strong> <code>' + data.task_id + '</code></p>';
        }
        if (data.service_id) {
            html += '<p><strong>Service ID:</strong> <code>' + data.service_id + '</code></p>';
        }
    } else {
        html = '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> ' + (data.message || 'Operation failed') + '</div>';
    }

    $('#statusModalBody').html(html);
    modal.show();
}
