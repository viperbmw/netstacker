// Dashboard JavaScript for Netpalm GUI

$(document).ready(function() {
    loadDashboard();

    // Refresh every 10 seconds
    setInterval(loadDashboard, 10000);
});

function loadDashboard() {
    loadWorkers();
    loadTasks();
    loadDeviceCount();
}

function loadWorkers() {
    $.get('/api/workers')
        .done(function(data) {
            const workerCount = data.length || 0;
            $('#worker-count').text(workerCount);

            // Update workers table
            const tbody = $('#workers-body');
            tbody.empty();

            if (data.length === 0) {
                tbody.append('<tr><td colspan="3" class="text-center text-muted">No active workers</td></tr>');
            } else {
                data.slice(0, 5).forEach(function(worker) {
                    const workerType = worker.name.includes('pinned') ? 'Pinned' : 'FIFO';
                    const state = worker.state || 'idle';
                    const stateClass = state === 'busy' ? 'worker-busy' : 'worker-idle';

                    tbody.append(`
                        <tr>
                            <td>${worker.name || 'Unknown'}</td>
                            <td>${workerType}</td>
                            <td><span class="${stateClass}">${state}</span></td>
                        </tr>
                    `);
                });
            }

            $('#workers-loading').hide();
            $('#workers-container').show();
        })
        .fail(function() {
            $('#worker-count').text('?');
        });
}

function loadTasks() {
    $.get('/api/tasks')
        .done(function(data) {
            let queuedCount = 0;
            let runningCount = 0;
            let tasks = [];

            // Process tasks data
            if (data.task_meta_list && Array.isArray(data.task_meta_list)) {
                tasks = data.task_meta_list;
            } else if (Array.isArray(data)) {
                tasks = data;
            }

            tasks.forEach(function(task) {
                const status = task.status || task.task_status;
                if (status === 'queued' || status === 'started') {
                    if (status === 'queued') queuedCount++;
                    if (status === 'started') runningCount++;
                }
            });

            $('#queued-count').text(queuedCount);
            $('#running-count').text(runningCount);

            // Update recent tasks table
            const tbody = $('#recent-tasks-body');
            tbody.empty();

            if (tasks.length === 0) {
                tbody.append('<tr><td colspan="3" class="text-center text-muted">No recent tasks</td></tr>');
            } else {
                tasks.slice(0, 5).forEach(function(task) {
                    const taskId = task.task_id || task.id || 'Unknown';
                    const status = task.status || task.task_status || 'unknown';
                    const created = task.created_on || task.enqueued_at || 'N/A';

                    let statusBadge = 'secondary';
                    if (status === 'queued') statusBadge = 'badge-queued';
                    else if (status === 'started' || status === 'running') statusBadge = 'badge-running';
                    else if (status === 'finished' || status === 'completed') statusBadge = 'badge-completed';
                    else if (status === 'failed') statusBadge = 'badge-failed';

                    const shortId = taskId.length > 10 ? taskId.substring(0, 10) + '...' : taskId;
                    const createdDate = created !== 'N/A' ? new Date(created).toLocaleString() : 'N/A';

                    tbody.append(`
                        <tr style="cursor: pointer;" onclick="window.location.href='/monitor'">
                            <td><small class="font-monospace">${shortId}</small></td>
                            <td><span class="badge ${statusBadge}">${status}</span></td>
                            <td><small>${createdDate}</small></td>
                        </tr>
                    `);
                });
            }

            $('#recent-tasks-loading').hide();
            $('#recent-tasks-container').show();
        })
        .fail(function() {
            $('#queued-count').text('?');
            $('#running-count').text('?');
        });
}

function loadDeviceCount() {
    $.get('/api/device-names')
        .done(function(data) {
            const deviceCount = data.names ? data.names.length : 0;
            $('#device-count').text(deviceCount);
        })
        .fail(function() {
            $('#device-count').text('?');
        });
}
