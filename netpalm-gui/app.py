"""
Netpalm GUI - Web interface for netpalm network automation
"""
from flask import Flask, render_template, request, jsonify
import requests
import os
import logging
import json
import base64
from datetime import datetime
from netbox_client import NetboxClient

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'netpalm-gui-secret-key')

# Configuration
NETPALM_API_URL = os.environ.get('NETPALM_API_URL', 'http://netpalm-controller:9000')
NETPALM_API_KEY = os.environ.get('NETPALM_API_KEY', '2a84465a-cf38-46b2-9d86-b84Q7d57f288')
NETBOX_URL = os.environ.get('NETBOX_URL', 'https://netbox-prprd.gi-nw.viasat.io')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN', '')
VERIFY_SSL = os.environ.get('VERIFY_SSL', 'false').lower() == 'true'
TASK_HISTORY_FILE = os.environ.get('TASK_HISTORY_FILE', '/tmp/netpalm_gui_tasks.json')

# Initialize Netbox client
netbox = NetboxClient(NETBOX_URL, NETBOX_TOKEN, verify_ssl=VERIFY_SSL)

# Headers for netpalm API calls
NETPALM_HEADERS = {
    'x-api-key': NETPALM_API_KEY,
    'Content-Type': 'application/json'
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# Device list cache
device_cache = {
    'devices': None,
    'timestamp': None,
    'ttl': 300  # 5 minutes
}


# Task history management
def save_task_id(task_id, device_name=None):
    """Save a task ID to the history file with device name"""
    try:
        tasks = []
        if os.path.exists(TASK_HISTORY_FILE):
            with open(TASK_HISTORY_FILE, 'r') as f:
                tasks = json.load(f)

        # Add new task with timestamp and device name
        tasks.append({
            'task_id': task_id,
            'device_name': device_name,
            'created': datetime.utcnow().isoformat()
        })

        # Keep only last 500 tasks
        tasks = tasks[-500:]

        with open(TASK_HISTORY_FILE, 'w') as f:
            json.dump(tasks, f)
    except Exception as e:
        log.error(f"Error saving task ID: {e}")


def get_task_history():
    """Get all stored task IDs"""
    try:
        if os.path.exists(TASK_HISTORY_FILE):
            with open(TASK_HISTORY_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        log.error(f"Error reading task history: {e}")
        return []


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/deploy')
def deploy():
    """Config deployment page"""
    return render_template('deploy.html')


@app.route('/monitor')
def monitor():
    """Job monitoring page"""
    return render_template('monitor.html')


@app.route('/devices')
def devices():
    """Device list page"""
    return render_template('devices.html')


@app.route('/workers')
def workers():
    """Workers list page"""
    return render_template('workers.html')


@app.route('/templates')
def templates_page():
    """Templates management page"""
    return render_template('templates.html')


@app.route('/settings')
def settings_page():
    """Settings page"""
    return render_template('settings.html')


# API Endpoints for frontend

@app.route('/api/devices')
def get_devices():
    """Get device list from Netbox (with caching)"""
    try:
        # Check cache
        now = datetime.utcnow().timestamp()
        if (device_cache['devices'] is not None and
            device_cache['timestamp'] is not None and
            (now - device_cache['timestamp']) < device_cache['ttl']):
            log.info(f"Returning cached device list ({len(device_cache['devices'])} devices)")
            return jsonify({'success': True, 'devices': device_cache['devices'], 'cached': True})

        # Fetch fresh data
        log.info("Fetching fresh device list from Netbox...")
        devices = netbox.get_devices_with_details()

        # Update cache
        device_cache['devices'] = devices
        device_cache['timestamp'] = now

        log.info(f"Cached {len(devices)} devices")
        return jsonify({'success': True, 'devices': devices, 'cached': False})
    except Exception as e:
        log.error(f"Error fetching devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device-names')
def get_device_names():
    """Get simple list of device names"""
    try:
        names = netbox.get_device_names()
        return jsonify({'success': True, 'names': names})
    except Exception as e:
        log.error(f"Error fetching device names: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device/<device_name>/connection-info')
def get_device_connection_info(device_name):
    """Get device connection information including netmiko device_type"""
    try:
        device = netbox.get_device_by_name(device_name)
        if not device:
            return jsonify({'success': False, 'error': 'Device not found'}), 404

        # Get platform from config_context.nornir.platform (preferred)
        nornir_platform = device.get('config_context', {}).get('nornir', {}).get('platform')

        # Fallback to netbox platform if nornir platform not set
        if not nornir_platform:
            platform = device.get('platform', {})
            manufacturer = device.get('device_type', {}).get('manufacturer', {})
            platform_name = platform.get('name') if isinstance(platform, dict) else None
            manufacturer_name = manufacturer.get('name') if isinstance(manufacturer, dict) else None

            from netbox_client import get_netmiko_device_type
            nornir_platform = get_netmiko_device_type(platform_name, manufacturer_name)

        # Get IP address
        primary_ip = device.get('primary_ip', {}) or device.get('primary_ip4', {})
        ip_address = None
        if primary_ip:
            ip_addr_full = primary_ip.get('address', '')
            # Remove CIDR notation if present
            ip_address = ip_addr_full.split('/')[0] if ip_addr_full else None

        return jsonify({
            'success': True,
            'device_name': device_name,
            'device_type': nornir_platform,  # This is the netmiko device_type
            'ip_address': ip_address
        })
    except Exception as e:
        log.error(f"Error fetching device connection info for {device_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tasks')
def get_tasks():
    """Get all tasks - combines queue and history"""
    try:
        # Get currently queued tasks from netpalm
        response = requests.get(f'{NETPALM_API_URL}/taskqueue/', headers=NETPALM_HEADERS, timeout=5)
        response.raise_for_status()
        queued_data = response.json()

        # Get task history from our local store
        history = get_task_history()

        # Combine - start with queued tasks
        all_task_ids = queued_data.get('data', {}).get('task_id', [])

        # Add historical tasks (most recent first)
        for item in reversed(history):
            task_id = item['task_id']
            if task_id not in all_task_ids:
                all_task_ids.insert(0, task_id)

        # Return in same format as netpalm
        return jsonify({
            'status': 'success',
            'data': {
                'task_id': all_task_ids[:100]  # Limit to 100 most recent
            }
        })
    except Exception as e:
        log.error(f"Error fetching tasks: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/metadata')
def get_tasks_metadata():
    """Get task metadata including device names from history"""
    try:
        # Get task history from our local store
        history = get_task_history()

        # Build metadata map: task_id -> device_name
        metadata = {}
        for item in history:
            task_id = item.get('task_id')
            device_name = item.get('device_name')
            if task_id:
                metadata[task_id] = {
                    'device_name': device_name,
                    'created': item.get('created')
                }

        return jsonify({
            'success': True,
            'metadata': metadata
        })
    except Exception as e:
        log.error(f"Error fetching task metadata: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/task/<task_id>')
def get_task(task_id):
    """Get specific task details"""
    try:
        response = requests.get(f'{NETPALM_API_URL}/task/{task_id}', headers=NETPALM_HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        log.error(f"Error fetching task {task_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/workers')
def get_workers():
    """Get all workers from netpalm"""
    try:
        response = requests.get(f'{NETPALM_API_URL}/workers/', headers=NETPALM_HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        log.error(f"Error fetching workers: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/deploy/getconfig', methods=['POST'])
def deploy_getconfig():
    """Deploy getconfig to device"""
    try:
        data = request.json

        # Extract device name if provided
        device_name = data.get('device_name')

        # Forward request to netpalm
        library = data.get('library', 'netmiko')
        endpoint = f'/getconfig/{library}' if library != 'auto' else '/getconfig'

        response = requests.post(
            f'{NETPALM_API_URL}{endpoint}',
            json=data.get('payload'),
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # Save task ID to history with device name
        if result.get('status') == 'success' and result.get('data', {}).get('task_id'):
            save_task_id(result['data']['task_id'], device_name)

        return jsonify(result)
    except Exception as e:
        log.error(f"Error deploying getconfig: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/deploy/setconfig', methods=['POST'])
def deploy_setconfig():
    """Deploy setconfig to device"""
    try:
        data = request.json

        # Extract device name if provided
        device_name = data.get('device_name')

        # Forward request to netpalm
        library = data.get('library', 'netmiko')
        endpoint = f'/setconfig/{library}' if library != 'auto' else '/setconfig'

        response = requests.post(
            f'{NETPALM_API_URL}{endpoint}',
            json=data.get('payload'),
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # Save task ID to history with device name
        if result.get('status') == 'success' and result.get('data', {}).get('task_id'):
            save_task_id(result['data']['task_id'], device_name)

        return jsonify(result)
    except Exception as e:
        log.error(f"Error deploying setconfig: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/deploy/setconfig/dry-run', methods=['POST'])
def deploy_setconfig_dryrun():
    """Deploy setconfig dry-run to device"""
    try:
        data = request.json

        response = requests.post(
            f'{NETPALM_API_URL}/setconfig/dry-run',
            json=data.get('payload'),
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        log.error(f"Error deploying dry-run: {e}")
        return jsonify({'error': str(e)}), 500


# Template Management API Endpoints

@app.route('/api/templates')
def get_templates():
    """List all J2 config templates"""
    try:
        response = requests.get(
            f'{NETPALM_API_URL}/j2template/config/',
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Extract template list from response
        templates = result.get('data', {}).get('task_result', {}).get('templates', [])

        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        log.error(f"Error fetching templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates/<template_name>')
def get_template(template_name):
    """Get specific J2 template content"""
    try:
        response = requests.get(
            f'{NETPALM_API_URL}/j2template/config/{template_name}',
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Extract base64 template content and decode
        template_data = result.get('data', {}).get('task_result', {})
        base64_content = template_data.get('base64_payload') or template_data.get('template')

        if base64_content:
            # Decode from base64
            decoded_content = base64.b64decode(base64_content).decode('utf-8')
            return jsonify({'success': True, 'content': decoded_content})
        else:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

    except Exception as e:
        log.error(f"Error fetching template {template_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates', methods=['POST'])
def create_template():
    """Create/update J2 template"""
    try:
        data = request.json
        template_name = data.get('name')
        base64_payload = data.get('base64_payload')

        if not template_name or not base64_payload:
            return jsonify({'success': False, 'error': 'Missing name or base64_payload'}), 400

        payload = {
            'name': template_name,
            'base64_payload': base64_payload
        }

        response = requests.post(
            f'{NETPALM_API_URL}/j2template/config/',
            json=payload,
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Check if netpalm returned success
        if result.get('status') == 'success':
            return jsonify({'success': True, 'message': 'Template saved successfully'})
        else:
            error_msg = result.get('data', {}).get('task_result', {}).get('error', 'Unknown error')
            return jsonify({'success': False, 'error': error_msg}), 500
    except Exception as e:
        log.error(f"Error creating template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates', methods=['DELETE'])
def delete_template():
    """Delete J2 template"""
    try:
        data = request.json
        template_name = data.get('name')

        if not template_name:
            return jsonify({'success': False, 'error': 'Missing template name'}), 400

        payload = {'name': template_name}

        response = requests.delete(
            f'{NETPALM_API_URL}/j2template/config/',
            json=payload,
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()

        return jsonify({'success': True, 'message': 'Template deleted successfully'})
    except Exception as e:
        log.error(f"Error deleting template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates/<template_name>/variables')
def get_template_variables(template_name):
    """Extract variables from J2 template"""
    try:
        # Get template content
        response = requests.get(
            f'{NETPALM_API_URL}/j2template/config/{template_name}',
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        template_data = result.get('data', {}).get('task_result', {})
        base64_content = template_data.get('base64_payload') or template_data.get('template')

        if not base64_content:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        # Decode template
        template_content = base64.b64decode(base64_content).decode('utf-8')

        # Extract variables using regex
        import re
        # Match {{ variable_name }} patterns
        variable_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        variables = list(set(re.findall(variable_pattern, template_content)))
        variables.sort()

        return jsonify({'success': True, 'variables': variables, 'template_content': template_content})
    except Exception as e:
        log.error(f"Error extracting template variables: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates/render', methods=['POST'])
def render_j2_template():
    """Render J2 template with provided variables"""
    try:
        data = request.json
        template_name = data.get('template_name')
        variables = data.get('variables', {})

        if not template_name:
            return jsonify({'success': False, 'error': 'Missing template name'}), 400

        # Call netpalm's template render API
        payload = {
            'template_name': template_name,
            'args': variables
        }

        response = requests.post(
            f'{NETPALM_API_URL}/j2template/render/config/{template_name}',
            json=payload,
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Extract rendered configuration from response
        task_result = result.get('data', {}).get('task_result', {})
        rendered_config = task_result.get('template_render_result', '') or task_result.get('rendered_config', '')

        if not rendered_config:
            return jsonify({'success': False, 'error': 'No rendered configuration returned from template'}), 500

        return jsonify({'success': True, 'rendered_config': rendered_config})
    except Exception as e:
        log.error(f"Error rendering template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8088, debug=True)
