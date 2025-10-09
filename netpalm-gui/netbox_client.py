"""
Netbox API client for fetching device information
"""
import requests
from typing import List, Dict
import logging

log = logging.getLogger(__name__)


class NetboxClient:
    def __init__(self, base_url: str, token: str = None, verify_ssl: bool = True):
        """
        Initialize Netbox client

        Args:
            base_url: Netbox base URL (e.g., https://netbox-prprd.gi-nw.viasat.io)
            token: Optional API token for authentication
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        if self.token:
            self.session.headers.update({
                'Authorization': f'Token {token}',
                'Content-Type': 'application/json'
            })

    def get_devices(self, brief: bool = True, limit: int = 1000, manufacturer_ids: list = None) -> List[Dict]:
        """
        Fetch all devices from Netbox

        Args:
            brief: Use brief format for faster response
            limit: Number of results per page (default 1000 for faster pagination)
            manufacturer_ids: List of manufacturer IDs to filter (default: [7, 1, 5, 3])

        Returns:
            List of device dictionaries with name, id, and other metadata
        """
        try:
            # Default to specific manufacturers if not provided
            if manufacturer_ids is None:
                manufacturer_ids = [7, 1, 5, 3]

            # Build query string with multiple manufacturer_id parameters
            query_parts = []
            if brief:
                query_parts.append('brief=true')
            if limit:
                query_parts.append(f'limit={limit}')
            for mid in manufacturer_ids:
                query_parts.append(f'manufacturer_id={mid}')

            url = f"{self.base_url}/api/dcim/devices/?{'&'.join(query_parts)}"

            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()

            data = response.json()
            devices = data.get('results', [])

            log.info(f"Fetched {len(devices)} devices from Netbox (total count: {data.get('count', 0)})")

            # Handle pagination if there are more results
            while data.get('next'):
                log.info(f"Fetching next page: {data['next']}")
                response = self.session.get(data['next'], verify=self.verify_ssl, timeout=30)
                response.raise_for_status()
                data = response.json()
                devices.extend(data.get('results', []))

            log.info(f"Total devices fetched: {len(devices)}")
            return devices

        except requests.exceptions.RequestException as e:
            log.error(f"Error fetching devices from Netbox: {e}")
            return []

    def get_device_names(self) -> List[str]:
        """
        Get a simple list of device names

        Returns:
            List of device name strings
        """
        devices = self.get_devices()
        return sorted([device.get('name', '') for device in devices if device.get('name')])

    def get_devices_with_details(self) -> List[Dict]:
        """
        Get devices with relevant details for the GUI
        Uses brief format for faster response

        Returns:
            List of dicts containing name, id, display, etc.
        """
        devices = self.get_devices(brief=True)
        device_list = []

        for device in devices:
            # Brief format returns: id, url, display, name, description
            device_list.append({
                'name': device.get('name', ''),
                'id': device.get('id'),
                'display': device.get('display', device.get('name', '')),
                'url': device.get('url', '')
            })

        # Remove duplicates and sort by name
        seen = set()
        unique_devices = []
        for device in device_list:
            if device['name'] and device['name'] not in seen:
                seen.add(device['name'])
                unique_devices.append(device)

        return sorted(unique_devices, key=lambda x: x['name'])
