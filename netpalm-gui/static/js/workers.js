// Workers page JavaScript

$(document).ready(function() {
    loadWorkers();

    // Refresh button
    $('#refresh-workers').click(function() {
        loadWorkers();
    });

    // Auto-refresh every 10 seconds
    setInterval(loadWorkers, 10000);
});

function loadWorkers() {
    $('#workers-loading').show();
    $('#workers-container').hide();

    $.get('/api/workers')
        .done(function(data) {
            const tbody = $('#workers-body');
            tbody.empty();

            if (!data || data.length === 0) {
                tbody.append('<tr><td colspan="4" class="text-center text-muted">No active workers</td></tr>');
                $('#worker-count-display').text('0');
            } else {
                $('#worker-count-display').text(data.length);

                data.forEach(function(worker) {
                    const workerType = worker.name.includes('pinned') ? 'Pinned' : 'FIFO';
                    const state = worker.state || 'idle';
                    const currentJob = worker.current_job || 'None';

                    let stateBadge = 'bg-secondary';
                    if (state === 'idle') stateBadge = 'bg-success';
                    else if (state === 'busy') stateBadge = 'bg-warning text-dark';
                    else if (state === 'failed') stateBadge = 'bg-danger';

                    const row = `
                        <tr>
                            <td><strong>${worker.name || 'Unknown'}</strong></td>
                            <td><span class="badge bg-info">${workerType}</span></td>
                            <td><span class="badge ${stateBadge}">${state.toUpperCase()}</span></td>
                            <td><small class="font-monospace text-muted">${currentJob}</small></td>
                        </tr>
                    `;
                    tbody.append(row);
                });
            }

            $('#workers-loading').hide();
            $('#workers-container').show();
        })
        .fail(function() {
            $('#workers-body').html('<tr><td colspan="4" class="text-center text-danger">Failed to load workers</td></tr>');
            $('#workers-loading').hide();
            $('#workers-container').show();
        });
}
