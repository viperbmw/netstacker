// Templates page JavaScript

let currentTemplate = null;
let currentTemplateMetadata = null;
let isNewTemplate = false;
let editor = null;
let allTemplatesWithMetadata = [];

$(document).ready(function() {
    // Initialize CodeMirror
    initializeEditor();

    loadTemplateList();

    // Create new template
    $('#create-template-btn').click(function() {
        createNewTemplate();
    });

    // Save template
    $('#save-template-btn').click(function() {
        saveTemplate();
    });

    // Delete template
    $('#delete-template-btn').click(function() {
        deleteTemplate();
    });
});

function initializeEditor() {
    const textarea = document.getElementById('template-content');

    editor = CodeMirror.fromTextArea(textarea, {
        mode: 'jinja2',
        theme: 'monokai',
        lineNumbers: true,
        lineWrapping: true,
        indentUnit: 2,
        tabSize: 2,
        indentWithTabs: false,
        matchBrackets: true,
        autoCloseBrackets: true,
        extraKeys: {
            "Tab": function(cm) {
                cm.replaceSelection("  ", "end");
            }
        }
    });

    // Refresh editor when it becomes visible
    editor.on('focus', function() {
        editor.refresh();
    });
}

function loadTemplateList() {
    $('#templates-loading').show();
    $('#templates-list').hide();

    $.get('/api/templates')
        .done(function(data) {
            const templateList = $('#template-items');
            templateList.empty();

            if (data.success && data.templates && data.templates.length > 0) {
                // Store templates globally for metadata dropdowns
                allTemplatesWithMetadata = data.templates;

                // Populate template list
                data.templates.forEach(function(template) {
                    // Handle both string and object formats
                    const templateName = typeof template === 'string' ? template : template.name;
                    const hasValidation = template.validation_template ? '<i class="fas fa-check-circle text-success ms-2" title="Has validation template"></i>' : '';
                    const hasDelete = template.delete_template ? '<i class="fas fa-trash-alt text-danger ms-1" title="Has delete template"></i>' : '';

                    const item = `
                        <li class="list-group-item list-group-item-action template-item" data-name="${templateName}">
                            <i class="fas fa-file-code"></i> ${templateName}
                            ${hasValidation}
                            ${hasDelete}
                        </li>
                    `;
                    templateList.append(item);
                });

                // Populate metadata dropdowns
                populateMetadataDropdowns();

                // Click handler for template items
                $('.template-item').click(function() {
                    const templateName = $(this).data('name');
                    loadTemplate(templateName);
                    $('.template-item').removeClass('active');
                    $(this).addClass('active');
                });
            } else {
                templateList.append('<li class="list-group-item text-muted">No templates found</li>');
            }

            $('#templates-loading').hide();
            $('#templates-list').show();
        })
        .fail(function() {
            $('#template-items').html('<li class="list-group-item text-danger">Failed to load templates</li>');
            $('#templates-loading').hide();
            $('#templates-list').show();
        });
}

function populateMetadataDropdowns() {
    const validationSelect = $('#validation-template');
    const deleteSelect = $('#delete-template-select');

    validationSelect.html('<option value="">None - use deployed config</option>');
    deleteSelect.html('<option value="">None - manual cleanup</option>');

    allTemplatesWithMetadata.forEach(function(template) {
        const templateName = typeof template === 'string' ? template : template.name;
        validationSelect.append(`<option value="${templateName}">${templateName}</option>`);
        deleteSelect.append(`<option value="${templateName}">${templateName}</option>`);
    });
}

function loadTemplate(templateName) {
    $.get('/api/templates/' + encodeURIComponent(templateName))
        .done(function(data) {
            if (data.success && data.content) {
                currentTemplate = templateName;
                isNewTemplate = false;
                $('#template-name').val(templateName).prop('disabled', true);
                editor.setValue(data.content);
                editor.refresh();
                showEditor();
                $('#delete-template-btn').show();

                // Load metadata
                const templateObj = allTemplatesWithMetadata.find(t => {
                    const name = typeof t === 'string' ? t : t.name;
                    return name === templateName;
                });

                if (templateObj && typeof templateObj === 'object') {
                    currentTemplateMetadata = templateObj;
                    $('#template-description').val(templateObj.description || '');
                    $('#validation-template').val(templateObj.validation_template || '');
                    $('#delete-template-select').val(templateObj.delete_template || '');
                } else {
                    currentTemplateMetadata = null;
                    $('#template-description').val('');
                    $('#validation-template').val('');
                    $('#delete-template-select').val('');
                }
            } else {
                alert('Failed to load template content');
            }
        })
        .fail(function() {
            alert('Error loading template');
        });
}

function createNewTemplate() {
    currentTemplate = null;
    isNewTemplate = true;
    $('#template-name').val('').prop('disabled', false);
    editor.setValue('');
    editor.refresh();
    $('.template-item').removeClass('active');
    showEditor();
    $('#delete-template-btn').hide();
}

function showEditor() {
    $('#editor-empty').hide();
    $('#editor-container').show();
    $('#save-template-btn').show();
    // Refresh editor when shown
    setTimeout(function() {
        editor.refresh();
    }, 10);
}

function hideEditor() {
    $('#editor-empty').show();
    $('#editor-container').hide();
    $('#save-template-btn').hide();
    $('#delete-template-btn').hide();
}

function saveTemplate() {
    let templateName = $('#template-name').val().trim();
    const templateContent = editor.getValue();

    if (!templateName) {
        alert('Please enter a template name');
        return;
    }

    if (!templateContent) {
        alert('Please enter template content');
        return;
    }

    // Ensure template name ends with .j2
    if (!templateName.endsWith('.j2')) {
        templateName = templateName + '.j2';
    }

    // Encode content to base64
    const base64Content = btoa(unescape(encodeURIComponent(templateContent)));

    const payload = {
        name: templateName,
        base64_payload: base64Content
    };

    $('#save-template-btn').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Saving...');

    $.ajax({
        url: '/api/templates',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload)
    })
    .done(function(data) {
        if (data.success) {
            // Save metadata
            const templateNameNoExt = templateName.replace('.j2', '');
            const metadata = {
                description: $('#template-description').val().trim() || null,
                validation_template: $('#validation-template').val() || null,
                delete_template: $('#delete-template-select').val() || null
            };

            // Only save metadata if any field is set
            if (metadata.description || metadata.validation_template || metadata.delete_template) {
                $.ajax({
                    url: '/api/templates/' + encodeURIComponent(templateNameNoExt) + '/metadata',
                    method: 'PUT',
                    contentType: 'application/json',
                    data: JSON.stringify(metadata)
                })
                .always(function() {
                    alert('Template and metadata saved successfully!');
                    currentTemplate = templateName;
                    isNewTemplate = false;
                    $('#template-name').prop('disabled', true);
                    $('#delete-template-btn').show();
                    loadTemplateList();
                });
            } else {
                alert('Template saved successfully!');
                currentTemplate = templateName;
                isNewTemplate = false;
                $('#template-name').prop('disabled', true);
                $('#delete-template-btn').show();
                loadTemplateList();
            }
        } else {
            alert('Failed to save template: ' + (data.error || 'Unknown error'));
        }
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON?.error || 'Failed to save template';
        alert('Error: ' + error);
    })
    .always(function() {
        $('#save-template-btn').prop('disabled', false).html('<i class="fas fa-save"></i> Save');
    });
}

function deleteTemplate() {
    if (!currentTemplate) {
        return;
    }

    if (!confirm(`Are you sure you want to delete template "${currentTemplate}"?`)) {
        return;
    }

    $('#delete-template-btn').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Deleting...');

    $.ajax({
        url: '/api/templates',
        method: 'DELETE',
        contentType: 'application/json',
        data: JSON.stringify({ name: currentTemplate })
    })
    .done(function(data) {
        if (data.success) {
            alert('Template deleted successfully!');
            hideEditor();
            currentTemplate = null;
            loadTemplateList();
        } else {
            alert('Failed to delete template: ' + (data.error || 'Unknown error'));
        }
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON?.error || 'Failed to delete template';
        alert('Error: ' + error);
    })
    .always(function() {
        $('#delete-template-btn').prop('disabled', false).html('<i class="fas fa-trash"></i> Delete');
    });
}
