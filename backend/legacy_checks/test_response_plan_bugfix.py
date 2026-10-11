import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.services.incidents.incident_service import incident_service
from app.services.resources.resource_service import resource_service
from app.services.route_monitor_service import route_monitor_service
from app.services.route_replacement_service import route_replacement_service
from app.services.scenario_service import scenario_service
from app.services.routing_service import routing_service

client = TestClient(app)

def test_response_plan_isolation_and_idempotency():
    # 1. Populate demo incidents
    res = client.post("/api/national/incidents/recommend")
    assert res.status_code == 200
    
    incidents_res = client.get("/api/national/incidents")
    assert incidents_res.status_code == 200
    records = incidents_res.json().get("records", [])
    assert len(records) >= 2
    
    inc_a = records[0]["incident_id"]
    inc_b = records[1]["incident_id"]
    assert inc_a != inc_b

    # 2. Generate response plan for Incident A
    gen_a = client.post(f"/api/national/incidents/{inc_a}/response-plan")
    assert gen_a.status_code == 200
    plan_a = gen_a.json()["plan"]
    assert plan_a["incident_id"] == inc_a
    assert plan_a["status"] == "PENDING_APPROVAL"
    plan_a_id = plan_a["response_plan_id"]

    # 3. Approve Incident A response plan
    app_a1 = client.post(f"/api/national/response-plans/{plan_a_id}/approve")
    assert app_a1.status_code == 200
    plan_a_approved = app_a1.json()["plan"]
    assert plan_a_approved["status"] == "APPROVED"

    # 4. Repeat approval of Incident A (Idempotency test - must NOT fail with 400 or corrupt state)
    app_a2 = client.post(f"/api/national/response-plans/{plan_a_id}/approve")
    assert app_a2.status_code == 200
    assert app_a2.json()["status"] == "success"
    assert app_a2.json()["plan"]["status"] == "APPROVED"

    # 5. Generate response plan for Incident B
    gen_b = client.post(f"/api/national/incidents/{inc_b}/response-plan")
    assert gen_b.status_code == 200
    plan_b = gen_b.json()["plan"]
    assert plan_b["incident_id"] == inc_b
    assert plan_b["status"] == "PENDING_APPROVAL"
    plan_b_id = plan_b["response_plan_id"]
    assert plan_b_id != plan_a_id

    # 6. Verify Incident A remains APPROVED when fetching Incident A plans
    plans_a = client.get(f"/api/national/incidents/{inc_a}/response-plan").json()["records"]
    assert len(plans_a) > 0
    assert plans_a[-1]["status"] == "APPROVED"
    assert plans_a[-1]["incident_id"] == inc_a

    # 7. Approve Incident B plan
    app_b = client.post(f"/api/national/response-plans/{plan_b_id}/approve")
    assert app_b.status_code == 200
    assert app_b.json()["plan"]["status"] == "APPROVED"

    # 8. Dispatch response action for Incident A
    actions = plan_a_approved.get("actions", [])
    if actions:
        action_id = actions[0]["action_id"]
        disp_res = client.post(f"/api/national/response-actions/{action_id}/dispatch")
        assert disp_res.status_code == 200
        assert disp_res.json()["status"] == "success"

    # 9. Verify Replacement Route Flow still works
    scenario_service.set_active(True)
    scenario_service.update_config({
        "precipitation_mm": 300.0,
        "affected_area": {
            "min_lat": 15.3605, "max_lat": 15.3618,
            "min_lon": 75.1220, "max_lon": 75.1230
        }
    })

    standard_route = routing_service.calculate_route(15.36, 75.12, 15.37, 75.13, hazard_aware=False)
    reg_response = route_monitor_service.register_route(standard_route)
    route_id = reg_response["route_id"]

    # Reassess to trigger INVALIDATED
    route_monitor_service.reassess_route(route_id)
    assert route_monitor_service._monitored_routes[route_id]["monitor_status"] == "INVALIDATED"

    rec_res = client.post(f"/api/route-monitor/{route_id}/replacement/recommend")
    assert rec_res.status_code == 200
    rec_json = rec_res.json()
    assert rec_json["replacement_status"] == "RECOMMENDATION_READY"
    rec_id = rec_json["recommendation_id"]

    app_route = client.post(f"/api/route-monitor/{route_id}/replacement/approve", json={
        "recommendation_id": rec_id,
        "approved": True
    })
    assert app_route.status_code == 200
    assert app_route.json()["status"] == "success"
    assert route_monitor_service._monitored_routes[route_id]["monitor_status"] == "REPLACED"

    scenario_service.set_active(False)

if __name__ == "__main__":
    test_response_plan_isolation_and_idempotency()
    print("ALL TARGETED BUGFIX TESTS PASSED!")
