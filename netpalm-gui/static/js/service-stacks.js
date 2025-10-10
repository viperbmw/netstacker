// Service Stacks Management
let allDevices = [];
let allTemplates = [];
let serviceCounter = 0;

$(document).ready(function() {
    // Load initial data
    loadDevices();
    loadTemplates();
    loadServiceStacks();

    // Event handlers
    $('#create-stack-btn').click(function() {
        openStackModal();
    });

    $('#save-stack-btn').click(function() {
        saveServiceStack();
    });

    $('#add-service-btn').click(function() {
        addServiceToStack();
    });

    $('#add-shared-var-btn').click(function() {
        addSharedVariable();
    });
});

/**
 * Load devices from API
 */
function loadDevices() {
    // Get filters from settings
    let filters = [];
    try {
        const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');
        filters = settings.netbox_filters || [];
    } catch (e) {
        console.error('Error reading filters from settings:', e);
    }

    // Make POST request with filters
    $.ajax({
        url: '/api/devices',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ filters: filters })
    })
    .done(function(data) {
        if (data.success && data.devices) {
            allDevices = data.devices;
            console.log('Loaded ' + allDevices.length + ' devices');
        }
    })
    .fail(function() {
        console.error('Failed to load devices');
    });
}

/**
 * Load templates from API
 */
function loadTemplates() {
    $.get('/api/templates')
        .done(function(data) {
            if (data.success && data.templates) {
                allTemplates = data.templates;
            }
        })
        .fail(function() {
            console.error('Failed to load templates');
        });
}

/**
 * Load and display all service stacks
 */
function loadServiceStacks() {
    const container = $('#stacks-container');
    container.html('<div class="text-center"><div class="spinner-border"></div></div>');

    $.get('/api/service-stacks')
        .done(function(data) {
            if (data.success && data.stacks) {
                renderServiceStacks(data.stacks);
            } else {
                container.html('<div class="alert alert-warning">No service stacks found</div>');
            }
        })
        .fail(function() {
            container.html('<div class="alert alert-danger">Failed to load service stacks</div>');
        });
}

/**
 * Render service stacks as cards
 */
function renderServiceStacks(stacks) {
    const container = $('#stacks-container');

    if (stacks.length === 0) {
        container.html('<div class="alert alert-info">No service stacks created yet. Click "Create Stack" to get started.</div>');
        return;
    }

    let html = '<div class="row">';

    stacks.forEach(function(stack) {
        const stateColors = {
            'pending': 'secondary',
            'deploying': 'warning',
            'deployed': 'success',
            'failed': 'danger'
        };

        const stateColor = stateColors[stack.state] || 'secondary';

        // Calculate unique device count from all services
        const allDevicesInStack = new Set();
        if (stack.services && Array.isArray(stack.services)) {
            stack.services.forEach(service => {
                if (service.devices && Array.isArray(service.devices)) {
                    service.devices.forEach(device => allDevicesInStack.add(device));
                } else if (service.device) {
                    allDevicesInStack.add(service.device);
                }
            });
        }
        const deviceCount = allDevicesInStack.size;
        const deviceList = Array.from(allDevicesInStack);
        const serviceCount = stack.services ? stack.services.length : 0;

        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="card h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">${stack.name}</h6>
                        <span class="badge bg-${stateColor}">${stack.state}</span>
                    </div>
                    <div class="card-body">
                        ${stack.description ? `<p class="text-muted small">${stack.description}</p>` : ''}

                        <div class="mb-2">
                            <small>
                                <i class="fas fa-cogs text-primary"></i> <strong>${serviceCount}</strong> service${serviceCount !== 1 ? 's' : ''}
                            </small>
                        </div>

                        <div class="mb-2">
                            <small>
                                <i class="fas fa-server text-info"></i> <strong>${deviceCount}</strong> device${deviceCount !== 1 ? 's' : ''}
                            </small>
                        </div>

                        ${deviceList.length > 0 ? `
                            <div class="mb-2">
                                <small class="text-muted">
                                    ${deviceList.slice(0, 3).join(', ')}${deviceList.length > 3 ? '...' : ''}
                                </small>
                            </div>
                        ` : ''}

                        <div class="mt-3">
                            <small class="text-muted">
                                Created: ${new Date(stack.created_at).toLocaleString()}
                            </small>
                        </div>
                    </div>
                    <div class="card-footer bg-transparent">
                        <div class="btn-group w-100" role="group">
                            <button class="btn btn-sm btn-outline-primary view-stack-btn" data-stack-id="${stack.stack_id}">
                                <i class="fas fa-eye"></i> View
                            </button>
                            <button class="btn btn-sm btn-outline-secondary edit-stack-btn" data-stack-id="${stack.stack_id}">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                            ${stack.state === 'deployed' ? `
                                <button class="btn btn-sm btn-outline-info validate-stack-btn" data-stack-id="${stack.stack_id}">
                                    <i class="fas fa-check-circle"></i> Validate
                                </button>
                            ` : ''}
                            ${stack.state === 'pending' || stack.state === 'deploying' ? `
                                <button class="btn btn-sm btn-outline-success deploy-stack-btn" data-stack-id="${stack.stack_id}" ${stack.state === 'deploying' ? 'disabled' : ''}>
                                    <i class="fas fa-rocket"></i> ${stack.state === 'deploying' ? 'Deploying...' : 'Deploy'}
                                </button>
                            ` : `
                                <button class="btn btn-sm btn-outline-warning redeploy-stack-btn" data-stack-id="${stack.stack_id}">
                                    <i class="fas fa-redo"></i> Redeploy
                                </button>
                            `}
                            <button class="btn btn-sm btn-outline-danger delete-stack-btn" data-stack-id="${stack.stack_id}">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.html(html);

    // Attach event handlers
    $('.view-stack-btn').click(function() {
        const stackId = $(this).data('stack-id');
        viewStackDetails(stackId);
    });

    $('.edit-stack-btn').click(function() {
        const stackId = $(this).data('stack-id');
        editStack(stackId);
    });

    $('.deploy-stack-btn').click(function() {
        const stackId = $(this).data('stack-id');
        deployStack(stackId);
    });

    $('.validate-stack-btn').click(function() {
        const stackId = $(this).data('stack-id');
        validateStack(stackId);
    });

    $('.redeploy-stack-btn').click(function() {
        const stackId = $(this).data('stack-id');
        redeployStack(stackId);
    });

    $('.delete-stack-btn').click(function() {
        const stackId = $(this).data('stack-id');
        deleteStack(stackId);
    });
}

/**
 * Redeploy an existing stack
 */
function redeployStack(stackId) {
    if (!confirm('Redeploy this service stack? This will deploy the configuration to all devices again.')) {
        return;
    }

    // Reset stack state to pending before deploying
    $.ajax({
        url: '/api/service-stacks/' + encodeURIComponent(stackId),
        method: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({ state: 'pending' })
    })
    .done(function() {
        // Now deploy
        deployStack(stackId);
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
        alert('Failed to reset stack state: ' + error);
    });
}

/**
 * Validate a service stack - validates all deployed services
 */
function validateStack(stackId) {
    showStatus('info', {
        message: 'Validating service stack...',
        details: 'Checking all deployed services against device configurations.'
    });

    // Get credentials from settings
    let username, password;
    try {
        const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');
        username = settings.default_username;
        password = settings.default_password;
        console.log('Validate stack - Credentials from settings:', { username, hasPassword: !!password });
    } catch (e) {
        console.error('Error reading credentials from settings:', e);
    }

    $.ajax({
        url: '/api/service-stacks/' + encodeURIComponent(stackId) + '/validate',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            username: username,
            password: password
        }),
        timeout: 300000 // 5 minute timeout
    })
    .done(function(data) {
        if (data.success) {
            const allValid = data.all_valid;
            const results = data.results || [];

            let detailsHtml = '<strong>Validation Results:</strong><ul class="mb-0">';
            results.forEach(function(result) {
                const icon = result.valid ? '<i class="fas fa-check-circle text-success"></i>' : '<i class="fas fa-times-circle text-danger"></i>';
                detailsHtml += `<li>${icon} ${result.service_name}: ${result.message}`;
                if (result.missing_lines && result.missing_lines.length > 0) {
                    detailsHtml += '<br><small class="text-muted">Missing: ' + result.missing_lines.join(', ') + '</small>';
                }
                detailsHtml += '</li>';
            });
            detailsHtml += '</ul>';

            showStatus(allValid ? 'success' : 'warning', {
                message: allValid ? '✓ All services validated successfully!' : '⚠ Some services have configuration drift',
                details: detailsHtml
            });
        } else {
            showStatus('error', {
                message: '✗ Stack validation failed',
                details: data.error || 'Unknown error'
            });
        }
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.error : 'Request failed';
        showStatus('error', {
            message: '✗ Failed to validate stack',
            details: error
        });
    });
}

/**
 * Edit an existing stack
 */
function editStack(stackId) {
    $.get('/api/service-stacks/' + encodeURIComponent(stackId))
        .done(function(data) {
            if (data.success && data.stack) {
                openStackModal(data.stack);
            } else {
                alert('Failed to load stack: ' + (data.error || 'Unknown error'));
            }
        })
        .fail(function(xhr) {
            const error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
            alert('Failed to load stack: ' + error);
        });
}

/**
 * Add a shared variable key-value pair
 */
function addSharedVariable(key, value) {
    $('#no-shared-vars-msg').remove();

    const varHtml = `
        <div class="shared-var-item mb-2 d-flex gap-2">
            <input type="text" class="form-control form-control-sm shared-var-key" placeholder="Variable name" value="${key || ''}" style="flex: 1;">
            <input type="text" class="form-control form-control-sm shared-var-value" placeholder="Variable value" value="${value || ''}" style="flex: 2;">
            <button type="button" class="btn btn-sm btn-danger remove-shared-var-btn">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;

    $('#shared-vars-list').append(varHtml);

    // Attach remove handler
    $('#shared-vars-list').find('.shared-var-item').last().find('.remove-shared-var-btn').click(function() {
        $(this).closest('.shared-var-item').remove();

        if ($('#shared-vars-list .shared-var-item').length === 0) {
            $('#shared-vars-list').html('<p class="text-muted text-center mb-0" id="no-shared-vars-msg"><small>No shared variables. Click "Add Variable" to add one.</small></p>');
        }
    });
}

/**
 * Open modal to create new stack
 */
function openStackModal(stackData) {
    serviceCounter = 0;

    $('#stackModalTitle').text(stackData ? 'Edit Service Stack' : 'Create Service Stack');
    $('#stack-form')[0].reset();
    $('#services-list').html('<p class="text-muted text-center mb-0" id="no-services-msg">No services added yet. Click "Add Service" to begin.</p>');
    $('#shared-vars-list').html('<p class="text-muted text-center mb-0" id="no-shared-vars-msg"><small>No shared variables. Click "Add Variable" to add one.</small></p>');

    if (stackData) {
        $('#stack-id').val(stackData.stack_id);
        $('#stack-name').val(stackData.name);
        $('#stack-description').val(stackData.description || '');

        // Load shared variables
        if (stackData.shared_variables && Object.keys(stackData.shared_variables).length > 0) {
            Object.entries(stackData.shared_variables).forEach(([key, value]) => {
                addSharedVariable(key, value);
            });
        }

        // Load services
        if (stackData.services && stackData.services.length > 0) {
            stackData.services.forEach(function(service) {
                addServiceToStack(service);
            });
        }
    }

    const modal = new bootstrap.Modal(document.getElementById('stackModal'));
    modal.show();
}

/**
 * Add a service to the stack
 */
function addServiceToStack(serviceData) {
    serviceCounter++;
    const serviceId = serviceData ? serviceData.order : serviceCounter;

    $('#no-services-msg').remove();

    const serviceHtml = `
        <div class="service-item border rounded p-3 mb-3" data-service-id="${serviceId}">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <h6>Service #${serviceId}</h6>
                <button type="button" class="btn btn-sm btn-danger remove-service-btn">
                    <i class="fas fa-times"></i>
                </button>
            </div>

            <div class="row">
                <div class="col-md-6 mb-2">
                    <label class="form-label">Service Name *</label>
                    <input type="text" class="form-control service-name" placeholder="e.g., PE Router Config" value="${serviceData ? serviceData.name : ''}" required>
                </div>

                <div class="col-md-6 mb-2">
                    <label class="form-label">Order</label>
                    <input type="number" class="form-control service-order" value="${serviceId}" min="1" required>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-2">
                    <label class="form-label">Template *</label>
                    <select class="form-select service-template" required>
                        <option value="">Select template...</option>
                        ${allTemplates.map(t => {
                            const templateName = typeof t === 'string' ? t : t.name;
                            const templateDisplay = templateName.replace('.j2', '');
                            const isSelected = serviceData && serviceData.template === templateName;
                            return `<option value="${templateName}" ${isSelected ? 'selected' : ''}>${templateDisplay}</option>`;
                        }).join('')}
                    </select>
                </div>

                <div class="col-md-6 mb-2">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <label class="form-label mb-0">Devices *</label>
                        <button type="button" class="btn btn-sm btn-outline-primary add-device-btn">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <div class="devices-list">
                        <!-- Device dropdowns will be added here -->
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-12 mb-2">
                    <label class="form-label">Service Variables</label>
                    <div class="service-variables-container p-2 border rounded bg-light">
                        <div class="text-center text-muted">
                            <small>Select a template to load variables...</small>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-12">
                    <label class="form-label">Dependencies (comma-separated service names)</label>
                    <input type="text" class="form-control service-dependencies" placeholder="e.g., CE Router Config, VLAN Setup" value="${serviceData && serviceData.depends_on ? serviceData.depends_on.join(', ') : ''}">
                    <small class="form-text text-muted">This service will wait for these services to complete first</small>
                </div>
            </div>
        </div>
    `;

    $('#services-list').append(serviceHtml);

    const $serviceItem = $('#services-list').find('.service-item').last();

    // Initialize with at least one device dropdown
    if (serviceData && serviceData.devices) {
        // Load existing devices
        serviceData.devices.forEach(device => {
            addDeviceDropdown($serviceItem, device);
        });
    } else {
        // Add first empty device dropdown
        addDeviceDropdown($serviceItem, null);
    }

    // If we have service data with variables, populate them
    if (serviceData && serviceData.template) {
        loadTemplateVariablesForService($serviceItem, serviceData.template, serviceData.variables);
    }

    // Attach add device button handler
    $serviceItem.find('.add-device-btn').click(function() {
        addDeviceDropdown($serviceItem, null);
    });

    // Attach template change handler
    $serviceItem.find('.service-template').change(function() {
        const template = $(this).val();
        if (template) {
            loadTemplateVariablesForService($serviceItem, template);
        }
    });

    // Attach remove handler
    $serviceItem.find('.remove-service-btn').click(function() {
        $(this).closest('.service-item').remove();

        if ($('#services-list .service-item').length === 0) {
            $('#services-list').html('<p class="text-muted text-center mb-0" id="no-services-msg">No services added yet. Click "Add Service" to begin.</p>');
        }
    });
}

/**
 * Add a device dropdown to a service
 */
function addDeviceDropdown($serviceItem, selectedDevice) {
    const $devicesList = $serviceItem.find('.devices-list');
    const deviceCount = $devicesList.find('.device-dropdown-item').length;

    const deviceHtml = `
        <div class="device-dropdown-item mb-2 d-flex gap-2">
            <select class="form-select form-select-sm service-device-select" required>
                <option value="">Select device...</option>
                ${allDevices.map(d => `<option value="${d.name}" ${selectedDevice === d.name ? 'selected' : ''}>${d.display || d.name}</option>`).join('')}
            </select>
            ${deviceCount > 0 ? '<button type="button" class="btn btn-sm btn-danger remove-device-btn"><i class="fas fa-times"></i></button>' : ''}
        </div>
    `;

    $devicesList.append(deviceHtml);

    // Attach remove handler (only for additional devices, not the first one)
    if (deviceCount > 0) {
        $devicesList.find('.device-dropdown-item').last().find('.remove-device-btn').click(function() {
            $(this).closest('.device-dropdown-item').remove();
        });
    }
}

/**
 * Load template variables for a service
 */
function loadTemplateVariablesForService($serviceItem, templateName, existingVariables) {
    const $container = $serviceItem.find('.service-variables-container');
    $container.html('<div class="text-center"><small class="text-muted">Loading variables...</small></div>');

    $.get('/api/templates/' + encodeURIComponent(templateName) + '/variables')
        .done(function(data) {
            if (data.success && data.variables) {
                renderTemplateVariablesForm($container, data.variables, existingVariables);
            } else {
                $container.html('<div class="alert alert-warning alert-sm mb-0"><small>No variables found in template</small></div>');
            }
        })
        .fail(function() {
            $container.html('<div class="alert alert-danger alert-sm mb-0"><small>Failed to load template variables</small></div>');
        });
}

/**
 * Render template variables as form inputs
 */
function renderTemplateVariablesForm($container, variables, existingValues) {
    existingValues = existingValues || {};

    if (variables.length === 0) {
        $container.html('<div class="text-muted text-center"><small>No variables required for this template</small></div>');
        return;
    }

    let html = '<div class="row g-2">';

    variables.forEach(function(field) {
        // Handle both string array format and object format
        let fieldName, fieldLabel, fieldValue, fieldType, fieldDescription, fieldOptions, isRequired;

        if (typeof field === 'string') {
            // Simple string format from current API
            fieldName = field;
            fieldLabel = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            fieldValue = existingValues[fieldName] || '';
            fieldType = 'text';
            fieldDescription = '';
            fieldOptions = null;
            isRequired = false;
        } else {
            // Object format with metadata
            fieldName = field.name;
            fieldLabel = field.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            fieldValue = existingValues[fieldName] || field.default || '';
            fieldType = field.type || 'text';
            fieldDescription = field.description || '';
            fieldOptions = field.options || null;
            isRequired = field.required || false;
        }

        html += `<div class="col-md-6">`;
        html += `<label class="form-label small mb-1">${fieldLabel} ${isRequired ? '*' : ''}</label>`;

        if (fieldType === 'select' || fieldType === 'device') {
            html += `<select class="form-select form-select-sm var-input" data-var-name="${fieldName}" ${isRequired ? 'required' : ''}>`;
            html += `<option value="">Select ${fieldLabel}...</option>`;

            if (fieldType === 'device') {
                allDevices.forEach(function(device) {
                    const selected = fieldValue === device.name ? 'selected' : '';
                    html += `<option value="${device.name}" ${selected}>${device.display || device.name}</option>`;
                });
            } else if (fieldOptions) {
                fieldOptions.forEach(function(opt) {
                    const selected = fieldValue === opt ? 'selected' : '';
                    html += `<option value="${opt}" ${selected}>${opt}</option>`;
                });
            }

            html += '</select>';
        } else if (fieldType === 'boolean') {
            html += `<select class="form-select form-select-sm var-input" data-var-name="${fieldName}" ${isRequired ? 'required' : ''}>`;
            html += `<option value="true" ${fieldValue === 'true' || fieldValue === true ? 'selected' : ''}>True</option>`;
            html += `<option value="false" ${fieldValue === 'false' || fieldValue === false ? 'selected' : ''}>False</option>`;
            html += '</select>';
        } else if (fieldType === 'integer' || fieldType === 'number') {
            html += `<input type="number" class="form-control form-control-sm var-input" data-var-name="${fieldName}"
                     value="${fieldValue}" placeholder="${fieldDescription}" ${isRequired ? 'required' : ''}>`;
        } else {
            // Default to text input
            html += `<input type="text" class="form-control form-control-sm var-input" data-var-name="${fieldName}"
                     value="${fieldValue}" placeholder="${fieldDescription}" ${isRequired ? 'required' : ''}>`;
        }

        if (fieldDescription) {
            html += `<small class="form-text text-muted d-block">${fieldDescription}</small>`;
        }

        html += '</div>';
    });

    html += '</div>';
    $container.html(html);
}

/**
 * Save service stack
 */
function saveServiceStack() {
    // Validate form
    const name = $('#stack-name').val().trim();
    if (!name) {
        alert('Stack name is required');
        return;
    }

    const services = [];
    let valid = true;

    $('#services-list .service-item').each(function() {
        const serviceName = $(this).find('.service-name').val().trim();
        const template = $(this).find('.service-template').val();
        const order = parseInt($(this).find('.service-order').val());
        const dependenciesText = $(this).find('.service-dependencies').val().trim();

        // Collect all selected devices
        const devices = [];
        $(this).find('.service-device-select').each(function() {
            const deviceValue = $(this).val();
            if (deviceValue) {
                devices.push(deviceValue);
            }
        });

        if (!serviceName || !template || devices.length === 0) {
            alert('All services must have name, template, and at least one device');
            valid = false;
            return false;
        }

        // Collect variables from GUI inputs
        const variables = {};
        $(this).find('.var-input').each(function() {
            const varName = $(this).data('var-name');
            const varValue = $(this).val();
            if (varValue) {
                variables[varName] = varValue;
            }
        });

        const dependencies = dependenciesText ?
            dependenciesText.split(',').map(d => d.trim()).filter(d => d) : [];

        services.push({
            name: serviceName,
            template: template,
            devices: devices,
            order: order,
            variables: variables,
            depends_on: dependencies
        });
    });

    if (!valid || services.length === 0) {
        if (services.length === 0) {
            alert('At least one service is required');
        }
        return;
    }

    // Collect shared variables from key-value inputs
    const sharedVariables = {};
    $('#shared-vars-list .shared-var-item').each(function() {
        const key = $(this).find('.shared-var-key').val().trim();
        const value = $(this).find('.shared-var-value').val().trim();
        if (key && value) {
            sharedVariables[key] = value;
        }
    });

    const stackData = {
        name: name,
        description: $('#stack-description').val().trim(),
        services: services,
        shared_variables: sharedVariables
    };

    const stackId = $('#stack-id').val();
    const url = stackId ? `/api/service-stacks/${stackId}` : '/api/service-stacks';
    const method = stackId ? 'PUT' : 'POST';

    $('#save-stack-btn').prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');

    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(stackData)
    })
    .done(function(data) {
        if (data.success) {
            showStatus('success', {
                message: data.message
            });
            bootstrap.Modal.getInstance(document.getElementById('stackModal')).hide();
            loadServiceStacks();
        } else {
            showStatus('error', {
                message: data.error || 'Failed to save service stack'
            });
        }
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
        showStatus('error', {
            message: 'Failed to save service stack: ' + error
        });
    })
    .always(function() {
        $('#save-stack-btn').prop('disabled', false).html('<i class="fas fa-save"></i> Save Stack');
    });
}

/**
 * View stack details
 */
function viewStackDetails(stackId) {
    const modal = new bootstrap.Modal(document.getElementById('stackDetailsModal'));
    const body = $('#stackDetailsBody');
    body.html('<div class="text-center"><div class="spinner-border"></div></div>');

    modal.show();

    $.get('/api/service-stacks/' + encodeURIComponent(stackId))
        .done(function(data) {
            if (data.success && data.stack) {
                renderStackDetails(data.stack);
            } else {
                body.html('<div class="alert alert-danger">Failed to load stack details</div>');
            }
        })
        .fail(function() {
            body.html('<div class="alert alert-danger">Failed to load stack details</div>');
        });

    // Set up deploy and validate buttons
    $('#deploy-stack-details-btn').off('click').on('click', function() {
        deployStack(stackId);
    });

    $('#validate-stack-details-btn').off('click').on('click', function() {
        validateStack(stackId);
    });
}

/**
 * Render stack details in modal
 */
function renderStackDetails(stack) {
    const stateColors = {
        'pending': 'secondary',
        'deploying': 'warning',
        'deployed': 'success',
        'failed': 'danger'
    };

    const stateColor = stateColors[stack.state] || 'secondary';

    // Calculate unique device count from all services
    const allDevicesInStack = new Set();
    if (stack.services && Array.isArray(stack.services)) {
        stack.services.forEach(service => {
            if (service.devices && Array.isArray(service.devices)) {
                service.devices.forEach(device => allDevicesInStack.add(device));
            } else if (service.device) {
                allDevicesInStack.add(service.device);
            }
        });
    }
    const deviceCount = allDevicesInStack.size;

    let html = `
        <div class="mb-3">
            <h5>${stack.name} <span class="badge bg-${stateColor}">${stack.state}</span></h5>
            ${stack.description ? `<p class="text-muted">${stack.description}</p>` : ''}
        </div>

        <div class="row mb-3">
            <div class="col-md-4">
                <strong>Services:</strong> ${stack.services ? stack.services.length : 0}
            </div>
            <div class="col-md-4">
                <strong>Devices:</strong> ${deviceCount}
            </div>
            <div class="col-md-4">
                <strong>Created:</strong> ${new Date(stack.created_at).toLocaleString()}
            </div>
        </div>

        ${stack.shared_variables && Object.keys(stack.shared_variables).length > 0 ? `
            <div class="mb-3">
                <h6>Shared Variables</h6>
                <pre class="bg-light p-2 rounded"><code>${JSON.stringify(stack.shared_variables, null, 2)}</code></pre>
            </div>
        ` : ''}

        <div class="mb-3">
            <h6>Services in Stack</h6>
            <div class="table-responsive">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Order</th>
                            <th>Name</th>
                            <th>Template</th>
                            <th>Device</th>
                            <th>Dependencies</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${stack.services.sort((a, b) => a.order - b.order).map(s => {
                            const devices = s.devices || (s.device ? [s.device] : []);
                            return `
                            <tr>
                                <td>${s.order}</td>
                                <td>${s.name}</td>
                                <td><code>${s.template}</code></td>
                                <td>${devices.join(', ')}</td>
                                <td>${s.depends_on && s.depends_on.length > 0 ? s.depends_on.join(', ') : '-'}</td>
                            </tr>
                        `}).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        ${stack.deployed_services && stack.deployed_services.length > 0 ? `
            <div class="mb-3">
                <h6>Deployed Services</h6>
                <ul class="list-group">
                    ${stack.deployed_services.map(id => `<li class="list-group-item"><code>${id}</code></li>`).join('')}
                </ul>
            </div>
        ` : ''}

        ${stack.deployment_errors && stack.deployment_errors.length > 0 ? `
            <div class="alert alert-danger">
                <h6>Deployment Errors</h6>
                <ul class="mb-0">
                    ${stack.deployment_errors.map(e => `<li>${e.name || 'Unknown'}: ${e.error}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
    `;

    $('#stackDetailsBody').html(html);
    $('#stackDetailsTitle').text('Stack: ' + stack.name);
}

/**
 * Deploy a service stack
 */
function deployStack(stackId) {
    if (!confirm('Deploy this service stack? All services will be deployed in order with dependency checking.')) {
        return;
    }

    // Get credentials from settings
    let username, password;
    try {
        const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');
        username = settings.default_username;
        password = settings.default_password;
        console.log('Credentials from settings:', { username, hasPassword: !!password });
    } catch (e) {
        console.error('Error reading credentials from settings:', e);
    }

    showStatus('info', {
        message: 'Deploying service stack...',
        details: 'This may take several minutes depending on the number of services.'
    });

    $.ajax({
        url: '/api/service-stacks/' + encodeURIComponent(stackId) + '/deploy',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            username: username,
            password: password
        }),
        timeout: 300000 // 5 minute timeout
    })
    .done(function(data) {
        if (data.success) {
            showStatus('success', {
                message: `✓ Stack deployed successfully - ${data.deployed_count} service(s) deployed`,
                details: data.deployed_services.length > 0 ?
                    '<strong>Deployed services:</strong><br><ul class="mb-0">' +
                    data.deployed_services.map(id => '<li><code>' + id + '</code></li>').join('') +
                    '</ul>' : ''
            });
        } else {
            const failedDetails = data.failed_services && data.failed_services.length > 0 ?
                '<strong>Failed services:</strong><br><ul class="mb-0">' +
                data.failed_services.map(f => '<li>' + f.name + ': ' + f.error + '</li>').join('') +
                '</ul>' : '';

            showStatus('error', {
                message: `⚠ Stack deployment failed - ${data.deployed_count} deployed, ${data.failed_count} failed`,
                details: failedDetails
            });
        }

        loadServiceStacks();
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
        showStatus('error', {
            message: 'Stack deployment failed: ' + error
        });
    });
}

/**
 * Validate a service stack
 */
function validateStack(stackId) {
    showStatus('info', {
        message: 'Validating service stack...',
        details: 'Checking all deployed services against device running configs.'
    });

    $.ajax({
        url: '/api/service-stacks/' + encodeURIComponent(stackId) + '/validate',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({}),
        timeout: 180000 // 3 minute timeout
    })
    .done(function(data) {
        if (data.success) {
            if (data.valid) {
                showStatus('success', {
                    message: '✓ Stack validation passed - All services are valid',
                    details: data.results.length > 0 ?
                        '<strong>Validated services:</strong><br><ul class="mb-0">' +
                        data.results.map(r => '<li>' + r.service_name + ': ✓ Valid</li>').join('') +
                        '</ul>' : ''
                });
            } else {
                const invalidServices = data.results.filter(r => !r.valid);
                showStatus('warning', {
                    message: `⚠ Stack validation failed - ${invalidServices.length} service(s) have drift`,
                    details: '<strong>Services with drift:</strong><br><ul class="mb-0">' +
                        invalidServices.map(r => {
                            const missingLines = r.missing_lines || [];
                            return '<li>' + r.service_name + ': ' + missingLines.length + ' missing line(s)</li>';
                        }).join('') +
                        '</ul>'
                });
            }
        } else {
            showStatus('error', {
                message: 'Stack validation failed: ' + (data.error || 'Unknown error')
            });
        }
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
        showStatus('error', {
            message: 'Stack validation failed: ' + error
        });
    });
}

/**
 * Delete a service stack
 */
function deleteStack(stackId) {
    if (!confirm('Delete this service stack? This will not delete deployed service instances.')) {
        return;
    }

    $.ajax({
        url: '/api/service-stacks/' + encodeURIComponent(stackId),
        method: 'DELETE'
    })
    .done(function(data) {
        if (data.success) {
            showStatus('success', {
                message: data.message
            });
            loadServiceStacks();
        } else {
            showStatus('error', {
                message: data.error || 'Failed to delete service stack'
            });
        }
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
        showStatus('error', {
            message: 'Failed to delete service stack: ' + error
        });
    });
}

/**
 * Show status modal (reused from services.js)
 */
function showStatus(type, data) {
    const modal = new bootstrap.Modal(document.getElementById('statusModal'));

    const titles = {
        'success': 'Success',
        'error': 'Error',
        'warning': 'Warning',
        'info': 'Information'
    };
    $('#statusModalTitle').text(titles[type] || 'Status');

    const alertClasses = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    };

    const icons = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-triangle',
        'warning': 'fa-exclamation-circle',
        'info': 'fa-info-circle'
    };

    let html = `
        <div class="alert ${alertClasses[type] || 'alert-info'}">
            <h5><i class="fas ${icons[type] || 'fa-info-circle'}"></i> ${data.message || 'Status'}</h5>
            ${data.details ? `<hr><div>${data.details}</div>` : ''}
            ${data.task_id ? `<hr><small><strong>Task ID:</strong> <code>${data.task_id}</code></small>` : ''}
        </div>
    `;

    $('#statusModalBody').html(html);
    modal.show();

    // Cleanup backdrop on close
    const modalElement = document.getElementById('statusModal');
    modalElement.addEventListener('hidden.bs.modal', function () {
        const backdrops = document.querySelectorAll('.modal-backdrop');
        backdrops.forEach(backdrop => backdrop.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    });
}
