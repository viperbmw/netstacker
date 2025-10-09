# Service Device Integration - New Feature!

## What Changed?

Services now integrate with your cached device list and default credentials, making it much easier to deploy services!

### Before (Manual Entry)
- Type device hostname manually
- Enter username/password every time
- Easy to make typos
- No validation that device exists

### After (Integrated)
- **Select device from dropdown** - uses your configured Netbox filters
- **Auto-fills credentials** - uses default username/password from settings
- **No typos** - select from existing devices
- **Consistent** - same devices as Deploy Config page

## How It Works

### 1. Device Selection
When you create a service instance:

**VLAN Management Service:**
```
┌─────────────────────────────────┐
│ Device: [Select a device... ▼] │  ← Dropdown populated from Netbox
│                                 │
│ • switch01.lab.local            │
│ • switch02.lab.local            │
│ • router01.lab.local            │
│ ...                             │
└─────────────────────────────────┘
```

**Benefits:**
- Only shows devices matching your Netbox filters
- Same device list as Deploy Config page
- No manual hostname typing
- Validated devices only

### 2. Automatic Credentials

The service form **hides** username/password fields and automatically uses:
- Default username from Settings
- Default password from Settings

**Before:**
```
Device: switch01.lab.local
Username: admin          ← Had to enter
Password: ********       ← Had to enter
VLAN ID: 100
```

**After:**
```
Device: [switch01.lab.local ▼]
VLAN ID: 100
```
Username and password are automatically added from settings!

### 3. Filtered Devices

The device dropdown respects your Netbox filters from Settings:

**Example:**
```
Settings → Netbox Device Filters:
- manufacturer_id = 7
- tag = production
```

**Result:**
Only production devices from manufacturer 7 appear in service dropdown!

## Updated Service Form Fields

### VLAN Management Service

**Required Fields:**
- ✅ **Device** - Dropdown (from cached device list)
- ✅ **VLAN ID** - Number (1-4094)
- ✅ **VLAN Name** - Text

**Optional Fields:**
- **Device Type** - Dropdown (cisco_ios, cisco_xe, etc.)
- **Description** - Text
- **Interfaces** - Comma-separated (e.g., `Gi1/0/1, Gi1/0/2`)
- **VLAN Enabled** - Yes/No
- **Timeout** - Number

**Hidden (Auto-filled from Settings):**
- Username - From default settings
- Password - From default settings

### Test Service

**Required Fields:**
- ✅ **Name** - Text

**Optional Fields:**
- **Description** - Text
- **Value** - Number (1-100)

**No device or credentials needed** - perfect for learning!

## Step-by-Step: Creating a VLAN with New UI

### 1. Configure Netbox Filters (Optional)
Go to **Settings** → Netbox Device Filters:
```
Key: tag
Value: core-network
```
This limits devices to only those tagged "core-network"

### 2. Set Default Credentials
Go to **Settings** → Default Credentials:
```
Default Username: netadmin
Default Password: YourSecurePassword
```

### 3. Create VLAN Service
1. Navigate to **Services**
2. Click **Create Instance** on "Vlan Management"
3. Fill the form:
   ```
   Device: [Select switch01.lab.local from dropdown]
   VLAN ID: 100
   VLAN Name: GUEST_WIFI
   Device Type: cisco_ios
   Interfaces: GigabitEthernet1/0/10, GigabitEthernet1/0/11
   ```
4. Click **Create Service**

**Behind the scenes:**
- Service receives: `hostname=switch01.lab.local`
- Auto-adds: `username=netadmin`
- Auto-adds: `password=YourSecurePassword`
- Connects to device and deploys VLAN

### 4. Result
Service instance created with:
- VLAN 100 named "GUEST_WIFI"
- Assigned to interfaces Gi1/0/10 and Gi1/0/11
- Using your default credentials
- Tracked as active service instance

## Technical Details

### Device Loading
When you open the create service form:

```javascript
// 1. Load devices from Netbox (with filters)
Promise.all([
    $.get('/api/services/templates/vlan_management/schema'),
    loadDevicesForService()  // ← Loads filtered devices
])

// 2. Render form with device dropdown
function renderServiceForm(schema, devices) {
    if (field.format === 'device_select') {
        // Create dropdown from devices
        devices.forEach(device => {
            html += `<option value="${device.name}">${device.display}</option>`;
        });
    }
}
```

### Credential Auto-Fill
When you submit the form:

```javascript
// Collect form data
payload = {
    hostname: 'switch01.lab.local',
    vlan_id: 100,
    vlan_name: 'GUEST_WIFI'
    // username and password NOT in form
}

// Auto-add from settings
const settings = JSON.parse(localStorage.getItem('netpalm_gui_settings'));
if (!payload.username && settings.default_username) {
    payload.username = settings.default_username;  // ← Added here
}
if (!payload.password && settings.default_password) {
    payload.password = settings.default_password;  // ← Added here
}

// Now payload has credentials:
// {
//   hostname: 'switch01.lab.local',
//   vlan_id: 100,
//   vlan_name: 'GUEST_WIFI',
//   username: 'netadmin',
//   password: 'YourSecurePassword'
// }
```

### Schema Format
Services use special field formats:

```python
# In service schema (app.py)
'hostname': {
    'type': 'string',
    'title': 'Device',
    'description': 'Select device from inventory',
    'format': 'device_select'  # ← Special format for dropdown
},
'username': {
    'type': 'string',
    'format': 'hidden_default'  # ← Hidden, uses settings default
},
'password': {
    'type': 'string',
    'format': 'hidden_default'  # ← Hidden, uses settings default
}
```

## Creating Your Own Integrated Service

To add device selection and auto-credentials to a new service:

### 1. Update Schema (in app.py)
```python
'your_service': {
    'title': 'YourServiceModel',
    'type': 'object',
    'required': ['hostname', 'other_required_field'],
    'properties': {
        'hostname': {
            'type': 'string',
            'title': 'Device',
            'description': 'Select device from inventory',
            'format': 'device_select'  # ← Use this format
        },
        'username': {
            'type': 'string',
            'format': 'hidden_default'  # ← Auto-fill from settings
        },
        'password': {
            'type': 'string',
            'format': 'hidden_default'  # ← Auto-fill from settings
        },
        # ... your other fields
    }
}
```

### 2. Python Service (your_service.py)
```python
class YourServiceModel(BaseModel):
    hostname: str = Field(..., description="Device hostname")
    username: str = Field(default="admin", description="Username")
    password: str = Field(default="admin", description="Password")
    # ... your other fields

class YourService(NetpalmService):
    def create(self, model_data: model):
        # model_data.hostname = device from dropdown
        # model_data.username = from settings (or default)
        # model_data.password = from settings (or default)

        # Use these to connect to device
        connection_args = {
            "host": model_data.hostname,
            "username": model_data.username,
            "password": model_data.password
        }
```

## Troubleshooting

### Device Dropdown is Empty
**Cause**: No devices match your Netbox filters
**Solution**:
1. Check Settings → Netbox Device Filters
2. Remove or adjust filters
3. Click "Clear Cache & Reload" on Devices page
4. Try creating service again

### Wrong Devices in Dropdown
**Cause**: Netbox filters are configured
**Solution**:
1. Go to Settings → Netbox Device Filters
2. Review your filters
3. Adjust as needed
4. Clear cache and reload

### Credentials Not Working
**Cause**: Default credentials not set or incorrect
**Solution**:
1. Go to Settings → Default Credentials
2. Verify username and password
3. Test with "Deploy Config" first
4. Then try service

### Want to Override Credentials
**Cause**: Need different creds for specific service
**Solution**:
Currently, all services use default credentials. To use different creds:
1. Update default credentials in Settings
2. Deploy service
3. Change default credentials back

Or manually edit the service schema to show username/password fields.

## Benefits Summary

### For Users
- ✅ Faster service deployment
- ✅ No credential re-entry
- ✅ No typos in hostnames
- ✅ Consistent with Deploy Config
- ✅ Filter-aware device selection

### For Automation
- ✅ Same device filtering everywhere
- ✅ Centralized credential management
- ✅ Reduced human error
- ✅ Better security (credentials in one place)

## Next Steps

1. **Set Default Credentials** in Settings
2. **Configure Netbox Filters** (optional)
3. **Try VLAN Service** with device dropdown
4. **Create Custom Services** using device_select format

---

**Pro Tip**: The device dropdown and auto-credentials work for ALL services that use the special schema formats. Update your custom services to use `format: 'device_select'` and `format: 'hidden_default'` to get this functionality!
