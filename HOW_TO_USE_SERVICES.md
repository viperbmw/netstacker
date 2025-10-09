# How to Use Netpalm Services - Quick Start Guide

## What are Services? (Simple Explanation)

**Services are NOT templates.** They're completely different from the Jinja2 templates you use for configuration.

Think of services as **automated workflows that remember what they did**, so you can:
1. **Create** - Deploy configuration to a device
2. **Validate** - Check if it's still correct
3. **Update** - Change the configuration
4. **Delete** - Clean it up when you're done

## Example: VLAN Management Service

### What This Service Does

The VLAN Management service automates managing VLANs on switches:
- Creates a VLAN with a specific ID and name
- Optionally assigns interfaces to the VLAN
- Tracks what it created so you can modify or delete it later

### Step-by-Step: Creating a VLAN

#### 1. Go to Services Page
Navigate to **Services** in the main menu

#### 2. Click "Create Instance" on VLAN Management

You'll see a form with these fields:

**Required Fields:**
- **Hostname**: IP address or hostname of your switch (e.g., `192.168.1.1` or `switch01.lab.local`)
- **VLAN ID**: Number between 1-4094 (e.g., `100`)
- **VLAN Name**: What to call the VLAN (e.g., `GUEST_WIFI`)

**Optional Fields (with defaults):**
- **Device Type**: Type of device (defaults to `cisco_ios`)
  - cisco_ios
  - cisco_xe
  - cisco_nxos
  - arista_eos
  - juniper_junos
- **Username**: Device login (defaults to `admin`)
- **Password**: Device password (defaults to `admin`)
- **Description**: Optional VLAN description
- **Interfaces**: Comma-separated list of interfaces to assign to this VLAN
  - Example: `GigabitEthernet1/0/1, GigabitEthernet1/0/2`
- **VLAN Enabled**: Whether VLAN is active (defaults to `True`)
- **Timeout**: Connection timeout in seconds (defaults to `30`)

#### 3. Fill in the Form

Example for creating a guest WiFi VLAN:
```
Hostname: 192.168.1.10
VLAN ID: 100
VLAN Name: GUEST_WIFI
Device Type: cisco_ios
Username: admin
Password: mypassword
Description: Guest wireless network
Interfaces: GigabitEthernet1/0/5, GigabitEthernet1/0/6
VLAN Enabled: True
Timeout: 30
```

#### 4. Click "Create Service"

The service will:
1. Connect to the switch
2. Run these commands:
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
3. Save the configuration details
4. Set status to "active"

#### 5. Service Instance Created!

You'll see it in the "Service Instances" table below with:
- Service ID (unique identifier)
- Service Model (vlan_management)
- State (active, creating, errored, etc.)
- Created/Updated timestamps

### What Happens Behind the Scenes

When you create a service, the Python code:

```python
def create(self, model_data: model):
    # 1. Build commands from your input
    commands = [
        f"vlan {model_data.vlan_id}",
        f"name {model_data.vlan_name}",
        "exit"
    ]

    # 2. Add interface configuration
    for interface in model_data.interfaces:
        commands.extend([
            f"interface {interface}",
            "switchport mode access",
            f"switchport access vlan {model_data.vlan_id}",
            "exit"
        ])

    # 3. Execute on device using Netmiko
    result = self._execute_command(model_data, commands, operation="config")

    # 4. Save metadata about what we did
    self.mgr.set_service_instance_meta(self.service_id, {
        "hostname": model_data.hostname,
        "vlan_id": model_data.vlan_id,
        "vlan_name": model_data.vlan_name,
        "interfaces": model_data.interfaces
    })

    # 5. Mark as active
    self.mgr.set_service_instance_status(self.service_id, state="active")

    return {"status": "success", "vlan_id": model_data.vlan_id}
```

### Managing Your Service Instance

Once created, you can click these buttons on the service instance:

#### 👁️ View Details
See all the configuration details:
- Service ID
- State
- What VLAN was created
- Which interfaces were configured
- When it was created/updated

#### ✅ Validate
Checks if the VLAN still exists and is configured correctly:
```python
def validate(self, model_data: model):
    # Runs: show vlan id 100
    # Verifies VLAN exists with correct name and interfaces
```

#### 💓 Health Check
Verifies the VLAN is operational:
```python
def health_check(self, model_data: model):
    # Checks VLAN status
    # Checks interface status
    # Returns healthy/unhealthy
```

#### 🔄 Redeploy
Someone manually changed the VLAN name? Redeploy fixes it:
```python
def re_deploy(self, model_data: model):
    # Removes VLAN
    # Re-creates it with correct configuration
```

#### 🗑️ Delete
Cleanly removes the VLAN:
```python
def delete(self, model_data: model):
    # Removes VLAN from interfaces
    # Deletes the VLAN
    # Removes service instance
```

## Service vs. Templates - Key Differences

### Configuration Templates (Jinja2)
- **Purpose**: Generate configuration snippets
- **Files**: `.j2` files with variables
- **Usage**: One-time config generation
- **Example**:
  ```jinja2
  vlan {{ vlan_id }}
   name {{ vlan_name }}
  ```
- **Result**: Text output you copy/paste or deploy once

### Services (Python Classes)
- **Purpose**: Full lifecycle management
- **Files**: `.py` files with Python code
- **Usage**: Create, track, update, delete
- **Example**: Python class with create(), validate(), delete() methods
- **Result**: Stateful instance you can manage over time

## When to Use Services

**Use a Service when:**
- ✅ You need to track what you deployed
- ✅ You want to validate configuration hasn't drifted
- ✅ You might need to update it later
- ✅ You want clean removal when done
- ✅ You need health monitoring

**Use a Template when:**
- ✅ One-time configuration deployment
- ✅ Simple text generation
- ✅ Ad-hoc changes
- ✅ No need to track state

## Common Use Cases

### 1. VLAN Management (included)
Create, track, and manage VLANs across switches

### 2. BGP Neighbor (you could create)
- Create: Configure BGP neighbor
- Validate: Check neighbor is in config
- Health Check: Verify BGP session is established
- Delete: Remove neighbor cleanly

### 3. Interface Configuration (you could create)
- Create: Set IP, description, speed
- Validate: Verify config matches
- Update: Change IP or description
- Delete: Reset to defaults

### 4. Static Routes (you could create)
- Create: Add static routes
- Validate: Routes still in table
- Delete: Remove routes

## Testing the VLAN Service (Safe Test)

Try this with a test switch:

1. **Create Service**:
   - Hostname: `your-test-switch-ip`
   - VLAN ID: `999`
   - VLAN Name: `TEST_VLAN`
   - Username/Password: Your switch credentials
   - Leave interfaces empty (safer for testing)

2. **Check Status**:
   - Should show "active" state
   - Click "View Details" to see metadata

3. **Validate**:
   - Click validate button
   - Should confirm VLAN exists

4. **Delete**:
   - Click delete button
   - Removes VLAN from switch
   - Removes service instance

## Troubleshooting

### Service shows "errored" state
- Check device credentials
- Verify device is reachable
- Check device type is correct
- View service details for error message

### VLAN not created
- Verify switch supports VLAN ID range
- Check if VLAN already exists
- Verify user has config privileges

### Can't delete service
- Try "Redeploy" first to fix state
- Manually remove VLAN if needed
- Then delete service instance

## API Usage (for automation)

### Create Service Instance
```bash
curl -X POST http://localhost:9000/service/vlan_management \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "hostname": "192.168.1.10",
    "vlan_id": 100,
    "vlan_name": "GUEST_WIFI",
    "username": "admin",
    "password": "admin",
    "device_type": "cisco_ios"
  }'
```

Response:
```json
{
  "status": "success",
  "data": {
    "task_id": "abc-123",
    "service_id": "xyz-789"
  }
}
```

### Check Service Status
```bash
curl http://localhost:9000/service/instance/xyz-789 \
  -H "x-api-key: YOUR_API_KEY"
```

### Validate Service
```bash
curl -X POST http://localhost:9000/service/instance/xyz-789/validate \
  -H "x-api-key: YOUR_API_KEY"
```

### Delete Service
```bash
curl -X DELETE http://localhost:9000/service/instance/xyz-789 \
  -H "x-api-key: YOUR_API_KEY"
```

## Next Steps

1. **Try the Example**: Create a test VLAN on a lab switch
2. **Read the Code**: Look at `vlan_management.py` to understand the implementation
3. **Create Your Own**: Use `vlan_management.py` as a template for your own service
4. **Check Docs**: See `SERVICES_GUIDE.md` for detailed documentation

## Quick Reference

| Action | What It Does | When to Use |
|--------|-------------|-------------|
| Create | Deploy config | First time setup |
| Validate | Check config matches | Detect drift |
| Health Check | Verify operational | Monitor health |
| Update | Change config | Modify settings |
| Redeploy | Force correct state | Fix drift |
| Delete | Remove config | Decommission |

## Real World Example

**Scenario**: You have 50 switches and need to add VLAN 200 for IoT devices on ports Gi1/0/10-15

**Without Services:**
1. Manually configure each switch
2. Hope you remembered all 50
3. No easy way to verify later
4. Manual cleanup when done

**With VLAN Service:**
1. Create 50 service instances (can be automated via API)
2. Track all 50 in one place
3. Run validate on all to check for drift
4. Delete all when project is done

---

**Remember**: Services are not templates - they're automated workflows that track and manage configuration over time!
