# Services UI Updates

## Changes Made

### 1. Fixed API Docs Link
- **Issue**: Swagger docs link was pointing to `/docs` which doesn't exist
- **Fix**: Updated navigation link to point to `http://localhost:9000/` (Netpalm's Swagger UI root)
- **Location**: [templates/base.html:53](netpalm-gui/templates/base.html#L53)

### 2. Added Service Schema Support
- **Issue**: vlan_management service wasn't showing in UI with proper form
- **Fix**: Added hardcoded schemas for known services in the backend
- **Location**: [app.py:772-857](netpalm-gui/app.py#L772-L857)

#### Supported Services:
- **vlan_management**: Full VLAN lifecycle management
  - Required fields: hostname, vlan_id, vlan_name
  - Optional fields: device_type, username, password, description, interfaces, vlan_enabled, timeout
  - Field validation: VLAN ID (1-4094), device type enum, etc.

- **example_simple**: Basic example service
  - Required fields: hostname

### 3. Enhanced Form Rendering
Updated the services form to support all JSON Schema field types:

#### Field Type Support:
- **Integer/Number**: Input with min/max validation, default values
- **Boolean**: Select dropdown (True/False) with defaults
- **Enum**: Select dropdown with options and defaults
- **Array**: Comma-separated text input (for interfaces, etc.)
- **Password**: Password input field with masking
- **String**: Text input with minLength/maxLength validation

#### UI Improvements:
- Shows service description at top of form
- Uses field titles from schema (not just field names)
- Displays field descriptions as help text
- Shows required fields with red asterisk
- Pre-fills default values from schema
- Validates min/max, length constraints

**Location**: [services.js:93-169](netpalm-gui/static/js/services.js#L93-L169)

### 4. Array Field Handling
- **Issue**: Array fields (like interfaces) couldn't be entered
- **Fix**: Added comma-separated input with automatic array conversion
- **Example**: `GigabitEthernet1/0/1, GigabitEthernet1/0/2` → `["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"]`
- **Location**: [services.js:197-200](netpalm-gui/static/js/services.js#L197-L200)

### 5. Improved Service Cards
- Added descriptive text for each service template
- Better title formatting (converts underscores to spaces, title case)
- Clear descriptions:
  - vlan_management: "Deploy and manage VLANs across network devices with full lifecycle support"
  - example_simple: "Simple example service for testing"

**Location**: [services.js:40-77](netpalm-gui/static/js/services.js#L40-L77)

### 6. Updated Service States
Added support for all Netpalm service states with proper styling:

| State | Badge Color | Icon |
|-------|------------|------|
| active | Green (success) | Check circle |
| creating | Blue (info) | Spinning spinner |
| updating | Yellow (warning) | Spinning sync |
| deleting | Yellow (warning) | Trash icon |
| errored | Red (danger) | Exclamation triangle |

**Location**: [services.js:413-437](netpalm-gui/static/js/services.js#L413-L437)

## How to Use

### 1. Access Services Page
Navigate to **Services** in the main navigation

### 2. Create a VLAN Service Instance
1. Click **Create Instance** on the "Vlan Management" card
2. Fill in the form:
   - **Hostname** (required): Device IP or hostname
   - **VLAN ID** (required): 1-4094
   - **VLAN Name** (required): Alphanumeric name
   - **Device Type**: Select from dropdown (cisco_ios, cisco_xe, etc.)
   - **Username/Password**: Device credentials (defaults to "admin/admin")
   - **Description**: Optional VLAN description
   - **Interfaces**: Comma-separated list (e.g., `Gi1/0/1, Gi1/0/2`)
   - **VLAN Enabled**: True/False
   - **Timeout**: Connection timeout in seconds

3. Click **Create Service**

### 3. Manage Service Instance
Once created, you can:
- **View Details**: See service metadata and configuration
- **Validate**: Check if VLAN configuration matches intent
- **Health Check**: Verify VLAN is operational
- **Redeploy**: Fix configuration drift
- **Delete**: Remove VLAN from device

### 4. Access API Documentation
Click **API Docs** in the navigation to open Netpalm's Swagger UI in a new tab

## Service Schema Structure

The schema follows JSON Schema format:

```json
{
  "title": "ServiceName",
  "description": "Service description shown in UI",
  "type": "object",
  "required": ["field1", "field2"],
  "properties": {
    "field_name": {
      "type": "string|integer|boolean|array",
      "title": "Display Name",
      "description": "Help text shown under field",
      "default": "default_value",
      "enum": ["option1", "option2"],  // For dropdowns
      "minimum": 1,                     // For numbers
      "maximum": 100,                   // For numbers
      "minLength": 1,                   // For strings
      "maxLength": 32,                  // For strings
      "format": "password"              // For password fields
    }
  }
}
```

## Adding New Services

To add a new service to the UI:

1. **Create the service Python file** in `/netpalm/backend/plugins/extensibles/services/`
2. **Add schema to app.py** in the `service_schemas` dict (line 773)
3. **Add description to services.js** in the `descriptions` dict (line 45)

Example schema addition:

```python
# In app.py service_schemas dict
'my_service': {
    'title': 'MyServiceModel',
    'description': 'My service description',
    'type': 'object',
    'required': ['hostname'],
    'properties': {
        'hostname': {
            'type': 'string',
            'title': 'Device Hostname',
            'description': 'Target device hostname or IP'
        }
    }
}
```

## Technical Details

### Form Field Type Detection
The UI automatically detects field types from the schema and renders appropriate inputs:

1. Checks for `type: 'integer'` or `type: 'number'` → number input
2. Checks for `type: 'boolean'` → select (true/false)
3. Checks for `enum` array → select with options
4. Checks for `type: 'array'` → text input with comma-separated values
5. Checks for `format: 'password'` → password input
6. Defaults to text input

### Array Field Conversion
Array fields are handled specially:
- User enters: `value1, value2, value3`
- JavaScript splits on comma and trims whitespace
- Converts to: `["value1", "value2", "value3"]`
- Sends to API as proper JSON array

### Default Value Handling
Default values from schema are automatically applied:
- Number inputs: `value="${field.default}"`
- Select options: `selected` attribute on matching option
- Text inputs: `value="${field.default}"`
- Boolean selects: Pre-select true/false based on default

## Testing

To test the updated UI:

1. Navigate to http://localhost:8000/services
2. Click "Create Instance" on "Vlan Management"
3. Verify form shows all fields with descriptions
4. Fill in required fields (hostname, vlan_id, vlan_name)
5. Test array field: enter `Gi1/0/1, Gi1/0/2` in Interfaces
6. Click "Create Service"
7. Check service appears in instances table
8. Test lifecycle actions (validate, health check, etc.)

## Files Modified

1. `netpalm-gui/templates/base.html` - Fixed API docs link
2. `netpalm-gui/app.py` - Added service schemas
3. `netpalm-gui/static/js/services.js` - Enhanced form rendering and state handling
4. `netpalm/backend/plugins/extensibles/services/vlan_management.py` - Complete VLAN service example
5. `SERVICES_GUIDE.md` - Comprehensive service documentation
