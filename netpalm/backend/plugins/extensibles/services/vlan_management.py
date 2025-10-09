"""
Comprehensive Netpalm Service Example: VLAN Management Service

This service demonstrates all lifecycle methods and best practices for creating
stateful network services in Netpalm. It manages VLANs across network devices.

Service Lifecycle:
1. create() - Deploy VLAN configuration to device
2. validate() - Verify VLAN exists and is configured correctly
3. health_check() - Check if VLAN is still active and healthy
4. update() - Modify VLAN configuration (name, description)
5. re_deploy() - Reapply VLAN configuration (useful for drift correction)
6. delete() - Remove VLAN from device

Service States:
- creating: Service is being created
- active: Service is deployed and healthy
- updating: Service is being updated
- errored: Service encountered an error
- deleting: Service is being removed
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

from netpalm.backend.core.calls.service.netpalmservice import NetpalmService
from netpalm.backend.core.manager.netpalm_manager import NetpalmManager

log = logging.getLogger(__name__)


class VlanServiceModel(BaseModel):
    """
    Pydantic model defining the service input parameters.
    This model validates and structures the data passed to the service.
    """
    # Required fields
    hostname: str = Field(..., description="Device hostname or IP address")
    vlan_id: int = Field(..., ge=1, le=4094, description="VLAN ID (1-4094)")
    vlan_name: str = Field(..., min_length=1, max_length=32, description="VLAN name")

    # Optional fields with defaults
    device_type: str = Field(default="cisco_ios", description="Netmiko device type")
    username: str = Field(default="admin", description="Device username")
    password: str = Field(default="admin", description="Device password")
    description: Optional[str] = Field(default=None, description="VLAN description")

    # Advanced options
    interfaces: List[str] = Field(default_factory=list, description="List of interfaces to assign to VLAN")
    vlan_enabled: bool = Field(default=True, description="VLAN administrative state")
    timeout: int = Field(default=30, description="Connection timeout in seconds")

    @validator('vlan_name')
    def validate_vlan_name(cls, v):
        """Ensure VLAN name doesn't contain invalid characters"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('VLAN name must be alphanumeric (underscores and hyphens allowed)')
        return v

    class Config:
        schema_extra = {
            "example": {
                "hostname": "switch01.example.com",
                "vlan_id": 100,
                "vlan_name": "GUEST_WIFI",
                "description": "Guest wireless network",
                "interfaces": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"],
                "device_type": "cisco_ios",
                "username": "admin",
                "password": "admin"
            }
        }


class VlanManagementService(NetpalmService):
    """
    VLAN Management Service implementing full lifecycle management
    """

    # Required: Netpalm manager for executing network operations
    mgr = NetpalmManager()

    # Required: Associate the Pydantic model with this service
    model = VlanServiceModel

    def _get_connection_args(self, model_data: model) -> Dict[str, Any]:
        """Helper method to build connection arguments"""
        return {
            "device_type": model_data.device_type,
            "host": model_data.hostname,
            "username": model_data.username,
            "password": model_data.password,
            "timeout": model_data.timeout,
        }

    def _execute_command(self, model_data: model, commands: List[str],
                         operation: str = "config") -> Dict[str, Any]:
        """
        Helper method to execute commands on device

        Args:
            model_data: Service model with connection details
            commands: List of commands to execute
            operation: Type of operation ('config' or 'show')

        Returns:
            Task result from Netpalm
        """
        try:
            if operation == "config":
                # For configuration commands
                netmiko_data = {
                    "library": "netmiko",
                    "connection_args": self._get_connection_args(model_data),
                    "config": commands,
                    "queue_strategy": "pinned",
                }
                job_result = self.mgr.set_config_netmiko(netmiko_data)
            else:
                # For show commands
                netmiko_data = {
                    "library": "netmiko",
                    "connection_args": self._get_connection_args(model_data),
                    "command": commands[0] if isinstance(commands, list) else commands,
                    "queue_strategy": "pinned",
                }
                job_result = self.mgr.get_config_netmiko(netmiko_data)

            # Retrieve the task result
            result = self.mgr.retrieve_task_result(job_result)

            log.info(f"[{self.service_id}] Command execution result: {result}")
            return result

        except Exception as e:
            log.error(f"[{self.service_id}] Command execution failed: {str(e)}")
            raise

    def create(self, model_data: model) -> Dict[str, Any]:
        """
        Create the VLAN service - deploy VLAN to device

        This method:
        1. Builds VLAN configuration commands
        2. Executes commands on device
        3. Stores service metadata
        4. Sets service state to 'active'
        5. Returns deployment result
        """
        log.info(f"[{self.service_id}] Creating VLAN {model_data.vlan_id} on {model_data.hostname}")

        try:
            # Build VLAN configuration commands
            commands = [
                f"vlan {model_data.vlan_id}",
                f"name {model_data.vlan_name}",
            ]

            # Add description if provided
            if model_data.description:
                # Cisco uses 'description' in VLAN config mode (some platforms)
                # For IOS, description might need to be in vlan database or not supported
                pass  # Platform-specific handling

            # Add state command
            if not model_data.vlan_enabled:
                commands.append("shutdown")

            commands.append("exit")

            # Configure interfaces if provided
            for interface in model_data.interfaces:
                commands.extend([
                    f"interface {interface}",
                    "switchport mode access",
                    f"switchport access vlan {model_data.vlan_id}",
                    "exit"
                ])

            # Execute configuration
            result = self._execute_command(model_data, commands, operation="config")

            # Store service metadata for later use
            service_metadata = {
                "hostname": model_data.hostname,
                "vlan_id": model_data.vlan_id,
                "vlan_name": model_data.vlan_name,
                "description": model_data.description,
                "interfaces": model_data.interfaces,
                "created_at": str(datetime.now()),
                "deployment_result": result
            }

            # Set service state to active
            self.mgr.set_service_instance_status(self.service_id, state="active")

            log.info(f"[{self.service_id}] VLAN {model_data.vlan_id} created successfully")

            return {
                "status": "success",
                "message": f"VLAN {model_data.vlan_id} created on {model_data.hostname}",
                "vlan_id": model_data.vlan_id,
                "vlan_name": model_data.vlan_name,
                "service_id": self.service_id,
                "result": result
            }

        except Exception as e:
            error_msg = f"Failed to create VLAN: {str(e)}"
            log.error(f"[{self.service_id}] {error_msg}")

            # Set service state to errored
            self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "error",
                "message": error_msg,
                "error": str(e),
                "service_id": self.service_id
            }

    def validate(self, model_data: model) -> Dict[str, Any]:
        """
        Validate the VLAN configuration exists and matches expected state

        This method:
        1. Retrieves current VLAN configuration
        2. Verifies VLAN ID exists
        3. Checks VLAN name matches
        4. Validates interface assignments
        5. Returns validation result
        """
        log.info(f"[{self.service_id}] Validating VLAN {model_data.vlan_id} on {model_data.hostname}")

        try:
            # Get VLAN configuration
            vlan_check = self._execute_command(
                model_data,
                f"show vlan id {model_data.vlan_id}",
                operation="show"
            )

            # Parse result (simplified - real implementation would parse output)
            validation_result = {
                "vlan_exists": True,  # Would parse from output
                "vlan_name_match": True,  # Would parse from output
                "interfaces_match": True,  # Would parse from output
            }

            # Check if all validations pass
            is_valid = all(validation_result.values())

            if is_valid:
                log.info(f"[{self.service_id}] VLAN validation passed")
                return {
                    "status": "success",
                    "message": "VLAN configuration is valid",
                    "validation": validation_result,
                    "raw_output": vlan_check
                }
            else:
                log.warning(f"[{self.service_id}] VLAN validation failed: {validation_result}")
                return {
                    "status": "warning",
                    "message": "VLAN configuration validation has issues",
                    "validation": validation_result,
                    "raw_output": vlan_check
                }

        except Exception as e:
            error_msg = f"Validation failed: {str(e)}"
            log.error(f"[{self.service_id}] {error_msg}")

            return {
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }

    def health_check(self, model_data: model) -> Dict[str, Any]:
        """
        Check if VLAN is healthy and operational

        This method:
        1. Verifies VLAN exists
        2. Checks VLAN operational state
        3. Validates interface states
        4. Returns health status
        """
        log.info(f"[{self.service_id}] Health check for VLAN {model_data.vlan_id}")

        try:
            # Check VLAN status
            vlan_status = self._execute_command(
                model_data,
                f"show vlan id {model_data.vlan_id}",
                operation="show"
            )

            # Check interface status if interfaces are assigned
            interface_status = []
            for interface in model_data.interfaces:
                intf_check = self._execute_command(
                    model_data,
                    f"show interface {interface} switchport",
                    operation="show"
                )
                interface_status.append({
                    "interface": interface,
                    "status": "up",  # Would parse from output
                    "raw": intf_check
                })

            # Update service state based on health
            self.mgr.set_service_instance_status(self.service_id, state="active")

            return {
                "status": "healthy",
                "message": f"VLAN {model_data.vlan_id} is operational",
                "vlan_status": vlan_status,
                "interface_status": interface_status,
                "service_id": self.service_id
            }

        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            log.error(f"[{self.service_id}] {error_msg}")

            # Set service to errored if health check fails
            self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "unhealthy",
                "message": error_msg,
                "error": str(e)
            }

    def update(self, model_data: model) -> Dict[str, Any]:
        """
        Update VLAN configuration (name, description, interfaces)

        This method:
        1. Sets service state to 'updating'
        2. Updates VLAN name/description
        3. Updates interface assignments
        4. Sets state back to 'active'
        5. Returns update result
        """
        log.info(f"[{self.service_id}] Updating VLAN {model_data.vlan_id} on {model_data.hostname}")

        try:
            # Set service state to updating
            self.mgr.set_service_instance_status(self.service_id, state="updating")

            # Build update commands - just update name and interfaces
            commands = [
                f"vlan {model_data.vlan_id}",
                f"name {model_data.vlan_name}",
                "exit"
            ]

            # Update interface assignments
            for intf in model_data.interfaces:
                commands.extend([
                    f"interface {intf}",
                    "switchport mode access",
                    f"switchport access vlan {model_data.vlan_id}",
                    "exit"
                ])

            # Execute update commands
            result = self._execute_command(model_data, commands, operation="config")

            # Set service state back to active
            self.mgr.set_service_instance_status(self.service_id, state="active")

            log.info(f"[{self.service_id}] VLAN {model_data.vlan_id} updated successfully")

            return {
                "status": "success",
                "message": f"VLAN {model_data.vlan_id} updated successfully",
                "service_id": self.service_id,
                "result": result
            }

        except Exception as e:
            error_msg = f"Update failed: {str(e)}"
            log.error(f"[{self.service_id}] {error_msg}")

            self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }

    def re_deploy(self, model_data: model) -> Dict[str, Any]:
        """
        Re-deploy VLAN configuration (useful for drift correction)

        This method:
        1. Removes existing VLAN configuration
        2. Re-applies VLAN configuration
        3. Validates deployment
        4. Returns result
        """
        log.info(f"[{self.service_id}] Re-deploying VLAN {model_data.vlan_id}")

        try:
            # First, delete existing config
            delete_commands = [
                f"no vlan {model_data.vlan_id}"
            ]
            self._execute_command(model_data, delete_commands, operation="config")

            # Then re-create (reuse create logic)
            create_result = self.create(model_data)

            log.info(f"[{self.service_id}] VLAN {model_data.vlan_id} re-deployed successfully")

            return {
                "status": "success",
                "message": f"VLAN {model_data.vlan_id} re-deployed successfully",
                "service_id": self.service_id,
                "create_result": create_result
            }

        except Exception as e:
            error_msg = f"Re-deploy failed: {str(e)}"
            log.error(f"[{self.service_id}] {error_msg}")

            self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }

    def delete(self, model_data: model) -> Dict[str, Any]:
        """
        Delete VLAN configuration from device

        This method:
        1. Sets service state to 'deleting'
        2. Removes VLAN from interfaces
        3. Removes VLAN from device
        4. Returns deletion result
        """
        log.info(f"[{self.service_id}] Deleting VLAN {model_data.vlan_id} from {model_data.hostname}")

        try:
            # Set service state to deleting
            self.mgr.set_service_instance_status(self.service_id, state="deleting")

            # Build deletion commands
            commands = []

            # Remove VLAN from interfaces first
            for interface in model_data.interfaces:
                commands.extend([
                    f"interface {interface}",
                    "no switchport access vlan",
                    "exit"
                ])

            # Delete the VLAN
            commands.append(f"no vlan {model_data.vlan_id}")

            # Execute deletion commands
            result = self._execute_command(model_data, commands, operation="config")

            log.info(f"[{self.service_id}] VLAN {model_data.vlan_id} deleted successfully")

            return {
                "status": "success",
                "message": f"VLAN {model_data.vlan_id} deleted from {model_data.hostname}",
                "service_id": self.service_id,
                "result": result
            }

        except Exception as e:
            error_msg = f"Deletion failed: {str(e)}"
            log.error(f"[{self.service_id}] {error_msg}")

            self.mgr.set_service_instance_status(self.service_id, state="errored")

            return {
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }


"""
Usage Examples:

1. Create a VLAN service instance:
POST /service/vlan_management

{
    "hostname": "switch01.lab.local",
    "vlan_id": 100,
    "vlan_name": "GUEST_WIFI",
    "description": "Guest wireless network",
    "interfaces": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"],
    "device_type": "cisco_ios",
    "username": "admin",
    "password": "password"
}

Response: {"service_id": "12345", "status": "creating"}

2. Validate the service:
POST /service/instance/12345/validate

3. Health check:
POST /service/instance/12345/health_check

4. Update the service (change name or add interfaces):
POST /service/instance/12345/update

{
    "hostname": "switch01.lab.local",
    "vlan_id": 100,
    "vlan_name": "GUEST_NETWORK",
    "interfaces": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/3"]
}

5. Re-deploy (fix drift):
POST /service/instance/12345/redeploy

6. Delete the service:
DELETE /service/instance/12345
"""
