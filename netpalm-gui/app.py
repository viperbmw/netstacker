"""
Netpalm GUI - Web interface for netpalm network automation
"""
from flask import Flask, render_template, request, jsonify, redirect
import requests
import os
import logging
import json
import base64
import uuid
import time
from datetime import datetime
from netbox_client import NetboxClient
import redis
from jinja2 import Template, TemplateSyntaxError

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'netpalm-gui-secret-key')

# Configuration
NETPALM_API_URL = os.environ.get('NETPALM_API_URL', 'http://netpalm-controller:9000')
NETPALM_API_KEY = os.environ.get('NETPALM_API_KEY', '2a84465a-cf38-46b2-9d86-b84Q7d57f288')
NETBOX_URL = os.environ.get('NETBOX_URL', 'https://netbox-prprd.gi-nw.viasat.io')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN', '')
VERIFY_SSL = os.environ.get('VERIFY_SSL', 'false').lower() == 'true'
TASK_HISTORY_FILE = os.environ.get('TASK_HISTORY_FILE', '/tmp/netpalm_gui_tasks.json')
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', 'Red1zp4ww0rd_')
TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR', '/templates')

# Setup logging first
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Headers for netpalm API calls
NETPALM_HEADERS = {
    'x-api-key': NETPALM_API_KEY,
    'Content-Type': 'application/json'
}

# Initialize Netbox client
netbox = NetboxClient(NETBOX_URL, NETBOX_TOKEN, verify_ssl=VERIFY_SSL)

# Initialize Redis client for service storage with SSL
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        ssl=True,
        ssl_cert_reqs=None  # Don't verify cert (since it's self-signed)
    )
    redis_client.ping()
    log.info("Connected to Redis for service storage")
except Exception as e:
    log.warning(f"Could not connect to Redis: {e}. Service storage will be unavailable.")
    redis_client = None


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


# ============================================================================
# Template Metadata Storage Functions (Redis-based)
# ============================================================================

def save_template_metadata(template_name, metadata):
    """Save template metadata to Redis"""
    if not redis_client:
        raise Exception("Redis not available")

    # Store metadata with key format: gui_template_meta:<template_name>
    redis_key = f"gui_template_meta:{template_name}"
    redis_client.set(redis_key, json.dumps(metadata))
    log.info(f"Saved template metadata: {template_name}")
    return True


def get_template_metadata(template_name):
    """Get template metadata from Redis"""
    if not redis_client:
        return None

    redis_key = f"gui_template_meta:{template_name}"
    data = redis_client.get(redis_key)

    if data:
        return json.loads(data)
    return None


def get_all_template_metadata():
    """Get all template metadata from Redis"""
    if not redis_client:
        return {}

    metadata_dict = {}
    for key in redis_client.scan_iter("gui_template_meta:*"):
        template_name = key.replace("gui_template_meta:", "")
        data = redis_client.get(key)
        if data:
            try:
                metadata_dict[template_name] = json.loads(data)
            except json.JSONDecodeError:
                log.error(f"Error decoding metadata for template: {template_name}")

    return metadata_dict


# ============================================================================
# Service Storage Functions (Redis-based)
# ============================================================================

def save_service_instance(service_data):
    """Save a service instance to Redis"""
    if not redis_client:
        raise Exception("Redis not available")

    service_id = service_data.get('service_id', str(uuid.uuid4()))
    service_data['service_id'] = service_id
    service_data['updated_at'] = datetime.utcnow().isoformat()

    if 'created_at' not in service_data:
        service_data['created_at'] = service_data['updated_at']

    # Store in Redis with key format: gui_service:<service_id>
    redis_key = f"gui_service:{service_id}"
    redis_client.set(redis_key, json.dumps(service_data))

    log.info(f"Saved service instance: {service_id}")
    return service_id


def get_service_instance(service_id):
    """Get a service instance from Redis"""
    if not redis_client:
        return None

    redis_key = f"gui_service:{service_id}"
    data = redis_client.get(redis_key)

    if data:
        return json.loads(data)
    return None


def get_all_service_instances():
    """Get all service instances from Redis"""
    if not redis_client:
        return []

    instances = []
    for key in redis_client.scan_iter("gui_service:*"):
        data = redis_client.get(key)
        if data:
            try:
                instances.append(json.loads(data))
            except json.JSONDecodeError:
                log.error(f"Failed to parse service data for key: {key}")

    # Sort by created_at (newest first)
    instances.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return instances


def delete_service_instance(service_id):
    """Delete a service instance from Redis"""
    if not redis_client:
        return False

    redis_key = f"gui_service:{service_id}"
    result = redis_client.delete(redis_key)
    log.info(f"Deleted service instance: {service_id}")
    return result > 0


def update_service_state(service_id, state):
    """Update the state of a service instance"""
    service = get_service_instance(service_id)
    if service:
        service['state'] = state
        service['updated_at'] = datetime.utcnow().isoformat()
        save_service_instance(service)
        return True
    return False


# Service Stack storage functions
def save_service_stack(stack_data):
    """Save a service stack to Redis"""
    if not redis_client:
        raise Exception("Redis not available")

    stack_id = stack_data.get('stack_id', str(uuid.uuid4()))
    stack_data['stack_id'] = stack_id
    stack_data['updated_at'] = datetime.utcnow().isoformat()

    if 'created_at' not in stack_data:
        stack_data['created_at'] = stack_data['updated_at']

    redis_key = f"gui_service_stack:{stack_id}"
    redis_client.set(redis_key, json.dumps(stack_data))

    log.info(f"Saved service stack: {stack_id}")
    return stack_id


def get_service_stack(stack_id):
    """Get a service stack from Redis"""
    if not redis_client:
        return None

    redis_key = f"gui_service_stack:{stack_id}"
    data = redis_client.get(redis_key)

    if data:
        return json.loads(data)
    return None


def get_all_service_stacks():
    """Get all service stacks from Redis"""
    if not redis_client:
        return []

    stacks = []
    for key in redis_client.scan_iter("gui_service_stack:*"):
        data = redis_client.get(key)
        if data:
            try:
                stacks.append(json.loads(data))
            except json.JSONDecodeError:
                log.error(f"Failed to parse service stack data for key: {key}")

    stacks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return stacks


def delete_service_stack(stack_id):
    """Delete a service stack from Redis"""
    if not redis_client:
        return False

    redis_key = f"gui_service_stack:{stack_id}"
    result = redis_client.delete(redis_key)
    log.info(f"Deleted service stack: {stack_id}")
    return result > 0


def render_j2_template(template_name, variables):
    """Render a Jinja2 template using Netpalm's template system"""
    try:
        # Call Netpalm's j2template render endpoint
        response = requests.post(
            f'{NETPALM_API_URL}/j2template/render/config/{template_name}',
            json=variables,
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Extract rendered config from response
        task_result = result.get('data', {}).get('task_result', {})
        rendered = task_result.get('template_render_result', '') if isinstance(task_result, dict) else task_result

        return rendered

    except Exception as e:
        log.error(f"Error rendering template {template_name}: {e}")
        return None


def render_template_locally(template_name, variables):
    """Render a Jinja2 template locally instead of using Netpalm's broken renderer"""
    try:
        # Build template path
        template_file = os.path.join(TEMPLATE_DIR, f"{template_name}.j2")

        # Check if template file exists
        if not os.path.exists(template_file):
            log.error(f"Template file not found: {template_file}")
            return None

        # Read template content
        with open(template_file, 'r') as f:
            template_content = f.read()

        # Render template with Jinja2
        template = Template(template_content)
        rendered = template.render(**variables)

        log.info(f"Successfully rendered template '{template_name}' locally")
        return rendered

    except TemplateSyntaxError as e:
        log.error(f"Template syntax error in '{template_name}': {e}")
        return None
    except Exception as e:
        log.error(f"Error rendering template '{template_name}' locally: {e}")
        return None


def get_device_connection_info(device_name, credential_override=None):
    """Get device connection info from Netbox"""
    try:
        # Get device from Netbox
        device = netbox.get_device_by_name(device_name)
        if not device or not device.get('name'):
            log.error(f"Device {device_name} not found in Netbox")
            return None

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
        host = None
        if primary_ip:
            ip_addr_full = primary_ip.get('address', '')
            # Remove CIDR notation if present
            host = ip_addr_full.split('/')[0] if ip_addr_full else None

        # Fallback to device name if no IP
        if not host:
            host = device_name

        # Build connection args
        connection_args = {
            'device_type': nornir_platform or 'cisco_ios',  # Default to cisco_ios
            'host': host,
            'timeout': 30
        }

        # Add credentials from override if provided
        if credential_override:
            connection_args['username'] = credential_override.get('username')
            connection_args['password'] = credential_override.get('password')
            log.info(f"Applied credential override for device {device_name} (username: {credential_override.get('username')})")

        platform_info = device.get('platform', {})
        platform_name = platform_info.get('name') if isinstance(platform_info, dict) else ''

        return {
            'connection_args': connection_args,
            'device_info': {
                'name': device.get('name'),
                'platform': platform_name,
                'site': device.get('site', {}).get('name') if device.get('site') else None
            }
        }

    except Exception as e:
        log.error(f"Error getting device connection info for {device_name}: {e}", exc_info=True)
        return None


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


@app.route('/api-docs')
def api_docs():
    """Redirect to Netpalm API documentation using current host"""
    # Use the current request host but with port 9000 for Netpalm
    host = request.host.rsplit(':', 1)[0]  # Remove port if present
    return redirect(f'http://{host}:9000/', code=302)


# API Endpoints for frontend

@app.route('/api/devices', methods=['GET', 'POST'])
def get_devices():
    """Get device list from Netbox (with caching and optional filters)"""
    try:
        # Get filters from request if provided (POST body or query params)
        filters = []
        if request.method == 'POST' and request.json:
            filter_list = request.json.get('filters', [])
            # Keep as list to support multiple values for same key
            for f in filter_list:
                if 'key' in f and 'value' in f:
                    filters.append({'key': f['key'], 'value': f['value']})

        # Create cache key based on filters
        cache_key = json.dumps(filters, sort_keys=True) if filters else 'default'

        # Check cache (with filter-specific key)
        now = datetime.utcnow().timestamp()
        cache_entry = device_cache.get(cache_key, {})
        if (cache_entry.get('devices') is not None and
            cache_entry.get('timestamp') is not None and
            (now - cache_entry['timestamp']) < device_cache.get('ttl', 300)):
            log.info(f"Returning cached device list ({len(cache_entry['devices'])} devices) with filters: {filters}")
            return jsonify({'success': True, 'devices': cache_entry['devices'], 'cached': True})

        # Fetch fresh data with filters
        log.info(f"Fetching fresh device list from Netbox with filters: {filters}...")
        devices = netbox.get_devices_with_details(filters=filters)

        # Update cache with filter-specific key
        device_cache[cache_key] = {
            'devices': devices,
            'timestamp': now
        }

        log.info(f"Cached {len(devices)} devices with filters: {filters}")
        return jsonify({'success': True, 'devices': devices, 'cached': False})
    except Exception as e:
        log.error(f"Error fetching devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/devices/clear-cache', methods=['POST'])
def clear_device_cache():
    """Clear the device cache"""
    try:
        global device_cache
        device_cache.clear()
        device_cache['ttl'] = 300  # Restore TTL
        log.info("Device cache cleared")
        return jsonify({'success': True, 'message': 'Cache cleared successfully'})
    except Exception as e:
        log.error(f"Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test-netbox', methods=['POST'])
def test_netbox_connection():
    """Test Netbox API connection with provided credentials"""
    try:
        import time
        from netbox_client import NetboxClient

        data = request.json
        netbox_url = data.get('netbox_url', '').strip()
        netbox_token = data.get('netbox_token', '').strip()
        verify_ssl = data.get('verify_ssl', False)
        filter_list = data.get('filters', [])

        if not netbox_url:
            return jsonify({'success': False, 'error': 'Netbox URL is required'}), 400

        # Keep filters as list to support multiple values for same key
        filters = []
        for f in filter_list:
            if 'key' in f and 'value' in f:
                filters.append({'key': f['key'], 'value': f['value']})

        # Build the test URL that will be called
        test_url = f"{netbox_url.rstrip('/')}/api/dcim/devices/?limit=3000"
        if filters:
            filter_params = '&'.join([f"{f['key']}={f['value']}" for f in filters])
            test_url += '&' + filter_params

        # Log the full request details
        log.info(f"Testing Netbox connection to: {test_url}")
        log.info(f"SSL Verification: {verify_ssl}")
        log.info(f"Using token: {'Yes' if netbox_token else 'No'}")
        if filters:
            log.info(f"Applying filters: {filters}")

        # Create a test client
        test_client = NetboxClient(netbox_url, netbox_token, verify_ssl)

        # Measure response time
        start_time = time.time()

        # Try to fetch devices with filters
        devices = test_client.get_devices(brief=False, limit=3000, filters=filters)

        end_time = time.time()
        response_time = f"{(end_time - start_time):.2f}s"

        if devices is not None:
            # Get total count
            device_count = len(devices)

            return jsonify({
                'success': True,
                'device_count': device_count,
                'response_time': response_time,
                'message': 'Successfully connected to Netbox',
                'api_url': test_url,
                'verify_ssl': verify_ssl,
                'has_token': bool(netbox_token)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch devices from Netbox',
                'api_url': test_url
            }), 500

    except requests.exceptions.SSLError as e:
        log.error(f"SSL Error testing Netbox: {e}")
        return jsonify({
            'success': False,
            'error': f'SSL certificate verification failed. Try disabling "Verify SSL certificates" if using self-signed certificates.',
            'api_url': test_url if 'test_url' in locals() else 'N/A',
            'details': str(e)
        }), 500
    except requests.exceptions.ConnectionError as e:
        log.error(f"Connection Error testing Netbox: {e}")
        return jsonify({
            'success': False,
            'error': f'Could not connect to Netbox. Check the URL and network connectivity.',
            'api_url': test_url if 'test_url' in locals() else 'N/A',
            'details': str(e)
        }), 500
    except requests.exceptions.Timeout as e:
        log.error(f"Timeout testing Netbox: {e}")
        return jsonify({
            'success': False,
            'error': 'Connection timed out after 30 seconds. Netbox may be slow or unreachable.',
            'api_url': test_url if 'test_url' in locals() else 'N/A',
            'details': str(e)
        }), 500
    except requests.exceptions.HTTPError as e:
        log.error(f"HTTP Error testing Netbox: {e}")
        status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
        if status_code == 403:
            return jsonify({
                'success': False,
                'error': 'Authentication failed. Check your API token.',
                'api_url': test_url if 'test_url' in locals() else 'N/A',
                'status_code': status_code,
                'details': str(e)
            }), 500
        elif status_code == 404:
            return jsonify({
                'success': False,
                'error': 'API endpoint not found. Check your Netbox URL.',
                'api_url': test_url if 'test_url' in locals() else 'N/A',
                'status_code': status_code,
                'details': str(e)
            }), 500
        else:
            return jsonify({
                'success': False,
                'error': f'HTTP error {status_code}: {str(e)}',
                'api_url': test_url if 'test_url' in locals() else 'N/A',
                'status_code': status_code,
                'details': str(e)
            }), 500
    except Exception as e:
        log.error(f"Error testing Netbox connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'api_url': test_url if 'test_url' in locals() else 'N/A',
            'details': str(e)
        }), 500


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
def api_get_device_connection_info(device_name):
    """API endpoint: Get device connection information including netmiko device_type"""
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
    """Get all tasks - combines queue and history, sorted by creation time (newest first)"""
    try:
        # Get currently queued tasks from netpalm
        response = requests.get(f'{NETPALM_API_URL}/taskqueue/', headers=NETPALM_HEADERS, timeout=5)
        response.raise_for_status()
        queued_data = response.json()

        # Get task history from our local store
        history = get_task_history()

        # Build map of task_id to creation time
        task_times = {}
        for item in history:
            task_id = item.get('task_id')
            created = item.get('created', '1970-01-01T00:00:00')
            if task_id:
                task_times[task_id] = created

        # Get all unique task IDs
        all_task_ids = list(set(queued_data.get('data', {}).get('task_id', [])))

        # Add historical tasks not in queue
        for item in history:
            task_id = item['task_id']
            if task_id not in all_task_ids:
                all_task_ids.append(task_id)

        # Sort by creation time (newest first)
        sorted_tasks = sorted(
            all_task_ids,
            key=lambda tid: task_times.get(tid, '9999-99-99T99:99:99'),
            reverse=True
        )

        # Return in same format as netpalm
        return jsonify({
            'status': 'success',
            'data': {
                'task_id': sorted_tasks[:100]  # Limit to 100 most recent
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
    """List all J2 config templates with metadata"""
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

        # Get all template metadata
        all_metadata = get_all_template_metadata()

        # Enhance template list with metadata
        enhanced_templates = []
        for template_name in templates:
            # Strip .j2 extension for lookup
            lookup_name = template_name[:-3] if template_name.endswith('.j2') else template_name

            metadata = all_metadata.get(lookup_name, {})
            enhanced_templates.append({
                'name': template_name,
                'validation_template': metadata.get('validation_template'),
                'delete_template': metadata.get('delete_template'),
                'description': metadata.get('description')
            })

        return jsonify({'success': True, 'templates': enhanced_templates})
    except Exception as e:
        log.error(f"Error fetching templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/templates/<template_name>')
def get_template(template_name):
    """Get specific J2 template content"""
    try:
        # Strip .j2 extension if present (Netpalm adds it automatically)
        if template_name.endswith('.j2'):
            template_name_without_ext = template_name[:-3]
        else:
            template_name_without_ext = template_name

        response = requests.get(
            f'{NETPALM_API_URL}/j2template/config/{template_name_without_ext}',
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

        # Ensure template name doesn't have .j2 extension (Netpalm adds it automatically)
        if template_name.endswith('.j2'):
            template_name = template_name[:-3]

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


@app.route('/api/templates/<template_name>/metadata', methods=['PUT'])
def update_template_metadata(template_name):
    """Update template metadata (validation and delete templates)"""
    try:
        data = request.json

        # Strip .j2 extension for consistency
        if template_name.endswith('.j2'):
            template_name = template_name[:-3]

        metadata = {
            'validation_template': data.get('validation_template'),
            'delete_template': data.get('delete_template'),
            'description': data.get('description'),
            'updated_at': datetime.utcnow().isoformat()
        }

        save_template_metadata(template_name, metadata)

        return jsonify({'success': True, 'message': 'Template metadata updated successfully'})
    except Exception as e:
        log.error(f"Error updating template metadata: {e}")
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
        # Strip .j2 extension if present (Netpalm adds it automatically)
        if template_name.endswith('.j2'):
            template_name_without_ext = template_name[:-3]
        else:
            template_name_without_ext = template_name

        # Get template content
        response = requests.get(
            f'{NETPALM_API_URL}/j2template/config/{template_name_without_ext}',
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
def api_render_j2_template():
    """API endpoint: Render J2 template with provided variables"""
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


# Services routes
@app.route('/services')
def services_page():
    """Render services management page"""
    return render_template('services.html')


@app.route('/service-stacks')
def service_stacks_page():
    """Render service stacks management page"""
    return render_template('service-stacks.html')


@app.route('/api/services/templates')
def get_service_templates():
    """List all available service templates using helper script"""
    try:
        # Use custom script to list service templates
        payload = {
            "script": "list_service_templates",
            "args": {}
        }

        response = requests.post(
            f'{NETPALM_API_URL}/script',
            json=payload,
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()

        # Get the task_id and retrieve the result
        task_id = result.get('data', {}).get('task_id')
        if task_id:
            import time
            time.sleep(0.5)  # Brief wait for task to complete

            task_response = requests.get(
                f'{NETPALM_API_URL}/task/{task_id}',
                headers=NETPALM_HEADERS,
                timeout=10
            )
            task_response.raise_for_status()
            task_result = task_response.json()

            script_result = task_result.get('data', {}).get('task_result', {})
            templates = script_result.get('templates', [])

            return jsonify({'success': True, 'templates': templates})

        # Fallback to empty list
        return jsonify({'success': True, 'templates': []})
    except Exception as e:
        log.error(f"Error fetching service templates: {e}")
        # Return empty list as fallback
        return jsonify({'success': True, 'templates': []})


@app.route('/api/services/templates/<template_name>/schema')
def get_service_template_schema(template_name):
    """Get the Pydantic model schema for a service template

    Note: This endpoint is maintained for backward compatibility.
    The template-based system now uses dynamic template variable extraction
    instead of hardcoded schemas.
    """

    # Empty schemas dictionary - using template-based system now
    service_schemas = {}

    # Check if we have a hardcoded schema (none currently)
    if template_name in service_schemas:
        return jsonify({'success': True, 'schema': service_schemas[template_name]})

    try:
        # Try to get the schema from netpalm (if it provides one)
        response = requests.get(
            f'{NETPALM_API_URL}/service/schema/{template_name}',
            headers=NETPALM_HEADERS,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            schema = result.get('data', {}).get('task_result', {})
            return jsonify({'success': True, 'schema': schema})
        else:
            # Return empty schema if not available
            return jsonify({'success': True, 'schema': None})
    except Exception as e:
        log.error(f"Error fetching service schema: {e}")
        return jsonify({'success': True, 'schema': None})


@app.route('/api/services/instances')
def get_service_instances():
    """List all template-based service instances from GUI Redis storage"""
    try:
        instances = get_all_service_instances()
        return jsonify({'success': True, 'instances': instances})
    except Exception as e:
        log.error(f"Error fetching service instances: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/<service_id>')
def get_service_instance_endpoint(service_id):
    """Get details of a specific template-based service instance"""
    try:
        instance = get_service_instance(service_id)  # Call the storage function
        if instance:
            return jsonify({'success': True, 'instance': instance})
        else:
            return jsonify({'success': False, 'error': 'Service not found'}), 404
    except Exception as e:
        log.error(f"Error fetching service instance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/create', methods=['POST'])
def create_template_service():
    """Create a new template-based service instance

    Expected JSON payload:
    {
        "name": "My VLAN Service",
        "template": "vlan_config.j2",
        "reverse_template": "vlan_remove.j2",  // optional
        "variables": {"vlan_id": 100, "vlan_name": "Guest"},
        "device": "switch1",  // single device for now
        "username": "admin",  // optional - from settings if not provided
        "password": "secret"  // optional - from settings if not provided
    }
    """
    try:
        data = request.json
        log.info(f"Creating template service with data: {data}")

        # Extract required fields
        service_name = data.get('name')
        template = data.get('template')
        variables = data.get('variables', {})
        device = data.get('device')

        if not all([service_name, template, device]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: name, template, device'
            }), 400

        # Get credentials
        username = data.get('username')
        password = data.get('password')

        # Get device connection info
        credential_override = None
        if username and password:
            credential_override = {'username': username, 'password': password}

        device_info = get_device_connection_info(device, credential_override)
        if not device_info:
            return jsonify({
                'success': False,
                'error': f'Could not get connection info for device: {device}'
            }), 400

        # Add credentials to connection_args if provided
        if username and password:
            device_info['connection_args']['username'] = username
            device_info['connection_args']['password'] = password

        # Get template metadata (validation and delete templates)
        template_lookup = template[:-3] if template.endswith('.j2') else template
        template_metadata = get_template_metadata(template_lookup) or {}

        # Render template
        rendered_config = render_j2_template(template, variables)
        if not rendered_config:
            return jsonify({
                'success': False,
                'error': f'Failed to render template: {template}'
            }), 500

        # Push config to device using setconfig
        setconfig_payload = {
            'library': 'netmiko',
            'connection_args': device_info['connection_args'],
            'config': rendered_config.split('\n'),
            'queue_strategy': 'fifo'
        }

        response = requests.post(
            f'{NETPALM_API_URL}/setconfig',
            json=setconfig_payload,
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        task_id = result.get('data', {}).get('task_id')
        if task_id:
            save_task_id(task_id, device_name=f"service:{service_name}")

        # Create service instance
        service_data = {
            'name': service_name,
            'template': template,
            'reverse_template': data.get('reverse_template') or template_metadata.get('delete_template'),
            'validation_template': template_metadata.get('validation_template'),
            'delete_template': template_metadata.get('delete_template'),
            'variables': variables,
            'device': device,
            'state': 'deploying',
            'rendered_config': rendered_config,
            'task_id': task_id
        }

        service_id = save_service_instance(service_data)

        return jsonify({
            'success': True,
            'service_id': service_id,
            'task_id': task_id,
            'message': f'Service "{service_name}" created and deploying to {device}'
        })

    except Exception as e:
        log.error(f"Error creating template service: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/<service_id>/healthcheck', methods=['POST'])
def health_check_service_instance(service_id):
    """Health check a service instance"""
    try:
        response = requests.post(
            f'{NETPALM_API_URL}/service/instance/healthcheck/{service_id}',
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        task_id = result.get('data', {}).get('task_id')
        if task_id:
            save_task_id(task_id, device_name=f"service_healthcheck:{service_id}")

        return jsonify({'success': True, 'task_id': task_id, 'result': result.get('data', {})})
    except Exception as e:
        log.error(f"Error health checking service instance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/<service_id>/redeploy', methods=['POST'])
def redeploy_service_instance(service_id):
    """Redeploy a service instance"""
    try:
        response = requests.post(
            f'{NETPALM_API_URL}/service/instance/redeploy/{service_id}',
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        task_id = result.get('data', {}).get('task_id')
        if task_id:
            save_task_id(task_id, device_name=f"service_redeploy:{service_id}")

        return jsonify({'success': True, 'task_id': task_id, 'result': result.get('data', {})})
    except Exception as e:
        log.error(f"Error redeploying service instance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/<service_id>/delete', methods=['POST'])
def delete_template_service(service_id):
    """Delete a template-based service instance - removes config from device first"""
    try:
        # Get service instance
        service = get_service_instance(service_id)
        if not service:
            return jsonify({'success': False, 'error': 'Service not found'}), 404

        # Get credentials from request if provided
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')

        task_id = None
        delete_template = service.get('delete_template') or service.get('reverse_template')

        # If delete template exists, use it to remove config from device
        if delete_template:
            log.info(f"Using delete template '{delete_template}' to remove service from device")

            # Get device connection info
            credential_override = None
            if username and password:
                credential_override = {'username': username, 'password': password}

            device_info = get_device_connection_info(service['device'], credential_override)
            if not device_info:
                return jsonify({
                    'success': False,
                    'error': f'Could not get connection info for device: {service["device"]}'
                }), 400

            # Add credentials
            if username and password:
                device_info['connection_args']['username'] = username
                device_info['connection_args']['password'] = password

            # Render delete template using local rendering
            template_name = delete_template[:-3] if delete_template.endswith('.j2') else delete_template
            rendered_config = render_template_locally(template_name, service.get('variables', {}))

            if not rendered_config:
                return jsonify({
                    'success': False,
                    'error': f'Failed to render delete template: {delete_template}'
                }), 500

            log.info(f"Rendered delete config: {rendered_config[:200]}...")

            # Push delete config to device
            setconfig_payload = {
                'library': 'netmiko',
                'connection_args': device_info['connection_args'],
                'config': rendered_config.split('\n'),
                'queue_strategy': 'fifo'
            }

            response = requests.post(
                f'{NETPALM_API_URL}/setconfig',
                json=setconfig_payload,
                headers=NETPALM_HEADERS,
                timeout=60
            )

            if response.status_code != 201:
                return jsonify({
                    'success': False,
                    'error': f'Failed to execute delete on device: {response.text}'
                }), 500

            result = response.json()
            task_id = result.get('data', {}).get('task_id')

            if task_id:
                save_task_id(task_id, device_name=f"service_delete:{service_id}")

            # Wait for deletion task to complete
            log.info(f"Waiting for deletion task {task_id} to complete...")
            max_wait = 60
            waited = 0
            while waited < max_wait:
                time.sleep(2)
                waited += 2

                task_response = requests.get(
                    f'{NETPALM_API_URL}/task/{task_id}',
                    headers=NETPALM_HEADERS,
                    timeout=10
                )
                task_data = task_response.json()
                task_status = task_data.get('data', {}).get('task_status')

                if task_status == 'finished':
                    log.info(f"Delete task completed successfully")
                    break
                elif task_status == 'failed':
                    task_errors = task_data.get('data', {}).get('task_errors', [])
                    return jsonify({
                        'success': False,
                        'error': f'Delete task failed: {task_errors}',
                        'task_id': task_id
                    }), 500

            if waited >= max_wait:
                return jsonify({
                    'success': False,
                    'error': 'Timeout waiting for delete task to complete',
                    'task_id': task_id
                }), 500

        # Only delete from Redis after successful device cleanup
        delete_service_instance(service_id)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'Service "{service["name"]}" deleted successfully'
        })

    except Exception as e:
        log.error(f"Error deleting template service: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/<service_id>/check_status', methods=['POST'])
def check_service_status(service_id):
    """Check task status and update service state"""
    try:
        service = get_service_instance(service_id)
        if not service:
            return jsonify({'success': False, 'error': 'Service not found'}), 404

        task_id = service.get('task_id')
        if not task_id:
            return jsonify({'success': False, 'error': 'No task ID found'}), 400

        # Check task status
        response = requests.get(
            f'{NETPALM_API_URL}/task/{task_id}',
            headers=NETPALM_HEADERS,
            timeout=10
        )
        response.raise_for_status()
        task_data = response.json()

        task_status = task_data.get('data', {}).get('task_status')
        task_errors = task_data.get('data', {}).get('task_errors', [])

        # Update service state based on task status
        if task_status == 'finished' and not task_errors:
            service['state'] = 'deployed'
        elif task_status == 'failed' or task_errors:
            service['state'] = 'failed'
            service['error'] = str(task_errors) if task_errors else 'Task failed'

        save_service_instance(service)

        return jsonify({
            'success': True,
            'state': service['state'],
            'task_status': task_status
        })

    except Exception as e:
        log.error(f"Error checking service status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/services/instances/<service_id>/validate', methods=['POST'])
def validate_service_instance(service_id):
    """Validate that the service configuration exists on the device"""
    try:
        service = get_service_instance(service_id)
        if not service:
            return jsonify({'success': False, 'error': 'Service not found'}), 404

        # Get credentials from request if provided
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')

        log.info(f"Service validation RAW request data: {data}")
        log.info(f"Validation credentials - username: {username}, has_password: {bool(password)}")

        # Get device connection info
        credential_override = None
        if username and password:
            credential_override = {'username': username, 'password': password}
            log.info(f"Using credential override for validation")

        device_info = get_device_connection_info(service['device'], credential_override)
        if not device_info:
            return jsonify({
                'success': False,
                'error': f'Could not get connection info for device: {service["device"]}'
            }), 400

        # Add credentials
        if username and password:
            device_info['connection_args']['username'] = username
            device_info['connection_args']['password'] = password
        else:
            # Use default credentials from settings
            settings = {}
            try:
                # Try to load from environment or config
                settings = {
                    'username': os.environ.get('DEFAULT_USERNAME'),
                    'password': os.environ.get('DEFAULT_PASSWORD')
                }
            except:
                pass

            if settings.get('username'):
                device_info['connection_args']['username'] = settings['username']
                device_info['connection_args']['password'] = settings['password']

        # Determine appropriate show command based on device type
        device_type = device_info['connection_args'].get('device_type', 'cisco_ios')

        if 'juniper' in device_type.lower() or 'junos' in device_type.lower():
            # For Juniper devices, use "show configuration | display set" for set format
            show_command = 'show configuration | display set'
        else:
            # For Cisco and other vendors, use standard running-config
            show_command = 'show running-config'

        # Get running config from device
        getconfig_payload = {
            'library': 'netmiko',
            'connection_args': device_info['connection_args'],
            'command': show_command,
            'queue_strategy': 'fifo'
        }

        response = requests.post(
            f'{NETPALM_API_URL}/getconfig',
            json=getconfig_payload,
            headers=NETPALM_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        task_id = result.get('data', {}).get('task_id')
        if task_id:
            save_task_id(task_id, device_name=f"validate:{service_id}")

        # Poll for task completion (simple approach for now)
        import time
        max_wait = 30
        waited = 0
        running_config = None

        while waited < max_wait:
            time.sleep(2)
            waited += 2

            task_response = requests.get(
                f'{NETPALM_API_URL}/task/{task_id}',
                headers=NETPALM_HEADERS,
                timeout=10
            )
            task_response.raise_for_status()
            task_data = task_response.json()

            task_status = task_data.get('data', {}).get('task_status')
            if task_status == 'finished':
                running_config = task_data.get('data', {}).get('task_result', {})
                break
            elif task_status == 'failed':
                return jsonify({
                    'success': False,
                    'error': 'Failed to retrieve running config',
                    'task_errors': task_data.get('data', {}).get('task_errors', [])
                }), 500

        if not running_config:
            return jsonify({
                'success': False,
                'error': 'Timeout waiting for config retrieval'
            }), 500

        # Extract config - handle both dict and list formats
        running_config_lines = []

        if isinstance(running_config, dict):
            # Extract from dict (command key)
            config_text = running_config.get(show_command, '') or running_config.get('show running-config', '')
            if isinstance(config_text, list):
                running_config_lines = [line.strip() for line in config_text if line.strip()]
            else:
                running_config_lines = [line.strip() for line in config_text.split('\n') if line.strip()]
        elif isinstance(running_config, list):
            # Already a list
            running_config_lines = [line.strip() for line in running_config if isinstance(line, str) and line.strip()]
        else:
            # String format
            running_config_lines = [line.strip() for line in str(running_config).split('\n') if line.strip()]

        # Get validation config - use validation template if specified, otherwise use deployed config
        validation_template = service.get('validation_template')
        if validation_template:
            # Render validation template with service variables
            log.info(f"Using validation template: {validation_template}")
            template_lookup = validation_template[:-3] if validation_template.endswith('.j2') else validation_template
            validation_config = render_template_locally(template_lookup, service.get('variables', {}))

            if not validation_config:
                log.warning(f"Failed to render validation template, falling back to deployed config")
                validation_config = service['rendered_config']

            rendered_lines = [line.strip() for line in validation_config.split('\n') if line.strip()]
        else:
            # Use deployed config for validation
            rendered_lines = [line.strip() for line in service['rendered_config'].split('\n') if line.strip()]

        # Normalize config lines for comparison - handle abbreviations and whitespace
        def normalize_config_line(line):
            """Normalize a config line for comparison"""
            # Strip all whitespace
            line = line.strip()

            # Handle common Cisco abbreviations
            line = line.replace('int ', 'interface ')
            line = line.replace('Int ', 'Interface ')

            # Normalize IP address format (remove /32 if present for comparison)
            # This helps with cases where running config shows it differently

            return line

        # Normalize both lists for comparison
        normalized_running = [normalize_config_line(line) for line in running_config_lines]
        normalized_rendered = [normalize_config_line(line) for line in rendered_lines]

        # Validate line by line - each rendered line should exist as a substring in running config
        missing_lines = []
        for i, line in enumerate(normalized_rendered):
            # Check if this line appears as a substring in any running config line
            found = False
            for running_line in normalized_running:
                if line in running_line:
                    found = True
                    break

            if not found:
                # Store the original line, not normalized
                missing_lines.append(rendered_lines[i])

        is_valid = len(missing_lines) == 0

        # Update service validation status
        service['last_validated'] = datetime.utcnow().isoformat()
        service['validation_status'] = 'valid' if is_valid else 'invalid'
        if not is_valid:
            service['validation_errors'] = missing_lines

        save_service_instance(service)

        return jsonify({
            'success': True,
            'valid': is_valid,
            'missing_lines': missing_lines,
            'task_id': task_id,
            'message': 'Configuration is present on device' if is_valid else 'Configuration drift detected'
        })

    except Exception as e:
        log.error(f"Error validating service instance: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


### Service Stack Endpoints ###

@app.route('/api/service-stacks', methods=['POST'])
def create_service_stack():
    """Create a new service stack"""
    try:
        data = request.json

        # Validate required fields
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Stack name is required'}), 400

        if not data.get('services') or not isinstance(data['services'], list):
            return jsonify({'success': False, 'error': 'Services list is required'}), 400

        # Create stack data structure
        stack_data = {
            'stack_id': str(uuid.uuid4()),
            'name': data['name'],
            'description': data.get('description', ''),
            'services': data['services'],
            'shared_variables': data.get('shared_variables', {}),
            'state': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        # Validate service structure
        for i, service in enumerate(stack_data['services']):
            if not service.get('name'):
                return jsonify({'success': False, 'error': f'Service {i} missing name'}), 400
            if not service.get('template'):
                return jsonify({'success': False, 'error': f'Service {i} missing template'}), 400

            # Accept both 'device' (old format) and 'devices' (new format)
            if not service.get('device') and not service.get('devices'):
                return jsonify({'success': False, 'error': f'Service {i} missing device(s)'}), 400

            # Set defaults
            service.setdefault('order', i)
            service.setdefault('variables', {})
            service.setdefault('depends_on', [])

        # Save stack
        stack_id = save_service_stack(stack_data)

        return jsonify({
            'success': True,
            'stack_id': stack_id,
            'message': f'Service stack "{data["name"]}" created successfully'
        })

    except Exception as e:
        log.error(f"Error creating service stack: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/service-stacks', methods=['GET'])
def list_service_stacks():
    """Get all service stacks"""
    try:
        stacks = get_all_service_stacks()

        # Add summary information
        for stack in stacks:
            stack['service_count'] = len(stack.get('services', []))
            stack['devices'] = list(set([s.get('device') for s in stack.get('services', []) if s.get('device')]))

        return jsonify({
            'success': True,
            'stacks': stacks,
            'count': len(stacks)
        })

    except Exception as e:
        log.error(f"Error listing service stacks: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/service-stacks/<stack_id>', methods=['GET'])
def get_stack_details(stack_id):
    """Get details of a specific service stack"""
    try:
        stack = get_service_stack(stack_id)

        if not stack:
            return jsonify({'success': False, 'error': 'Service stack not found'}), 404

        # Add additional details
        stack['service_count'] = len(stack.get('services', []))
        stack['devices'] = list(set([s.get('device') for s in stack.get('services', []) if s.get('device')]))
        stack['templates'] = list(set([s.get('template') for s in stack.get('services', []) if s.get('template')]))

        return jsonify({
            'success': True,
            'stack': stack
        })

    except Exception as e:
        log.error(f"Error getting service stack details: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/service-stacks/<stack_id>', methods=['PUT'])
def update_service_stack(stack_id):
    """Update a service stack"""
    try:
        stack = get_service_stack(stack_id)

        if not stack:
            return jsonify({'success': False, 'error': 'Service stack not found'}), 404

        data = request.json

        # Update fields
        if 'name' in data:
            stack['name'] = data['name']
        if 'description' in data:
            stack['description'] = data['description']
        if 'services' in data:
            stack['services'] = data['services']
        if 'shared_variables' in data:
            stack['shared_variables'] = data['shared_variables']
        if 'state' in data:
            stack['state'] = data['state']

        stack['updated_at'] = datetime.utcnow().isoformat()

        save_service_stack(stack)

        return jsonify({
            'success': True,
            'message': f'Service stack "{stack["name"]}" updated successfully'
        })

    except Exception as e:
        log.error(f"Error updating service stack: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/service-stacks/<stack_id>', methods=['DELETE'])
def delete_stack(stack_id):
    """Delete a service stack"""
    try:
        stack = get_service_stack(stack_id)

        if not stack:
            return jsonify({'success': False, 'error': 'Service stack not found'}), 404

        # Optional: Delete associated service instances
        delete_services = request.args.get('delete_services', 'false').lower() == 'true'

        if delete_services and 'deployed_services' in stack:
            for service_id in stack.get('deployed_services', []):
                try:
                    delete_service_instance(service_id)
                except Exception as e:
                    log.warning(f"Failed to delete service {service_id}: {e}")

        delete_service_stack(stack_id)

        return jsonify({
            'success': True,
            'message': f'Service stack "{stack["name"]}" deleted successfully'
        })

    except Exception as e:
        log.error(f"Error deleting service stack: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/service-stacks/<stack_id>/deploy', methods=['POST'])
def deploy_service_stack(stack_id):
    """Deploy all services in a stack with dependency management"""
    try:
        # Get credentials from request
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')

        log.info(f"Deploy request data: {data.keys() if data else 'empty'}")
        log.info(f"Username from request: {username}, Password present: {bool(password)}")

        credential_override = None
        if username and password:
            credential_override = {'username': username, 'password': password}
            log.info(f"Using provided credentials for stack deployment (user: {username})")
        else:
            log.warning(f"No credentials provided in deployment request!")

        stack = get_service_stack(stack_id)

        if not stack:
            return jsonify({'success': False, 'error': 'Service stack not found'}), 404

        if stack.get('state') == 'deploying':
            return jsonify({'success': False, 'error': 'Stack is already being deployed'}), 400

        # Update stack state
        stack['state'] = 'deploying'
        stack['deploy_started_at'] = datetime.utcnow().isoformat()
        stack['deployed_services'] = []
        save_service_stack(stack)

        # Sort services by order
        services = sorted(stack['services'], key=lambda s: s.get('order', 0))

        deployed_service_ids = []
        failed_services = []

        # Deploy services sequentially
        for service_def in services:
            try:
                log.info(f"Deploying service: {service_def}")

                # Check dependencies
                depends_on = service_def.get('depends_on', [])
                if depends_on:
                    # Verify all dependencies are deployed
                    for dep_name in depends_on:
                        dep_deployed = False
                        for deployed_id in deployed_service_ids:
                            deployed_svc = get_service_instance(deployed_id)
                            if deployed_svc and deployed_svc.get('name') == dep_name:
                                if deployed_svc.get('state') != 'deployed':
                                    raise Exception(f"Dependency '{dep_name}' not in deployed state")
                                dep_deployed = True
                                break

                        if not dep_deployed:
                            raise Exception(f"Dependency '{dep_name}' not found or not deployed")

                # Merge shared variables with service-specific variables
                variables = {**stack.get('shared_variables', {}), **service_def.get('variables', {})}

                # Render template once (same config for all devices)
                template_name = service_def.get('template')
                log.info(f"Template name from service_def: '{template_name}'")

                if not template_name:
                    raise Exception(f"Service '{service_def.get('name')}' has no template specified")

                # Strip .j2 extension if present for consistency
                if template_name.endswith('.j2'):
                    template_name = template_name[:-3]

                # Get template metadata (validation and delete templates)
                template_metadata = get_template_metadata(template_name) or {}

                log.info(f"Rendering template: '{template_name}' with variables: {variables}")

                # Render template locally using Jinja2 instead of Netpalm's broken renderer
                rendered_config = render_template_locally(template_name, variables)

                if not rendered_config:
                    raise Exception(f"Failed to render template: {template_name}")

                log.info(f"Rendered config preview: {rendered_config[:200]}...")

                # Handle both single device (old format) and multiple devices (new format)
                devices = service_def.get('devices', [service_def.get('device')]) if service_def.get('devices') else [service_def.get('device')]

                # Deploy to each device
                for device_name in devices:
                    if not device_name:
                        continue

                    # Get device connection info from Netbox
                    log.info(f"Getting connection info for device: {device_name}")
                    device_info = get_device_connection_info(device_name, credential_override)
                    if not device_info:
                        raise Exception(f"Could not get connection info for device '{device_name}'")

                    log.info(f"Deploying configuration to {device_name}")
                    # Deploy configuration
                    deploy_response = requests.post(
                        f'{NETPALM_API_URL}/setconfig',
                        headers=NETPALM_HEADERS,
                        json={
                            'library': 'netmiko',
                            'connection_args': device_info['connection_args'],
                            'config': rendered_config.split('\n')
                        },
                        timeout=60
                    )

                    log.info(f"Deploy response status: {deploy_response.status_code}")
                    if deploy_response.status_code != 201:
                        raise Exception(f"Failed to deploy configuration to {device_name}: {deploy_response.text}")

                    deploy_result = deploy_response.json()
                    task_id = deploy_result.get('data', {}).get('task_id')
                    log.info(f"Got task_id: {task_id}")

                    # Save task to history for monitoring
                    save_task_id(task_id, device_name=f"stack:{stack.get('name')}:{service_def['name']}:{device_name}")

                    # Wait for deployment to complete (with timeout)
                    max_wait = 60
                    waited = 0
                    while waited < max_wait:
                        time.sleep(2)
                        waited += 2

                        status_response = requests.get(
                            f'{NETPALM_API_URL}/task/{task_id}',
                            headers=NETPALM_HEADERS,
                            timeout=10
                        )

                        if status_response.status_code == 200:
                            task_status = status_response.json()
                            task_data = task_status.get('data', {})

                            if task_data.get('task_status') == 'finished':
                                break
                            elif task_data.get('task_status') == 'failed':
                                raise Exception(f"Deployment task failed on {device_name}: {task_data.get('task_errors')}")

                    # Create service instance record for this device
                    service_instance = {
                        'service_id': str(uuid.uuid4()),
                        'name': f"{service_def['name']} ({device_name})",
                        'template': service_def['template'],
                        'validation_template': template_metadata.get('validation_template'),
                        'delete_template': template_metadata.get('delete_template'),
                        'device': device_name,
                        'variables': variables,
                        'rendered_config': rendered_config,
                        'state': 'deployed',
                        'task_id': task_id,
                        'stack_id': stack_id,
                        'stack_order': service_def.get('order', 0),
                        'created_at': datetime.utcnow().isoformat()
                    }

                    save_service_instance(service_instance)
                    deployed_service_ids.append(service_instance['service_id'])

                    log.info(f"Deployed service '{service_def['name']}' to device '{device_name}' in stack '{stack_id}'")

            except Exception as e:
                log.error(f"Failed to deploy service '{service_def['name']}': {e}")
                failed_services.append({
                    'name': service_def['name'],
                    'error': str(e)
                })

                # Stop deployment on first failure
                break

        # Update stack state
        if failed_services:
            stack['state'] = 'failed'
            stack['deployment_errors'] = failed_services
        else:
            stack['state'] = 'deployed'

        stack['deployed_services'] = deployed_service_ids
        stack['deploy_completed_at'] = datetime.utcnow().isoformat()
        save_service_stack(stack)

        return jsonify({
            'success': len(failed_services) == 0,
            'deployed_count': len(deployed_service_ids),
            'failed_count': len(failed_services),
            'deployed_services': deployed_service_ids,
            'failed_services': failed_services,
            'message': f'Stack deployment {"completed successfully" if not failed_services else "failed"}'
        })

    except Exception as e:
        log.error(f"Error deploying service stack: {e}", exc_info=True)

        # Update stack state to failed
        try:
            stack = get_service_stack(stack_id)
            if stack:
                stack['state'] = 'failed'
                stack['deployment_errors'] = [{'error': str(e)}]
                save_service_stack(stack)
        except:
            pass

        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/service-stacks/<stack_id>/validate', methods=['POST'])
def validate_service_stack(stack_id):
    """Validate all services in a stack by calling individual service validation"""
    try:
        stack = get_service_stack(stack_id)

        if not stack:
            return jsonify({'success': False, 'error': 'Service stack not found'}), 404

        if not stack.get('deployed_services'):
            return jsonify({'success': False, 'error': 'Stack has no deployed services'}), 400

        # Get credentials from request
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')

        log.info(f"Stack validation RAW request data: {data}")
        log.info(f"Stack validation credentials - username: {username}, has_password: {bool(password)}")

        validation_results = []
        all_valid = True

        log.info(f"Validating stack '{stack_id}' with {len(stack.get('deployed_services', []))} services")

        # Validate each deployed service using the service validation endpoint
        for service_id in stack.get('deployed_services', []):
            service = get_service_instance(service_id)

            if not service:
                validation_results.append({
                    'service_id': service_id,
                    'service_name': 'Unknown',
                    'valid': False,
                    'message': 'Service not found'
                })
                all_valid = False
                continue

            try:
                log.info(f"Validating service '{service.get('name')}' ({service_id}) with username={username}")

                # Build validation request context and push it
                ctx = app.test_request_context(
                    f'/api/services/instances/{service_id}/validate',
                    method='POST',
                    json={'username': username, 'password': password},
                    content_type='application/json'
                )
                ctx.push()

                try:
                    # Call the service validation function directly
                    response = validate_service_instance(service_id)

                    if isinstance(response, tuple):
                        response_data = response[0].get_json()
                    else:
                        response_data = response.get_json()

                    if response_data.get('success'):
                        is_valid = response_data.get('valid', False)
                        validation_results.append({
                            'service_id': service_id,
                            'service_name': service.get('name'),
                            'valid': is_valid,
                            'message': response_data.get('message', ''),
                            'missing_lines': response_data.get('missing_lines', [])
                        })
                        if not is_valid:
                            all_valid = False
                    else:
                        raise Exception(response_data.get('error', 'Validation failed'))
                finally:
                    ctx.pop()

            except Exception as e:
                log.error(f"Error validating service {service_id}: {e}")
                validation_results.append({
                    'service_id': service_id,
                    'service_name': service.get('name'),
                    'valid': False,
                    'message': f'Validation error: {str(e)}'
                })
                all_valid = False

        # Update stack validation status
        stack['last_validated'] = datetime.utcnow().isoformat()
        stack['validation_status'] = 'valid' if all_valid else 'invalid'
        save_service_stack(stack)

        log.info(f"Stack validation complete: {len(validation_results)} services validated, all_valid={all_valid}")

        return jsonify({
            'success': True,
            'all_valid': all_valid,
            'results': validation_results,
            'message': f'Stack validation {"passed" if all_valid else "failed"}'
        })

    except Exception as e:
        log.error(f"Error validating service stack: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8088, debug=True)
