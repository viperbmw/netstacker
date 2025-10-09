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
    const device = $('#get-device').val();
    const library = $('#get-library').val();
    const command = $('#get-command').val();
    const username = $('#get-username').val();
    const password = $('#get-password').val();
    const enableCache = $('#get-cache').is(':checked');

    if (!device) {
        showStatus('error', { message: 'Please select a device' });
        return;
    }

    showStatus('loading');

    const payload = {
        connection_args: {
            device_type: "cisco_ios",  // Default, can be made configurable
            host: device,
            username: username,
            password: password
        },
        command: command
    };

    if (enableCache) {
        payload.cache = {
            enabled: true,
            ttl: 300
        };
    }

    $.ajax({
        url: '/api/deploy/getconfig',
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
        let errorMsg = 'Failed to execute command';
        if (xhr.responseJSON && xhr.responseJSON.error) {
            errorMsg = xhr.responseJSON.error;
        } else if (error) {
            errorMsg = error;
        }
        showStatus('error', { message: errorMsg });
    });
}

function executeSetConfig() {
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
