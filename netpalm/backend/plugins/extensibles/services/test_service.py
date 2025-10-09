"""
Simple Test Service - No device required

This service demonstrates the lifecycle without needing a real device.
Perfect for testing the UI and understanding how services work.
"""

import logging
from datetime import datetime
from pydantic import BaseModel, Field
from netpalm.backend.core.calls.service.netpalmservice import NetpalmService
from netpalm.backend.core.manager.netpalm_manager import NetpalmManager

log = logging.getLogger(__name__)


class TestServiceModel(BaseModel):
    """Simple test service model"""
    name: str = Field(..., description="Name of the test instance")
    description: str = Field(default="", description="Optional description")
    value: int = Field(default=42, description="A test number value", ge=1, le=100)


class TestService(NetpalmService):
    """Test service that doesn't require a real device"""

    mgr = NetpalmManager()
    model = TestServiceModel

    def create(self, model_data: model):
        """Create the test service"""
        log.info(f"[{self.service_id}] Creating test service: {model_data.name}")

        try:
            # Just set the status and return result
            self.mgr.set_service_instance_status(self.service_id, state="active")

            result = {
                "status": "success",
                "message": f"Test service '{model_data.name}' created",
                "service_id": self.service_id,
                "data": {
                    "name": model_data.name,
                    "description": model_data.description,
                    "value": model_data.value,
                    "created_at": str(datetime.now())
                }
            }

            log.info(f"[{self.service_id}] Service created successfully")
            return result

        except Exception as e:
            log.error(f"[{self.service_id}] Error: {str(e)}")
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}

    def validate(self, model_data: model):
        """Validate the service"""
        log.info(f"[{self.service_id}] Validating test service")

        return {
            "status": "success",
            "message": "Validation passed - test service is valid",
            "validation": {
                "name": model_data.name,
                "value": model_data.value
            }
        }

    def health_check(self, model_data: model):
        """Health check"""
        log.info(f"[{self.service_id}] Health check")

        self.mgr.set_service_instance_status(self.service_id, state="active")

        return {
            "status": "healthy",
            "message": "Service is healthy",
            "uptime": "Always up - this is a test service!",
            "checked_at": str(datetime.now())
        }

    def update(self, model_data: model):
        """Update the service"""
        log.info(f"[{self.service_id}] Updating test service")

        try:
            self.mgr.set_service_instance_status(self.service_id, state="updating")

            result = {
                "status": "success",
                "message": "Service updated",
                "data": {
                    "name": model_data.name,
                    "description": model_data.description,
                    "value": model_data.value,
                    "updated_at": str(datetime.now())
                }
            }

            self.mgr.set_service_instance_status(self.service_id, state="active")
            return result

        except Exception as e:
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}

    def re_deploy(self, model_data: model):
        """Re-deploy the service"""
        log.info(f"[{self.service_id}] Re-deploying test service")

        # Just re-create
        return self.create(model_data)

    def delete(self, model_data: model):
        """Delete the service"""
        log.info(f"[{self.service_id}] Deleting test service")

        try:
            self.mgr.set_service_instance_status(self.service_id, state="deleting")

            return {
                "status": "success",
                "message": f"Test service '{model_data.name}' deleted",
                "deleted_at": str(datetime.now())
            }

        except Exception as e:
            self.mgr.set_service_instance_status(self.service_id, state="errored")
            return {"status": "error", "error": str(e)}
