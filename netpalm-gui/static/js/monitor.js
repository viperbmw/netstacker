// Monitor page JavaScript for Netpalm GUI

let autoRefreshInterval = null;
let showCompleted = true;

$(document).ready(function() {
    loadMonitor();

    // Refresh button
    $('#refresh-btn').click(function() {
        loadMonitor();
    });

    // Auto-refresh toggle
    $('#auto-refresh-btn').click(function() {
        const btn = $(this);
        const isAuto = btn.attr('data-auto') === 'true';

        if (isAuto) {
            // Stop auto-refresh
            clearInterval(autoRefreshInterval);
            btn.attr('data-auto', 'false');
            btn.removeClass('active');
            btn.html('<i class="fas fa-play"></i> Auto-Refresh (5s)');
        } else {
            // Start auto-refresh
            autoRefreshInterval = setInterval(loadMonitor, 5000);
            btn.attr('data-auto', 'true');
            btn.addClass('active');
            btn.html('<i class="fas fa-pause"></i> Stop Auto-Refresh');
        }
    });

    // Show completed toggle
    $('#show-completed').change(function() {
        showCompleted = $(this).is(':checked');
        loadTasks();
    });
});

function loadMonitor() {
    loadTasks();
    loadWorkers();
}

function loadTasks() {
    $('#tasks-loading').show();
    $('#tasks-container').hide();

    $.get('/api/tasks')
        .done(function(data) {
            const tbody = $('#tasks-body');
            tbody.empty();

            let tasks = [];
            if (data.task_meta_list && Array.isArray(data.task_meta_list)) {
                tasks = data.task_meta_list;
            } else if (Array.isArray(data)) {
                tasks = data;
            }

            // Filter tasks based on showCompleted
            if (!showCompleted) {
                tasks = tasks.filter(function(task) {
                    const status = task.status || task.task_status;
                    return status !== 'finished' && status !== 'completed';
                });
            }

            if (tasks.length === 0) {
                $('#no-tasks').show();
                $('#tasks-table').hide();
            } else {
                $('#no-tasks').hide();
                $('#tasks-table').show();

                tasks.forEach(function(task) {
                    const taskId = task.task_id || task.id || 'Unknown';
                    const status = task.status || task.task_status || 'unknown';
                    const created = task.created_on || task.enqueued_at || 'N/A';
                    const operation = task.task_queue || task.operation || 'N/A';

                    let statusBadge = 'secondary';
                    if (status === 'queued') statusBadge = 'badge-queued';
                    else if (status === 'started' || status === 'running') statusBadge = 'badge-running';
                    else if (status === 'finished' || status === 'completed') statusBadge = 'badge-completed';
                    else if (status === 'failed') statusBadge = 'badge-failed';

                    const shortId = taskId.length > 16 ? taskId.substring(0, 16) + '...' : taskId;
                    const createdDate = created !== 'N/A' ? new Date(created).toLocaleString() : 'N/A';

                    tbody.append(`
                        <tr data-task-id="${taskId}">
                            <td><small class="font-monospace">${shortId}</small></td>
                            <td><small>${operation}</small></td>
                            <td><span class="badge ${statusBadge}">${status}</span></td>
                            <td><small>${createdDate}</small></td>
                            <td>
                                <button class="btn btn-sm btn-primary view-task-btn" data-task-id="${taskId}">
                                    <i class="fas fa-eye"></i> View
                                </button>
                            </td>
                        </tr>
                    `);
                });

                // Add click handlers for view buttons
                $('.view-task-btn').click(function(e) {
                    e.stopPropagation();
                    const taskId = $(this).data('task-id');
                    viewTaskDetails(taskId);
                });
            }

            $('#tasks-loading').hide();
            $('#tasks-container').show();
        })
        .fail(function(xhr, status, error) {
            $('#tasks-loading').hide();
            $('#tasks-container').show();
            $('#no-tasks').html('<i class="fas fa-exclamation-triangle"></i> Error loading tasks: ' + error).show();
            $('#tasks-table').hide();
        });
}

function loadWorkers() {
    $('#workers-loading').show();
    $('#workers-container').hide();

    $.get('/api/workers')
        .done(function(data) {
            const tbody = $('#workers-body');
            tbody.empty();

            if (data.length === 0) {
                tbody.append('<tr><td colspan="4" class="text-center text-muted">No active workers</td></tr>');
            } else {
                data.forEach(function(worker) {
                    const workerName = worker.name || 'Unknown';
                    const workerType = workerName.includes('pinned') ? 'Pinned' : 'FIFO';
                    const state = worker.state || 'idle';
                    const currentJob = worker.current_job || 'None';

                    let stateClass = 'worker-idle';
                    let stateIcon = '<i class="fas fa-pause-circle"></i>';
                    if (state === 'busy' || state === 'started') {
                        stateClass = 'worker-busy';
                        stateIcon = '<i class="fas fa-spinner fa-spin"></i>';
                    } else if (state === 'failed') {
                        stateClass = 'worker-failed';
                        stateIcon = '<i class="fas fa-exclamation-circle"></i>';
                    }

                    tbody.append(`
                        <tr>
                            <td>${workerName}</td>
                            <td><span class="badge bg-secondary">${workerType}</span></td>
                            <td><span class="${stateClass}">${stateIcon} ${state}</span></td>
                            <td><small class="font-monospace">${currentJob}</small></td>
                        </tr>
                    `);
                });
            }

            $('#workers-loading').hide();
            $('#workers-container').show();
        })
        .fail(function() {
            $('#workers-loading').hide();
            $('#workers-container').show();
        });
}

function viewTaskDetails(taskId) {
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('taskDetailModal'));
    modal.show();

    // Reset modal content
    $('#task-detail-loading').show();
    $('#task-detail-content').hide();

    // Fetch task details
    $.get('/api/task/' + taskId)
        .done(function(data) {
            const status = data.status || data.task_status || 'unknown';
            const result = data.task_result || data.data || 'No result available';

            let statusClass = 'bg-secondary';
            if (status === 'queued') statusClass = 'bg-warning text-dark';
            else if (status === 'started' || status === 'running') statusClass = 'bg-info';
            else if (status === 'finished' || status === 'completed') statusClass = 'bg-success';
            else if (status === 'failed') statusClass = 'bg-danger';

            $('#detail-status').removeClass().addClass('badge ' + statusClass).text(status);
            $('#detail-task-id').text(taskId);

            // Format result
            let formattedResult = result;
            if (typeof result === 'object') {
                formattedResult = JSON.stringify(result, null, 2);
            }
            $('#detail-result').text(formattedResult);

            $('#task-detail-loading').hide();
            $('#task-detail-content').show();
        })
        .fail(function(xhr, status, error) {
            $('#task-detail-loading').hide();
            $('#task-detail-content').show();
            $('#detail-status').removeClass().addClass('badge bg-danger').text('Error');
            $('#detail-task-id').text(taskId);
            $('#detail-result').text('Error loading task details: ' + error);
        });
}
