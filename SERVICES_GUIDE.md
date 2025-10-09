# Netpalm Services Guide

## What are Netpalm Services?

Netpalm Services are **stateful, lifecycle-managed network automation workflows**. Unlike simple getconfig/setconfig operations, services maintain state and can be created, updated, validated, and deleted over time.

Think of services as "infrastructure as code" for network configurations - they track what was deployed, allow you to update it, validate it's still correct, and cleanly remove it when no longer needed.

## Service Lifecycle

A Netpalm service has 6 lifecycle methods:

### 1. **create()** - Deploy the service
- **Purpose**: Initial deployment of the configuration
- **When to use**: First time deploying the service
- **Example**: Create a VLAN on a switch
- **State transitions**: `creating` → `active` (or `errored`)

### 2. **validate()** - Verify configuration matches intent
- **Purpose**: Check if the deployed config matches what the service expects
- **When to use**: After deployment or periodically to check for drift
- **Example**: Verify VLAN exists with correct name and interfaces
- **State**: No state change (read-only operation)

### 3. **health_check()** - Check operational health
- **Purpose**: Verify the service is working correctly
- **When to use**: Scheduled health monitoring or troubleshooting
- **Example**: Check if VLAN is up and interfaces are passing traffic
- **State**: Updates to `errored` if unhealthy

### 4. **update()** - Modify existing configuration
- **Purpose**: Change service parameters without recreating
- **When to use**: When you need to modify the configuration
- **Example**: Change VLAN name or add/remove interfaces
- **State transitions**: `active` → `updating` → `active`

### 5. **re_deploy()** - Reapply configuration
- **Purpose**: Fix configuration drift by removing and redeploying
- **When to use**: When validation shows drift and you want to force correct state
- **Example**: Someone manually changed the VLAN name, re_deploy fixes it
- **State**: Removes and recreates the service

### 6. **delete()** - Remove configuration
- **Purpose**: Clean up and remove the service
- **When to use**: Service is no longer needed
- **Example**: Remove VLAN from device
- **State transitions**: `active` → `deleting` → (instance removed)

## Service States

Services can be in the following states:

- **creating**: Service is being deployed
- **active**: Service is deployed and healthy
- **updating**: Service configuration is being modified
- **errored**: Service encountered an error
- **deleting**: Service is being removed

## Service Architecture

### Components

1. **Pydantic Model** (`BaseModel`)
   - Defines input parameters
   - Validates data
   - Provides type hints
   - Documents expected fields

2. **Service Class** (`NetpalmService`)
   - Implements lifecycle methods
   - Uses NetpalmManager for operations
   - Manages service state
   - Stores metadata

3. **NetpalmManager** (`self.mgr`)
   - Executes network operations (getconfig, setconfig, script)
   - Manages service state and metadata
   - Retrieves task results

### Key Attributes

- `self.service_id` - Unique identifier for this service instance
- `self.mgr` - NetpalmManager for executing operations
- `self.model` - Associated Pydantic model

### Key Methods (NetpalmManager)

```python
# Execute network operations
job_result = self.mgr.get_config_netmiko(data)  # Get config
job_result = self.mgr.set_config_netmiko(data)  # Set config
result = self.mgr.retrieve_task_result(job_result)  # Get task result

# Manage service state
self.mgr.set_service_instance_status(self.service_id, state="active")
self.mgr.set_service_instance_status(self.service_id, state="errored")

# Store/retrieve metadata
self.mgr.set_service_instance_meta(self.service_id, metadata_dict)
metadata = self.mgr.get_service_instance_meta(self.service_id)

# Timestamps
timestamp = self.mgr.get_current_timestamp()
```

## Service API Endpoints

### Create a service instance
```bash
POST /service/{service_name}

{
    "hostname": "switch01.lab.local",
    "vlan_id": 100,
    "vlan_name": "GUEST_WIFI"
}

Response: {"service_id": "abc-123", "status": "creating"}
```

### List service instances
```bash
GET /service/instances/

Response: [
    {"service_id": "abc-123", "service_name": "vlan_management", "state": "active"},
    ...
]
```

### Get service instance details
```bash
GET /service/instance/{service_id}

Response: {
    "service_id": "abc-123",
    "service_name": "vlan_management",
    "state": "active",
    "metadata": {...}
}
```

### Validate service
```bash
POST /service/instance/{service_id}/validate

Response: {"status": "success", "validation": {...}}
```

### Health check
```bash
POST /service/instance/{service_id}/health_check

Response: {"status": "healthy", ...}
```

### Update service
```bash
POST /service/instance/{service_id}/update

{
    "hostname": "switch01.lab.local",
    "vlan_id": 100,
    "vlan_name": "NEW_NAME"
}

Response: {"status": "success", ...}
```

### Re-deploy service
```bash
POST /service/instance/{service_id}/redeploy

Response: {"status": "success", ...}
```

### Delete service
```bash
DELETE /service/instance/{service_id}

Response: {"status": "success", "message": "Service deleted"}
```

## Best Practices

### 1. **Use Pydantic Models for Validation**
```python
class MyServiceModel(BaseModel):
    hostname: str = Field(..., description="Device hostname")
    vlan_id: int = Field(..., ge=1, le=4094)  # Validate range

    @validator('hostname')
    def validate_hostname(cls, v):
        # Custom validation
        return v
```

### 2. **Store Metadata**
Always store deployment information for later use:
```python
def create(self, model_data: model):
    # ... deploy config ...

    metadata = {
        "hostname": model_data.hostname,
        "deployed_at": str(self.mgr.get_current_timestamp()),
        "config": commands,
        "result": result
    }
    self.mgr.set_service_instance_meta(self.service_id, metadata)
```

### 3. **Update State Appropriately**
```python
# On success
self.mgr.set_service_instance_status(self.service_id, state="active")

# On error
self.mgr.set_service_instance_status(self.service_id, state="errored")

# During updates
self.mgr.set_service_instance_status(self.service_id, state="updating")
# ... update logic ...
self.mgr.set_service_instance_status(self.service_id, state="active")
```

### 4. **Handle Errors Gracefully**
```python
def create(self, model_data: model):
    try:
        # ... deployment logic ...
        self.mgr.set_service_instance_status(self.service_id, state="active")
        return {"status": "success", ...}
    except Exception as e:
        log.error(f"[{self.service_id}] Error: {str(e)}")
        self.mgr.set_service_instance_status(self.service_id, state="errored")
        return {"status": "error", "error": str(e)}
```

### 5. **Use Helper Methods**
Keep code DRY by creating helper methods:
```python
def _get_connection_args(self, model_data: model):
    return {
        "device_type": model_data.device_type,
        "host": model_data.hostname,
        "username": model_data.username,
        "password": model_data.password,
    }

def _execute_command(self, model_data: model, commands: List[str]):
    # Shared command execution logic
    ...
```

### 6. **Log Everything**
```python
log.info(f"[{self.service_id}] Creating service on {model_data.hostname}")
log.error(f"[{self.service_id}] Failed: {str(e)}")
```

### 7. **Validate Before Update**
```python
def update(self, model_data: model):
    # Get current state
    current_meta = self.mgr.get_service_instance_meta(self.service_id)

    # Only update what changed
    if model_data.vlan_name != current_meta.get("vlan_name"):
        # Update VLAN name
        ...
```

## Common Use Cases

### 1. **VLAN Management**
- Create: Deploy VLAN to switch(es)
- Validate: Verify VLAN exists with correct name
- Update: Change VLAN name or add interfaces
- Delete: Remove VLAN cleanly

### 2. **BGP Neighbor Configuration**
- Create: Configure BGP neighbor
- Health_check: Verify BGP session is established
- Update: Change BGP parameters (timers, policies)
- Delete: Remove BGP neighbor

### 3. **Interface Configuration**
- Create: Configure interface (IP, description, etc.)
- Validate: Verify interface config matches
- Update: Change IP address or description
- Delete: Reset interface to default

### 4. **Access Control Lists (ACLs)**
- Create: Deploy ACL to device(s)
- Validate: Verify ACL rules are correct
- Update: Add/remove ACL entries
- Delete: Remove ACL

### 5. **Routing Policies**
- Create: Deploy route-map or prefix-list
- Validate: Verify policy is applied correctly
- Update: Modify policy rules
- Delete: Remove policy

## Service vs. Simple Automation

**Use Simple Automation (getconfig/setconfig) when:**
- One-time configuration changes
- Ad-hoc queries
- Simple commands
- No need to track state

**Use Services when:**
- Configuration needs to be tracked over time
- You want to validate/monitor configuration
- Configuration may need updates
- Clean removal is important
- Multiple devices need coordinated changes
- Configuration drift detection needed

## Debugging Services

### Check Service Status
```bash
GET /service/instance/{service_id}
```

### View Service Logs
```bash
docker logs netpalm-controller | grep {service_id}
```

### Get Service Metadata
Service metadata is returned in the instance details:
```python
metadata = self.mgr.get_service_instance_meta(self.service_id)
```

### Test Service Operations
Use the validate() and health_check() methods to test without making changes:
```bash
POST /service/instance/{service_id}/validate
POST /service/instance/{service_id}/health_check
```

## Example: Complete VLAN Service

See `/netpalm/backend/plugins/extensibles/services/vlan_management.py` for a comprehensive example that demonstrates:

- Full Pydantic model with validation
- All 6 lifecycle methods implemented
- Error handling and state management
- Metadata storage and retrieval
- Helper methods for code reuse
- Extensive logging
- Complete API usage examples

## Quick Start Template

```python
import logging
from pydantic import BaseModel, Field
from netpalm.backend.core.calls.service.netpalmservice import NetpalmService
from netpalm.backend.core.manager.netpalm_manager import NetpalmManager

log = logging.getLogger(__name__)

class MyServiceModel(BaseModel):
    hostname: str = Field(..., description="Device hostname")
    # Add your fields here

class MyService(NetpalmService):
    mgr = NetpalmManager()
    model = MyServiceModel

    def create(self, model_data: model):
        log.info(f"[{self.service_id}] Creating service")
        try:
            # Your deployment logic
            self.mgr.set_service_instance_status(self.service_id, state="active")
            return {"status": "success"}
        except Exception as e:
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}

    def validate(self, model_data: model):
        # Validation logic
        pass

    def health_check(self, model_data: model):
        # Health check logic
        pass

    def update(self, model_data: model):
        # Update logic
        pass

    def re_deploy(self, model_data: model):
        # Re-deploy logic
        pass

    def delete(self, model_data: model):
        # Deletion logic
        pass
```

## Additional Resources

- Netpalm Documentation: https://netpalm.readthedocs.io/
- Example Services: `/netpalm/backend/plugins/extensibles/services/`
- Service Base Class: `/netpalm/backend/core/calls/service/netpalmservice.py`
- API Docs: http://localhost:9000/docs (when Netpalm is running)
