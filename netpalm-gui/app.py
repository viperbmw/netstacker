"""
Netpalm GUI - Web interface for netpalm network automation
"""
from flask import Flask, render_template, request, jsonify
import requests
import os
import logging
from netbox_client import NetboxClient

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'netpalm-gui-secret-key')

# Configuration
NETPALM_API_URL = os.environ.get('NETPALM_API_URL', 'http://netpalm-controller:9000')
NETPALM_API_KEY = os.environ.get('NETPALM_API_KEY', '2a84465a-cf38-46b2-9d86-b84Q7d57f288')
NETBOX_URL = os.environ.get('NETBOX_URL', 'https://netbox-prprd.gi-nw.viasat.io')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN', '')
VERIFY_SSL = os.environ.get('VERIFY_SSL', 'false').lower() == 'true'

# Initialize Netbox client
netbox = NetboxClient(NETBOX_URL, NETBOX_TOKEN, verify_ssl=VERIFY_SSL)

# Headers for netpalm API calls
NETPALM_HEADERS = {
    'x-api-key': NETPALM_API_KEY,
    'Content-Type': 'application/json'
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


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


# API Endpoints for frontend

@app.route('/api/devices')
def get_devices():
    """Get device list from Netbox"""
    try:
        devices = netbox.get_devices_with_details()
        return jsonify({'success': True, 'devices': devices})
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


@app.route('/api/tasks')
def get_tasks():
    """Get all tasks from netpalm"""
    try:
        response = requests.get(f'{NETPALM_API_URL}/taskqueue/', headers=NETPALM_HEADERS, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        log.error(f"Error fetching tasks: {e}")
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
        return jsonify(response.json())
    except Exception as e:
        log.error(f"Error deploying getconfig: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/deploy/setconfig', methods=['POST'])
def deploy_setconfig():
    """Deploy setconfig to device"""
    try:
        data = request.json

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
        return jsonify(response.json())
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8088, debug=True)
