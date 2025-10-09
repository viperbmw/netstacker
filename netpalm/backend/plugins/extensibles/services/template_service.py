"""
Template-Based Service
======================
A simplified service approach where services are:
- A Jinja2 template (config snippet)
- Variables to render the template
- Target devices to apply the config to

This makes services accessible without requiring Python knowledge.

Lifecycle:
- create: Render template with variables, push to all devices
- validate: Fetch device config, check if rendered config exists
- health_check: Same as validate
- update: Re-render with new variables/devices and push
- re_deploy: Push same config again
- delete: Use reverse template to remove config
"""

import logging
import json
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from netpalm.backend.core.calls.service.netpalmservice import NetpalmService
from netpalm.backend.core.manager.netpalm_manager import NetpalmManager

log = logging.getLogger(__name__)


class TemplateServiceModel(BaseModel):
    """
    Template-based service model.
    User selects a template, provides variables, and selects devices.
    """
    # Service metadata
    name: str = Field(..., description="Friendly name for this service instance")

    # Template configuration
    template: str = Field(..., description="Name of the Jinja2 template to use")
    reverse_template: Optional[str] = Field(None, description="Template to remove the configuration")

    # Variables for template rendering
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables to render the template")

    # Target devices (device names from Netbox)
    devices: List[str] = Field(..., description="List of device hostnames to apply config to")

    # Optional credential override (otherwise uses defaults from settings)
    credential_override: Optional[Dict[str, str]] = Field(None, description="Optional username/password override")


class TemplateService(NetpalmService):
    """Template-based service - no Python knowledge required"""

    mgr = NetpalmManager()
    model = TemplateServiceModel

    def _get_device_info(self, hostname: str) -> Dict[str, Any]:
        """
        Get device connection info from Netbox.
        This should be called from the GUI layer which has access to Netbox.
        Here we expect it to be passed in the variables.
        """
        # Device info should be pre-populated by GUI in variables as _device_info
        device_info = {}
        if hasattr(self, 'device_cache'):
            device_info = self.device_cache.get(hostname, {})

        return device_info

    def _render_template(self, template_name: str, variables: Dict[str, Any]) -> str:
        """Render a Jinja2 template with variables"""
        try:
            # Use Netpalm's template rendering
            result = self.mgr.execute_script(
                library="j2",
                args={
                    "template": template_name,
                    "args": variables
                }
            )

            if result and 'task_result' in result:
                return result['task_result']

            log.error(f"Failed to render template {template_name}")
            return None

        except Exception as e:
            log.error(f"Error rendering template {template_name}: {e}")
            return None

    def _push_config_to_device(self, hostname: str, config: str, model_data: model) -> Dict[str, Any]:
        """Push rendered config to a single device"""
        try:
            # Get device connection info
            # In reality, this should come from Netbox via GUI
            # For now, we'll use basic info from model_data

            device_type = "cisco_ios"  # Default, should come from Netbox
            username = None
            password = None

            # Check for credential override
            if model_data.credential_override:
                username = model_data.credential_override.get('username')
                password = model_data.credential_override.get('password')

            # Build setconfig request
            setconfig_data = {
                "library": "netmiko",
                "connection_args": {
                    "device_type": device_type,
                    "host": hostname,
                    "username": username,
                    "password": password,
                },
                "config": config.split('\n'),
                "queue_strategy": "fifo"
            }

            # Execute setconfig
            result = self.mgr.set_config_netmiko(setconfig_data)
            task_result = self.mgr.retrieve_task_result(result)

            return {
                "device": hostname,
                "status": "success",
                "result": task_result
            }

        except Exception as e:
            log.error(f"Error pushing config to {hostname}: {e}")
            return {
                "device": hostname,
                "status": "error",
                "error": str(e)
            }

    def _validate_device_config(self, hostname: str, expected_config: str, model_data: model) -> Dict[str, Any]:
        """Check if device has the expected config snippet"""
        try:
            device_type = "cisco_ios"
            username = None
            password = None

            if model_data.credential_override:
                username = model_data.credential_override.get('username')
                password = model_data.credential_override.get('password')

            # Get device config
            getconfig_data = {
                "library": "netmiko",
                "connection_args": {
                    "device_type": device_type,
                    "host": hostname,
                    "username": username,
                    "password": password,
                },
                "command": "show running-config",
                "queue_strategy": "fifo"
            }

            result = self.mgr.get_config_netmiko(getconfig_data)
            task_result = self.mgr.retrieve_task_result(result)

            # Check if config snippet exists in device config
            device_config = str(task_result.get('task_result', ''))

            # Simple check - does the config contain our snippet?
            # Remove whitespace for comparison
            expected_lines = [line.strip() for line in expected_config.split('\n') if line.strip()]
            device_lines = device_config.split('\n')

            # Check if all expected lines exist in device config
            config_present = all(
                any(expected_line in device_line for device_line in device_lines)
                for expected_line in expected_lines
            )

            return {
                "device": hostname,
                "status": "valid" if config_present else "drift_detected",
                "config_present": config_present
            }

        except Exception as e:
            log.error(f"Error validating config on {hostname}: {e}")
            return {
                "device": hostname,
                "status": "error",
                "error": str(e)
            }

    def create(self, model_data: model):
        """Create service: render template and push to all devices"""
        log.info(f"[{self.service_id}] Creating template service: {model_data.name}")

        try:
            # Render the template with variables
            rendered_config = self._render_template(model_data.template, model_data.variables)

            if not rendered_config:
                self.mgr.set_service_instance_status(self.service_id, state="errored")
                return {
                    "status": "error",
                    "error": "Failed to render template"
                }

            # Push config to all devices
            results = []
            for device in model_data.devices:
                result = self._push_config_to_device(device, rendered_config, model_data)
                results.append(result)

            # Check if all succeeded
            all_success = all(r['status'] == 'success' for r in results)

            if all_success:
                self.mgr.set_service_instance_status(self.service_id, state="active")
            else:
                self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "success" if all_success else "partial_success",
                "message": f"Service '{model_data.name}' created",
                "rendered_config": rendered_config,
                "device_results": results
            }

        except Exception as e:
            log.error(f"[{self.service_id}] Error: {str(e)}")
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}

    def validate(self, model_data: model):
        """Validate service: check if config exists on all devices (drift detection)"""
        log.info(f"[{self.service_id}] Validating service: {model_data.name}")

        try:
            # Render the template to get expected config
            rendered_config = self._render_template(model_data.template, model_data.variables)

            if not rendered_config:
                return {
                    "status": "error",
                    "error": "Failed to render template for validation"
                }

            # Validate config on all devices
            results = []
            for device in model_data.devices:
                result = self._validate_device_config(device, rendered_config, model_data)
                results.append(result)

            # Check for drift
            drift_detected = any(r['status'] == 'drift_detected' for r in results)
            all_valid = all(r['status'] == 'valid' for r in results)

            return {
                "status": "valid" if all_valid else "drift_detected",
                "message": "Configuration drift detected" if drift_detected else "All devices in sync",
                "device_results": results
            }

        except Exception as e:
            log.error(f"[{self.service_id}] Validation error: {str(e)}")
            return {"status": "error", "error": str(e)}

    def health_check(self, model_data: model):
        """Health check is same as validate for template services"""
        log.info(f"[{self.service_id}] Health check")
        return self.validate(model_data)

    def update(self, model_data: model):
        """Update service: re-render with new variables/devices and push"""
        log.info(f"[{self.service_id}] Updating service: {model_data.name}")

        try:
            self.mgr.set_service_instance_status(self.service_id, state="updating")

            # Render template with new variables
            rendered_config = self._render_template(model_data.template, model_data.variables)

            if not rendered_config:
                self.mgr.set_service_instance_status(self.service_id, state="errored")
                return {
                    "status": "error",
                    "error": "Failed to render template"
                }

            # Push to all devices (including any new ones)
            results = []
            for device in model_data.devices:
                result = self._push_config_to_device(device, rendered_config, model_data)
                results.append(result)

            all_success = all(r['status'] == 'success' for r in results)

            if all_success:
                self.mgr.set_service_instance_status(self.service_id, state="active")
            else:
                self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "success" if all_success else "partial_success",
                "message": "Service updated",
                "device_results": results
            }

        except Exception as e:
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}

    def re_deploy(self, model_data: model):
        """Re-deploy: push the same config again"""
        log.info(f"[{self.service_id}] Re-deploying service")
        return self.create(model_data)

    def delete(self, model_data: model):
        """Delete service: use reverse template to remove config"""
        log.info(f"[{self.service_id}] Deleting service: {model_data.name}")

        try:
            self.mgr.set_service_instance_status(self.service_id, state="deleting")

            # Use reverse template if available
            if not model_data.reverse_template:
                return {
                    "status": "warning",
                    "message": "No reverse template defined - service marked as deleted but config not removed"
                }

            # Render reverse template
            rendered_config = self._render_template(model_data.reverse_template, model_data.variables)

            if not rendered_config:
                return {
                    "status": "error",
                    "error": "Failed to render reverse template"
                }

            # Push reverse config to all devices
            results = []
            for device in model_data.devices:
                result = self._push_config_to_device(device, rendered_config, model_data)
                results.append(result)

            return {
                "status": "success",
                "message": "Service deleted and config removed from devices",
                "device_results": results
            }

        except Exception as e:
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}
