// Deploy page JavaScript for Netpalm GUI

$(document).ready(function() {
    loadDevices();

    // Get Config form submit
    $('#getconfig-form').submit(function(e) {
        e.preventDefault();
        executeGetConfig();
    });

    // Set Config form submit
    $('#setconfig-form').submit(function(e) {
        e.preventDefault();
        executeSetConfig();
    });

    // Copy result button
    $('#copy-result').click(function() {
        const resultText = $('#result-content').text();
        navigator.clipboard.writeText(resultText).then(function() {
            const btn = $('#copy-result');
            const originalText = btn.html();
            btn.html('<i class="fas fa-check"></i> Copied!');
            setTimeout(function() {
                btn.html(originalText);
            }, 2000);
        });
    });

    // View task link
    $('#view-task-link').click(function(e) {
        e.preventDefault();
        window.location.href = '/monitor';
    });

    // Toggle TTP template input visibility
    $('#get-use-ttp').change(function() {
        if ($(this).is(':checked')) {
            $('#get-ttp-template-container').show();
        } else {
            $('#get-ttp-template-container').hide();
        }
    });

    // Mutual exclusivity between TextFSM and TTP
    $('#get-use-textfsm').change(function() {
        if ($(this).is(':checked')) {
            $('#get-use-ttp').prop('checked', false);
            $('#get-ttp-template-container').hide();
        }
    });

    $('#get-use-ttp').change(function() {
        if ($(this).is(':checked')) {
            $('#get-use-textfsm').prop('checked', false);
        }
    });

    // Configuration source radio buttons
    $('input[name="set-config-source"]').change(function() {
        if ($(this).val() === 'manual') {
            $('#set-manual-container').show();
            $('#set-template-container').hide();
        } else if ($(this).val() === 'template') {
            $('#set-manual-container').hide();
            $('#set-template-container').show();
            loadTemplates(); // Load templates when switching to template mode
        }
    });

    // Setup template variable form/JSON toggle
    setupTemplateVariableToggle('#set-template-select', '#set-template-vars-container', '#set-template-vars-toggle');

    // Pre-fill credentials if defaults exist
    prefillCredentials('#get-username', '#get-password');
    prefillCredentials('#set-username', '#set-password');
});

function loadDevices() {
    $.get('/api/devices')
        .done(function(data) {
            if (data.success && data.devices) {
                populateDeviceDropdowns(data.devices);
            } else {
                $('#get-device, #set-device').html('<option value="">Error loading devices</option>');
            }
        })
        .fail(function() {
            $('#get-device, #set-device').html('<option value="">Error loading devices</option>');
        });
}

function populateDeviceDropdowns(devices) {
    const getSelect = $('#get-device');
    const setSelect = $('#set-device');

    getSelect.empty();
    setSelect.empty();

    if (devices.length === 0) {
        getSelect.append('<option value="">No devices found</option>');
        setSelect.append('<option value="">No devices found</option>');
        return;
    }

    getSelect.append('<option value="">Select a device...</option>');
    setSelect.append('<option value="">Select a device...</option>');

    devices.forEach(function(device) {
        const displayName = device.display || device.name;
        const deviceValue = device.name;

        const option = `<option value="${deviceValue}" data-name="${device.name}">${displayName}</option>`;
        getSelect.append(option);
        setSelect.append(option);
    });
}

function loadTemplates() {
    const select = $('#set-template-select');
    select.html('<option value="">Loading templates...</option>');

    $.get('/api/templates')
        .done(function(data) {
            select.empty();
            select.append('<option value="">Select a template...</option>');

            if (data.success && data.templates && data.templates.length > 0) {
                data.templates.forEach(function(template) {
                    select.append(`<option value="${template}">${template}</option>`);
                });
            } else {
                select.append('<option value="">No templates found</option>');
            }
        })
        .fail(function() {
            select.html('<option value="">Error loading templates</option>');
        });
}

function resetStatus() {
    $('#status-idle, #status-loading, #status-success, #status-error').hide();
}

function showStatus(status, data = {}) {
    resetStatus();

    switch(status) {
        case 'idle':
            $('#status-idle').show();
            break;
        case 'loading':
            $('#status-loading').show();
            break;
        case 'success':
            $('#success-task-id').text(data.taskId || 'Unknown');
            $('#status-success').show();
            break;
        case 'error':
            $('#error-message').text(data.message || 'Unknown error');
            $('#status-error').show();
            break;
    }
}

function executeGetConfig() {
    const devices = $('#get-device').val(); // Now returns array
    const library = $('#get-library').val();
    const command = $('#get-command').val();
    const username = $('#get-username').val();
    const password = $('#get-password').val();
    const enableCache = $('#get-cache').is(':checked');
    const useTextFsm = $('#get-use-textfsm').is(':checked');
    const useTtp = $('#get-use-ttp').is(':checked');
    const ttpTemplate = $('#get-ttp-template').val();

    if (!devices || devices.length === 0) {
        showStatus('error', { message: 'Please select at least one device' });
        return;
    }

    // Use default credentials if not provided
    const creds = loadDefaultCredentials();
    const finalUsername = username || creds.username;
    const finalPassword = password || creds.password;

    if (!finalUsername || !finalPassword) {
        showStatus('error', { message: 'Please provide credentials or set defaults in Settings' });
        return;
    }

    showStatus('loading');

    const taskIds = [];
    let completed = 0;

    // Send command to each device
    devices.forEach(function(device) {
        // Fetch device connection info first
        $.get('/api/device/' + encodeURIComponent(device) + '/connection-info')
            .done(function(deviceInfo) {
                const payload = {
                    connection_args: {
                        device_type: deviceInfo.device_type || "cisco_ios",
                        host: deviceInfo.ip_address || device,
                        username: finalUsername,
                        password: finalPassword,
                        timeout: 10
                    },
                    command: command,
                    queue_strategy: "pinned"
                };

                if (enableCache) {
                    payload.cache = {
                        enabled: true,
                        ttl: 300
                    };
                }

                // Add args for parsing options
                if (useTextFsm || useTtp) {
                    payload.args = {};
                    if (useTextFsm) {
                        payload.args.use_textfsm = true;
                    }
                    if (useTtp) {
                        payload.args.use_ttp = true;
                        if (ttpTemplate && ttpTemplate.trim() !== '') {
                            payload.args.ttp_template = ttpTemplate;
                        }
                    }
                }

                $.ajax({
                    url: '/api/deploy/getconfig',
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        library: library,
                        payload: payload,
                        device_name: device  // Include device name for tracking
                    }),
                    timeout: 30000
                })
                .done(function(data) {
                    // Netpalm returns: {status: 'success', data: {task_id: '...', ...}}
                    const taskId = data.data?.task_id || data.task_id || data.id;
                    if (taskId) {
                        taskIds.push(taskId);
                    }
                    completed++;

                    if (completed === devices.length) {
                        const taskIdList = taskIds.join(', ');
                        showStatus('success', { taskId: `${taskIds.length} tasks created` });
                    }
                })
                .fail(function(xhr, status, error) {
                    completed++;
                    let errorMsg = 'Failed to execute command on ' + device;
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        errorMsg += ': ' + xhr.responseJSON.error;
                    }
                    console.error(errorMsg);

                    if (completed === devices.length) {
                        showStatus('error', { message: `Completed with errors. ${taskIds.length} of ${devices.length} successful` });
                    }
                });
            })
            .fail(function() {
                completed++;
                console.error('Failed to fetch device info for ' + device);
                if (completed === devices.length) {
                    showStatus('error', { message: `Failed to fetch device info` });
                }
            });
    });
}

function executeSetConfig() {
    const devices = $('#set-device').val(); // Now returns array
    const library = $('#set-library').val();
    const username = $('#set-username').val();
    const password = $('#set-password').val();
    const dryRun = $('#set-dry-run').is(':checked');
    const configSource = $('input[name="set-config-source"]:checked').val();

    if (!devices || devices.length === 0) {
        showStatus('error', { message: 'Please select at least one device' });
        return;
    }

    if (configSource === 'manual') {
        // Manual configuration mode
        const config = $('#set-config').val();
        if (!config.trim()) {
            showStatus('error', { message: 'Please enter configuration commands' });
            return;
        }

        const commands = config.split('\n').filter(cmd => cmd.trim() !== '');
        deployToDevices(devices, library, commands, username, password, dryRun);
    } else {
        // Template mode
        const templateName = $('#set-template-select').val();
        if (!templateName) {
            showStatus('error', { message: 'Please select a template' });
            return;
        }

        let templateVars = {};

        // Collect variables from form or JSON
        try {
            templateVars = collectTemplateVariables('#set-template-vars-container');
        } catch (e) {
            showStatus('error', { message: e.message });
            return;
        }

        showStatus('loading');

        // Render template first
        $.ajax({
            url: '/api/templates/render',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                template_name: templateName,
                variables: templateVars
            }),
            timeout: 10000
        })
        .done(function(data) {
            if (data.success && data.rendered_config) {
                // Split rendered config into commands
                const commands = data.rendered_config.split('\n').filter(cmd => cmd.trim() !== '');
                deployToDevices(devices, library, commands, username, password, dryRun);
            } else {
                showStatus('error', { message: 'Failed to render template' });
            }
        })
        .fail(function(xhr, status, error) {
            let errorMsg = 'Failed to render template';
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg += ': ' + xhr.responseJSON.error;
            }
            showStatus('error', { message: errorMsg });
        });
    }
}

function deployToDevices(devices, library, commands, username, password, dryRun) {
    showStatus('loading');

    // Use default credentials if not provided
    const creds = loadDefaultCredentials();
    const finalUsername = username || creds.username;
    const finalPassword = password || creds.password;

    if (!finalUsername || !finalPassword) {
        showStatus('error', { message: 'Please provide credentials or set defaults in Settings' });
        return;
    }

    const taskIds = [];
    let completed = 0;
    const endpoint = dryRun ? '/api/deploy/setconfig/dry-run' : '/api/deploy/setconfig';

    // Send config to each device
    devices.forEach(function(device) {
        // Fetch device connection info first
        $.get('/api/device/' + encodeURIComponent(device) + '/connection-info')
            .done(function(deviceInfo) {
                const payload = {
                    connection_args: {
                        device_type: deviceInfo.device_type || "cisco_ios",
                        host: deviceInfo.ip_address || device,
                        username: finalUsername,
                        password: finalPassword,
                        timeout: 10
                    },
                    config: commands,
                    queue_strategy: "pinned"
                };

                $.ajax({
                    url: endpoint,
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        library: library,
                        payload: payload,
                        device_name: device  // Include device name for tracking
                    }),
                    timeout: 30000
                })
                .done(function(data) {
                    // Netpalm returns: {status: 'success', data: {task_id: '...', ...}}
                    const taskId = data.data?.task_id || data.task_id || data.id;
                    if (taskId) {
                        taskIds.push(taskId);
                    }
                    completed++;

                    if (completed === devices.length) {
                        showStatus('success', { taskId: `${taskIds.length} tasks created` });
                    }
                })
                .fail(function(xhr, status, error) {
                    completed++;
                    let errorMsg = 'Failed to deploy to ' + device;
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        errorMsg += ': ' + xhr.responseJSON.error;
                    }
                    console.error(errorMsg);

                    if (completed === devices.length) {
                        showStatus('error', { message: `Completed with errors. ${taskIds.length} of ${devices.length} successful` });
                    }
                });
            })
            .fail(function() {
                completed++;
                console.error('Failed to fetch device info for ' + device);
                if (completed === devices.length) {
                    showStatus('error', { message: `Failed to fetch device info` });
                }
            });
    });
}

function oldExecuteSetConfigSingle() {
    const device = $('#set-device').val();
    const library = $('#set-library').val();
    const config = $('#set-config').val();
    const username = $('#set-username').val();
    const password = $('#set-password').val();
    const dryRun = $('#set-dry-run').is(':checked');

    if (!device) {
        showStatus('error', { message: 'Please select a device' });
        return;
    }

    if (!config.trim()) {
        showStatus('error', { message: 'Please enter configuration commands' });
        return;
    }

    showStatus('loading');

    // Split config into array of commands
    const commands = config.split('\n').filter(cmd => cmd.trim() !== '');

    const payload = {
        connection_args: {
            device_type: "cisco_ios",  // Default, can be made configurable
            host: device,
            username: username,
            password: password
        },
        config: commands
    };

    const endpoint = dryRun ? '/api/deploy/setconfig/dry-run' : '/api/deploy/setconfig';

    $.ajax({
        url: endpoint,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            library: library,
            payload: payload
        }),
        timeout: 30000
    })
    .done(function(data) {
        // Netpalm returns: {status: 'success', data: {task_id: '...', ...}}
        const taskId = data.data?.task_id || data.task_id || data.id;
        showStatus('success', { taskId: taskId });

        // Poll for result
        if (taskId) {
            pollTaskResult(taskId);
        }
    })
    .fail(function(xhr, status, error) {
        let errorMsg = 'Failed to deploy configuration';
        if (xhr.responseJSON && xhr.responseJSON.error) {
            errorMsg = xhr.responseJSON.error;
        } else if (error) {
            errorMsg = error;
        }
        showStatus('error', { message: errorMsg });
    });
}

function pollTaskResult(taskId, attempts = 0) {
    if (attempts > 20) {  // Stop after 20 attempts (40 seconds)
        return;
    }

    setTimeout(function() {
        $.get('/api/task/' + taskId)
            .done(function(data) {
                // Netpalm returns: {status: 'success', data: {task_status: '...', task_result: ...}}
                const taskData = data.data || data;
                const status = taskData.task_status || taskData.status;

                if (status === 'finished' || status === 'completed') {
                    // Show result in modal
                    showResultModal(taskData);
                } else if (status === 'failed') {
                    showStatus('error', {
                        message: 'Task failed: ' + (taskData.task_errors || 'Unknown error')
                    });
                } else if (status === 'queued' || status === 'started') {
                    // Continue polling
                    pollTaskResult(taskId, attempts + 1);
                }
            })
            .fail(function() {
                // Continue polling on error (task might not be created yet)
                if (attempts < 5) {
                    pollTaskResult(taskId, attempts + 1);
                }
            });
    }, 2000);  // Poll every 2 seconds
}

function showResultModal(taskData) {
    const result = taskData.task_result || taskData.data || 'No result available';

    let formattedResult = result;
    if (typeof result === 'object') {
        formattedResult = JSON.stringify(result, null, 2);
    }

    $('#result-content').text(formattedResult);

    const modal = new bootstrap.Modal(document.getElementById('resultModal'));
    modal.show();
}
