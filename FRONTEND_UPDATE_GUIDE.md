# Frontend Update Guide for Template Services

## Current State
- Backend is complete and working ✅
- Redis connection fixed ✅
- API endpoints ready ✅
- Frontend still uses old Python service system ❌

## What Needs to Change in Frontend

### 1. Service Templates List
**Currently:** Shows Python service classes (vlan_management, test_service, etc.)
**Should Show:** Jinja2 config templates (cisco_ios_create_vlans, cisco_ios_add_ip_int, etc.)

**Change in services.js:**
```javascript
// Old: loadServiceTemplates() calls /api/services/templates
// New: Should call /api/templates to get J2 templates
$.get('/api/templates')  // Returns: {templates: ["cisco_ios_create_vlans", ...]}
```

### 2. Service Creation Form
**Currently:** Complex form based on Python Pydantic schema
**Should Be:** Simple form with:
- Service Name (text input)
- Template Selection (dropdown from /api/templates)
- Device Selection (dropdown from existing device list)
- Variables (JSON textarea or key-value pairs)
- Optional: Reverse Template (dropdown)
- Optional: Username/Password override

**Example Form:**
```html
<input type="text" id="service-name" placeholder="My VLAN Service">
<select id="template-select">
  <option value="cisco_ios_create_vlans">Create VLANs</option>
  ...
</select>
<select id="device-select">
  <!-- Populated from existing device cache -->
</select>
<textarea id="template-variables" placeholder='{"vlan_id": 100, "vlan_name": "Guest"}'></textarea>
```

### 3. Service Creation Submission
**Currently:** POST to `/api/services/instances/create/<template_name>`
**Should Be:** POST to `/api/services/instances/create`

**Payload Change:**
```javascript
// Old payload (Python service):
{
  "hostname": "switch1",
  "vlan_id": 100,
  // ... other Pydantic model fields
}

// New payload (Template service):
{
  "name": "Guest VLAN Service",
  "template": "cisco_ios_create_vlans.j2",
  "reverse_template": "cisco_ios_remove_vlans.j2",  // optional
  "variables": {
    "vlan_id": 100,
    "vlan_name": "Guest_WiFi"
  },
  "device": "switch1",
  "username": "admin",  // optional - uses settings default if not provided
  "password": "secret"  // optional
}
```

### 4. Service Instances Display
**Currently:** Tries to parse `instance.service_meta` structure from Netpalm
**Should Be:** Use flat structure from new API

**Already Fixed!** The instances display was already updated to handle flat structure.

## Quick Implementation Steps

### Step 1: Update Template Loading
In `services.js`, line ~23:
```javascript
// Change from:
$.get('/api/services/templates')

// To:
$.get('/api/templates')
```

Then update `renderServiceTemplates()` to handle the new format:
```javascript
function renderServiceTemplates(templates) {
    const grid = $('#templates-grid');
    grid.empty();

    templates.forEach(function(templateName) {
        const card = `
            <div class="col-md-4">
                <div class="card service-template-card" data-template="${templateName}">
                    <div class="card-body">
                        <h6>${templateName}</h6>
                        <button class="btn btn-sm btn-primary use-template-btn">
                            <i class="fas fa-plus"></i> Use This Template
                        </button>
                    </div>
                </div>
            </div>
        `;
        grid.append(card);
    });

    // Add click handler
    $('.use-template-btn').on('click', function() {
        const template = $(this).closest('.service-template-card').data('template');
        showServiceCreationForm(template);
    });
}
```

### Step 2: Simplify Service Creation Form
Replace the complex schema-based form with a simple form:

```javascript
function showServiceCreationForm(templateName) {
    const modal = new bootstrap.Modal(document.getElementById('createServiceModal'));

    // Build simple form
    const formHtml = `
        <div class="mb-3">
            <label>Service Name</label>
            <input type="text" class="form-control" id="service-name-input"
                   placeholder="e.g., Guest VLAN on Access Switches">
        </div>
        <div class="mb-3">
            <label>Template</label>
            <input type="text" class="form-control" value="${templateName}" readonly>
        </div>
        <div class="mb-3">
            <label>Device</label>
            <select class="form-select" id="device-select">
                <option value="">Select device...</option>
                <!-- Will be populated from device cache -->
            </select>
        </div>
        <div class="mb-3">
            <label>Template Variables (JSON)</label>
            <textarea class="form-control" id="template-vars" rows="5"
                      placeholder='{"vlan_id": 100, "vlan_name": "Guest"}'></textarea>
        </div>
        <div class="mb-3">
            <label>Reverse Template (Optional)</label>
            <select class="form-select" id="reverse-template-select">
                <option value="">None</option>
                <!-- Populate from /api/templates -->
            </select>
        </div>
    `;

    $('#service-creation-form').html(formHtml);
    $('#create-service-name').val(templateName);  // Store for later

    // Load devices into dropdown
    loadDevicesIntoSelect();

    modal.show();
}
```

### Step 3: Update Service Creation Submission
```javascript
function createServiceInstance() {
    const serviceName = $('#service-name-input').val();
    const templateName = $('#create-service-name').val();
    const device = $('#device-select').val();
    const reverseTemplate = $('#reverse-template-select').val();

    let variables = {};
    try {
        variables = JSON.parse($('#template-vars').val() || '{}');
    } catch (e) {
        showStatus('error', { message: 'Invalid JSON in variables: ' + e.message });
        return;
    }

    // Get credentials from settings
    const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings') || '{}');

    const payload = {
        name: serviceName,
        template: templateName,
        variables: variables,
        device: device,
        username: settings.default_username,
        password: settings.default_password
    };

    if (reverseTemplate) {
        payload.reverse_template = reverseTemplate;
    }

    $('#create-service-btn').prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Creating...');

    $.ajax({
        url: '/api/services/instances/create',  // New endpoint
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload)
    })
    .done(function(data) {
        $('#create-service-btn').prop('disabled', false).html('<i class="fas fa-rocket"></i> Create Service');

        if (data.success) {
            showStatus('success', {
                message: `Service "${serviceName}" created successfully!`,
                service_id: data.service_id,
                task_id: data.task_id
            });
            bootstrap.Modal.getInstance(document.getElementById('createServiceModal')).hide();
            loadServiceInstances();
        } else {
            showStatus('error', data);
        }
    })
    .fail(function(xhr) {
        $('#create-service-btn').prop('disabled', false).html('<i class="fas fa-rocket"></i> Create Service');
        const errorMsg = xhr.responseJSON?.error || 'Failed to create service';
        showStatus('error', { message: errorMsg });
    });
}
```

## Testing After Updates

1. Refresh services page
2. Should see list of J2 templates instead of Python services
3. Click "Use This Template" on any template
4. Fill in form (name, device, variables)
5. Click "Create Service"
6. Should see service in instances list
7. Check task queue for config push job

## Files to Modify

1. `netpalm-gui/static/js/services.js` - Main changes
2. `netpalm-gui/templates/services.html` - Minor form updates if needed

## Estimated Time

- 30-60 minutes for someone familiar with JavaScript
- The backend is done, just need to wire up the frontend!
