"""
Datadog Incident & Case Management Integration.
Automatically create incidents/cases based on LLM quality metrics.
"""
import os
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.incidents_api import IncidentsApi
from datadog_api_client.v2.model.incident_create_request import IncidentCreateRequest
from datadog_api_client.v2.model.incident_create_data import IncidentCreateData
from app.logging_config import setup_logging
import requests

logger = setup_logging()

DD_API_KEY = os.environ.get("DD_API_KEY")
DD_SITE = os.environ.get("DD_SITE", "datadoghq.com")

def create_incident(title: str, severity: str, fields: dict, request_id: str) -> dict:
    """Create Datadog Incident"""
    if not DD_API_KEY:
        logger.warning("DD_API_KEY not set, skipping incident creation")
        return {"status": "skipped"}
        
    try:
        configuration = Configuration()
        configuration.api_key["apiKeyAuth"] = DD_API_KEY
        configuration.server_variables["site"] = DD_SITE
        
        with ApiClient(configuration) as api_client:
            api_instance = IncidentsApi(api_client)
            
            body = IncidentCreateRequest(
                data=IncidentCreateData(
                    type="incidents",
                    attributes={
                        "title": title,
                        "severity": severity,
                        "impact": {
                            "customer_impact_scope": "Some customers",
                            "customer_impact_duration": 0,
                            "customer_impacted_count": 100,  # Estimated
                        },
                        "fields": {
                            "detection_method": "LLM-as-a-Judge",
                            "request_id": request_id,
                            **fields
                        }
                    }
                )
            )
            
            response = api_instance.create_incident(body=body)
            incident_id = response.data.id
            
            logger.info(
                "Incident created in Datadog",
                extra={
                    "incident_id": incident_id,
                    "title": title,
                    "severity": severity,
                    "request_id": request_id
                }
            )
            
            return {"incident_id": incident_id, "status": "created"}
    
    except Exception as e:
        logger.error(
            "Failed to create incident",
            extra={"error": str(e), "request_id": request_id},
            exc_info=True
        )
        return {"status": "failed", "error": str(e)}

def create_case(title: str, priority: str, fields: dict, request_id: str) -> dict:
    """Create Datadog Case"""
    if not DD_API_KEY:
        logger.warning("DD_API_KEY not set, skipping case creation")
        return {"status": "skipped"}

    try:
        url = f"https://api.{DD_SITE}/api/v2/cases"
        headers = {
            "DD-API-KEY": DD_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "data": {
                "type": "case",
                "attributes": {
                    "title": title,
                    "priority": priority,
                    "status": "open",
                    "description": f"Automatic case creation from LLM quality monitoring (request_id: {request_id})",
                    "fields": fields
                }
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            case_id = response.json()["data"]["id"]
            logger.info(
                "Case created in Datadog",
                extra={
                    "case_id": case_id,
                    "title": title,
                    "priority": priority,
                    "request_id": request_id
                }
            )
            return {"case_id": case_id, "status": "created"}
        else:
            logger.warning(
                "Case creation returned non-201",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                    "request_id": request_id
                }
            )
            return {"status": "failed", "status_code": response.status_code}
    
    except Exception as e:
        logger.error(
            "Failed to create case",
            extra={"error": str(e), "request_id": request_id},
            exc_info=True
        )
        return {"status": "failed", "error": str(e)}
