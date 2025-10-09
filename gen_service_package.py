import argparse
import os
import base64

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='netpalm service package generator')
    required_files = parser.add_argument_group('required arguments')
    required_files.add_argument('-n', '--name', help='service package name', required=True)
    required_files.add_argument('-o', '--output', help='python | base64', default="python", required=False)
    optional_files = parser.add_argument_group('optional arguments')
    optional_files.add_argument('-d', '--destination', help='destination path (default: current directory)', default=".", required=False)
    args = parser.parse_args()

    package_name = args.name.replace(" ", "_")
    destination = args.destination
    output_format = args.output

    # Determine the full path
    if destination != ".":
        full_path = os.path.join(destination, package_name)
    else:
        full_path = package_name

    if os.path.isdir(full_path) or os.path.isfile(f'{full_path}.py'):
        print(f"Error: '{package_name}' already exists. Please use a different package name.")
        exit(1)

    # Create the service template
    example_service = f'''import logging

from pydantic import BaseModel
from netpalm.backend.core.calls.service.netpalmservice import NetpalmService
from netpalm.backend.core.manager.netpalm_manager import NetpalmManager

log = logging.getLogger(__name__)


class {package_name.title().replace("_", "")}Model(BaseModel):
    """
    Service model defining input parameters for {package_name}
    Add your required fields here
    """
    hostname: str
    # Add additional fields as needed
    # username: str
    # vlan_id: int
    # interface: str


class {package_name.title().replace("_", "")}Service(NetpalmService):
    """
    Service class implementing lifecycle methods for {package_name}
    """

    mgr = NetpalmManager()
    model = {package_name.title().replace("_", "")}Model

    def create(self, model_data: model):
        """
        Create/deploy the service instance
        This is where you implement the logic to deploy your service
        """
        log.info(f"{package_name}: Creating service instance {{self.service_id}} for {{model_data.hostname}}")

        try:
            # Example: Use netpalm manager to interact with devices
            netmiko_send_data = {{
                "library": "netmiko",
                "connection_args": {{
                    "device_type": "cisco_ios",
                    "host": model_data.hostname,
                    "username": "admin",
                    "password": "admin",
                    "timeout": 10,
                }},
                "command": "show version",
                "queue_strategy": "pinned",
            }}

            job_result = self.mgr.get_config_netmiko(netmiko_send_data)
            return_result = self.mgr.retrieve_task_result(job_result)

            # Set service instance status based on result
            if return_result.get("data", {{}}).get("task_result"):
                self.mgr.set_service_instance_status(self.service_id, state="deployed")
                log.info(f"{package_name}: Service instance {{self.service_id}} deployed successfully")
            else:
                self.mgr.set_service_instance_status(self.service_id, state="errored")
                log.error(f"{package_name}: Service instance {{self.service_id}} deployment failed")

            return return_result

        except Exception as e:
            log.error(f"{package_name}: Error creating service instance {{self.service_id}}: {{e}}")
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            raise

    def update(self, model_data: model):
        """
        Update an existing service instance
        Implement logic to modify the deployed service
        """
        log.info(f"{package_name}: Updating service instance {{self.service_id}}")
        # Implement your update logic here
        pass

    def delete(self, model_data: model):
        """
        Delete/tear down the service instance
        Implement logic to remove the deployed service
        """
        log.info(f"{package_name}: Deleting service instance {{self.service_id}}")
        # Implement your deletion logic here
        pass

    def re_deploy(self, model_data: model):
        """
        Re-deploy the service instance
        Useful for configuration drift remediation
        """
        log.info(f"{package_name}: Re-deploying service instance {{self.service_id}}")
        # Typically calls delete() then create()
        return self.create(model_data)

    def validate(self, model_data: model):
        """
        Validate the service instance configuration
        Check if deployed configuration matches desired state
        """
        log.info(f"{package_name}: Validating service instance {{self.service_id}}")
        # Implement your validation logic here
        pass

    def health_check(self, model_data: model):
        """
        Perform health check on the service instance
        Verify the service is functioning correctly
        """
        log.info(f"{package_name}: Health check for service instance {{self.service_id}}")
        # Implement your health check logic here
        pass
'''

    if output_format == "python":
        # Write Python file
        with open(f'{full_path}.py', 'w') as fp:
            fp.write(example_service)
        print(f"✓ Service package created: {full_path}.py")
        print(f"\nNext steps:")
        print(f"1. Edit {full_path}.py and implement your service logic")
        print(f"2. Copy to netpalm/backend/plugins/extensibles/services/")
        print(f"3. Restart netpalm to load the service")
        print(f"4. Access via: POST /service/instance/create/{package_name}")

    elif output_format == "base64":
        # Encode as base64
        encoded = base64.b64encode(example_service.encode()).decode()
        with open(f'{full_path}_base64.txt', 'w') as fp:
            fp.write(encoded)
        print(f"✓ Service package created (base64): {full_path}_base64.txt")
        print(f"\nNext steps:")
        print(f"1. Use the base64 content to upload via netpalm API")
        print(f"2. Or decode and copy to netpalm/backend/plugins/extensibles/services/")
    else:
        print(f"Error: Invalid output format '{output_format}'. Use 'python' or 'base64'")
        exit(1)
