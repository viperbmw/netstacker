# Template-Based Services Migration

## Overview

We're replacing the complex Python-based service system with a simple template-based approach where:

**Service = Template + Variables + Devices**

## Architecture

### Old Approach (Python Services)
- Services were Python classes with lifecycle methods
- Required Python knowledge to create
- Stored in Netpalm's Redis with complex structure
- Disconnected from template system

### New Approach (Template Services)
- Services use existing Jinja2 templates
- User provides variables and target devices
- GUI handles all orchestration
- Stored in Redis with simple JSON structure

## Service Instance Structure

```json
{
  "service_id": "uuid",
  "name": "User-friendly name",
  "template": "vlan_config.j2",
  "reverse_template": "vlan_remove.j2",
  "variables": {
    "vlan_id": 100,
    "vlan_name": "Guest_WiFi"
  },
  "devices": ["switch1", "switch2"],
  "state": "active",
  "created_at": "2025-10-09T22:00:00",
  "updated_at": "2025-10-09T22:00:00"
}
```

## Lifecycle Operations

### Create
1. Get device info from Netbox (device_type, IP)
2. Get credentials from settings (or use override)
3. Render template with variables
4. Push rendered config to each device via setconfig
5. Save service instance to Redis
6. Return task IDs for monitoring

### Validate (Drift Detection)
1. Render template with current variables
2. Fetch config from each device via getconfig
3. Check if rendered config exists in device config
4. Return validation status per device

### Update
1. Render template with new variables
2. Push to all devices (including any new ones added)
3. Update service instance in Redis

### Re-deploy
1. Same as create (push existing config again)

### Delete
1. If reverse_template exists:
   - Render reverse template with variables
   - Push to all devices
2. Delete service instance from Redis

## Storage

- **Key Format**: `gui_service:<service_id>`
- **Backend**: Same Redis instance as Netpalm
- **Managed By**: GUI app.py (not Netpalm services)

## Benefits

1. **Simple**: No Python knowledge required
2. **Intuitive**: Users already understand templates
3. **Flexible**: Works with existing template system
4. **Drift Detection**: Validation checks if config matches
5. **Reversible**: Optional reverse templates for clean deletion
6. **Device-Aware**: Auto-populates connection info from Netbox

## Implementation Status

### Completed
- [x] Redis storage functions
- [x] Service instance CRUD operations
- [x] Updated service listing endpoint

### In Progress
- [ ] Service creation with template rendering
- [ ] Device info gathering from Netbox
- [ ] Config push orchestration
- [ ] Validation/drift detection
- [ ] Delete with reverse template

### Pending
- [ ] Update GUI JavaScript for new flow
- [ ] Add reverse template upload UI
- [ ] Update service creation form
- [ ] Add validation UI
- [ ] Testing with real devices

## Migration Plan

1. **Phase 1**: Implement GUI-based storage (DONE)
2. **Phase 2**: Implement create/delete endpoints
3. **Phase 3**: Implement validate/health_check
4. **Phase 4**: Update frontend UI
5. **Phase 5**: Test end-to-end
6. **Phase 6**: Remove old Python services

## Notes

- Credentials are automatically pulled from:
  1. Netbox device data (device_type, IP)
  2. GUI settings (default username/password)
  3. Optional per-service override

- No changes needed to Netpalm core
- Backwards compatible - old services still work
- Can be rolled back if needed
