import os
import logging

log = logging.getLogger(__name__)


def run(**kwargs):
    """
    List all available service templates
    Returns a list of service template names (without .py extension)
    """
    try:
        service_dir = "/code/netpalm/backend/plugins/extensibles/services"

        if not os.path.exists(service_dir):
            return {"templates": [], "error": "Service directory not found"}

        templates = []
        for filename in os.listdir(service_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                # Remove .py extension
                template_name = filename[:-3]
                templates.append(template_name)

        templates.sort()
        log.info(f"Found {len(templates)} service templates: {templates}")

        return {"templates": templates}
    except Exception as e:
        log.error(f"Error listing service templates: {e}")
        return {"templates": [], "error": str(e)}
