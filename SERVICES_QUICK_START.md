# Netpalm Services - Quick Start Guide

## Try It Now! (5 Minute Test)

The fastest way to understand services is to try the **Test Service** - it doesn't need any network devices!

### Step 1: Open Services Page
1. Navigate to http://localhost:8088/services
2. You'll see three service templates:
   - **Test Service** ← Start here!
   - **VLAN Management**
   - **Example Simple**

### Step 2: Create a Test Service Instance
1. Click **"Create Instance"** on the "Test Service" card
2. You'll see a simple form:
   - **Name** (required): Enter `my-first-test`
   - **Description** (optional): Enter `Learning how services work`
   - **Value** (optional): Default is 42, try changing to `77`
3. Click **"Create Service"**

### Step 3: What Just Happened?
Behind the scenes, the service:
1. Created a service instance with ID like `xyz-789`
2. Stored your data (name, description, value) as metadata
3. Set the state to "active"
4. Returned success

No network device was touched - this is just demonstrating the lifecycle!

### Step 4: View Your Service
Look at the "Service Instances" table below. You'll see:
- **Service ID**: `xyz-789` (unique identifier)
- **Service Model**: `test_service`
- **State**: `active` (green badge)
- **Created**: Timestamp
- **Actions**: 5 buttons

### Step 5: Try the Actions

#### 👁️ View Details
Click the eye icon to see:
```json
{
  "service_id": "xyz-789",
  "service_model": "test_service",
  "state": "active",
  "metadata": {
    "name": "my-first-test",
    "description": "Learning how services work",
    "value": 77,
    "created_at": "2025-10-09 21:20:00"
  }
}
```

#### ✅ Validate
Click the checkmark icon. The service checks if the stored data matches what you originally entered. Returns:
```json
{
  "status": "success",
  "message": "Validation passed",
  "validation": {
    "name_matches": true,
    "value_matches": true
  }
}
```

#### 💓 Health Check
Click the heartbeat icon. Returns:
```json
{
  "status": "healthy",
  "message": "Service is healthy",
  "uptime": "Always up - this is a test service!"
}
```

#### 🔄 Redeploy
Click the redo icon. It re-creates the service with the same data.

#### 🗑️ Delete
Click the trash icon. It removes the service instance completely.

## What You Learned

### Services Track State
Unlike templates which just generate text, services:
- Store what they created (`metadata`)
- Track their status (`active`, `creating`, `errored`)
- Remember their configuration over time

### Services Have a Lifecycle
1. **Create** → Deploy something
2. **Validate** → Check it's still correct
3. **Health Check** → Verify it's working
4. **Update** → Change configuration
5. **Redeploy** → Fix drift
6. **Delete** → Clean removal

### Services vs Templates

| Feature | Templates | Services |
|---------|-----------|----------|
| Output | Text/config | Actions on devices |
| State | Stateless | Stateful |
| Tracking | None | Full metadata |
| Lifecycle | Generate once | Create, update, delete |
| Use Case | One-time config | Ongoing management |

## Real Service Example: VLAN Management

Now that you understand the concept, try the VLAN service (requires a real switch):

### 1. Create VLAN Instance
Fill in the form:
```
Hostname: 192.168.1.10
VLAN ID: 100
VLAN Name: GUEST_WIFI
Device Type: cisco_ios
Username: admin
Password: yourpassword
Interfaces: GigabitEthernet1/0/5, GigabitEthernet1/0/6
```

### 2. What It Does
The service executes:
```
vlan 100
 name GUEST_WIFI
 exit
interface GigabitEthernet1/0/5
 switchport mode access
 switchport access vlan 100
 exit
interface GigabitEthernet1/0/6
 switchport mode access
 switchport access vlan 100
 exit
```

### 3. Stores Metadata
```json
{
  "hostname": "192.168.1.10",
  "vlan_id": 100,
  "vlan_name": "GUEST_WIFI",
  "interfaces": ["GigabitEthernet1/0/5", "GigabitEthernet1/0/6"],
  "created_at": "2025-10-09 21:20:00"
}
```

### 4. Lifecycle Actions

**Validate**: Runs `show vlan id 100` and checks:
- VLAN exists
- Name matches "GUEST_WIFI"
- Interfaces are assigned

**Health Check**: Verifies:
- VLAN is operational
- Interfaces are up

**Update**: Change VLAN name or add/remove interfaces
- Only changes what you modify
- Stores updated metadata

**Redeploy**: If someone manually changed the VLAN name
- Removes VLAN
- Re-creates with correct configuration

**Delete**: Clean removal
- Removes VLAN from interfaces
- Deletes the VLAN
- Removes service instance

## Understanding the Python Code

### Simple Example (Test Service)
```python
class TestService(NetpalmService):
    mgr = NetpalmManager()  # Manages operations
    model = TestServiceModel  # Input validation

    def create(self, model_data: model):
        # 1. Do something (or nothing for test)

        # 2. Store metadata
        self.mgr.set_service_instance_meta(self.service_id, {
            "name": model_data.name,
            "value": model_data.value
        })

        # 3. Set state
        self.mgr.set_service_instance_status(self.service_id, state="active")

        # 4. Return result
        return {"status": "success"}
```

### Real Example (VLAN Service)
```python
def create(self, model_data: model):
    # 1. Build commands
    commands = [
        f"vlan {model_data.vlan_id}",
        f"name {model_data.vlan_name}"
    ]

    # 2. Execute on device
    result = self._execute_command(model_data, commands, operation="config")

    # 3. Store what we did
    self.mgr.set_service_instance_meta(self.service_id, {
        "hostname": model_data.hostname,
        "vlan_id": model_data.vlan_id,
        "vlan_name": model_data.vlan_name
    })

    # 4. Set state
    self.mgr.set_service_instance_status(self.service_id, state="active")

    return {"status": "success"}
```

## Common Questions

### Q: Do I need templates to use services?
**A**: No! Services are completely independent. They execute commands directly, they don't use Jinja2 templates.

### Q: Can services use templates?
**A**: Yes, if you want! You could:
1. Load a Jinja2 template inside your service
2. Render it with variables
3. Execute the rendered config

But it's optional - many services just build commands directly in Python.

### Q: When should I use a service vs a template?
**A**:
- **Template**: One-time config generation, ad-hoc changes
- **Service**: When you need to track, update, or manage config over time

### Q: Can I automate services via API?
**A**: Yes! Services are designed for automation:

```bash
# Create service
curl -X POST http://localhost:9000/service/vlan_management \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_KEY" \
  -d '{"hostname": "192.168.1.10", "vlan_id": 100, "vlan_name": "GUEST"}'

# Get service ID from response
SERVICE_ID="xyz-789"

# Validate
curl -X POST http://localhost:9000/service/instance/$SERVICE_ID/validate \
  -H "x-api-key: YOUR_KEY"

# Delete
curl -X DELETE http://localhost:9000/service/instance/$SERVICE_ID \
  -H "x-api-key: YOUR_KEY"
```

### Q: How do I create my own service?
**A**:
1. Copy `test_service.py` or `vlan_management.py` as a template
2. Modify the Pydantic model for your inputs
3. Implement the lifecycle methods
4. Add schema to GUI app.py (optional, for UI support)
5. Rebuild containers: `docker compose build && docker compose up -d`

## Next Steps

### 1. Practice with Test Service
- Create a few test instances
- Try all the action buttons
- Delete them when done

### 2. Try VLAN Service (if you have a lab switch)
- Start with an unused VLAN ID
- Don't assign interfaces at first (safer)
- Test validate and health check
- Delete when done

### 3. Read the Code
- Study `test_service.py` - simplest example
- Study `vlan_management.py` - complete example
- Read `SERVICES_GUIDE.md` - detailed documentation

### 4. Build Your Own
Common service ideas:
- **Static Routes**: Add/remove static routes
- **SNMP Config**: Configure SNMP settings
- **NTP Servers**: Manage NTP configuration
- **BGP Neighbors**: Configure BGP peering
- **Interface Description**: Set interface descriptions

### 5. Automate
- Use the API to create services programmatically
- Build workflows that create multiple service instances
- Schedule health checks with cron/scheduler
- Auto-remediate with redeploy when validation fails

## Summary

**Services are Python workflows that:**
- Execute commands on devices
- Track what they did (metadata)
- Maintain state (active, errored, etc.)
- Support lifecycle operations (create, validate, update, delete)

**Start with test_service to learn, then move to real services like vlan_management!**

---

**Pro Tip**: The test_service is perfect for:
- Learning the UI
- Understanding the lifecycle
- Testing your service templates before adding device logic
- Demonstrating Netpalm to others without needing real hardware
