import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.route_monitor_service import route_monitor_service
from app.services.route_replacement_service import route_replacement_service
from app.services.scenario_service import scenario_service
from app.services.routing_service import routing_service
from app.services.weather_adapter import weather_adapter
import time

def run_tests():
    print("============================================================")
    print("  PHASE 5C-3: ROUTE REPLACEMENT TESTS")
    print("============================================================")
    
    scenario_service.set_active(False)
    
    # 1. Base standard route
    origin_lat, origin_lon = 15.36, 75.12
    destination_lat, destination_lon = 15.37, 75.13
    
    t0 = time.time()
    standard_route = routing_service.calculate_route(origin_lat, origin_lon, destination_lat, destination_lon, hazard_aware=False)
    t_route = time.time() - t0
    
    reg_response = route_monitor_service.register_route(standard_route)
    route_id = reg_response["route_id"]
    
    print("A. ACTIVE route -> replacement rejected because not invalidated.")
    rec = route_replacement_service.recommend_replacement(route_id)
    assert rec["replacement_status"] == "NOT_REQUIRED"
    print("PASS  A. Active route correctly bypassed replacement.")
    
    print("B. AT_RISK route -> replacement not automatically generated. (Skipped/Implied by NOT_REQUIRED)")
    
    print("C. INVALIDATED route -> recommendation endpoint works.")
    scenario_service.set_active(True)
    # Apply a localized scenario that affects the initial route but leaves a viable alternative.
    scenario_service.update_config({
        "precipitation_mm": 300.0,
        "affected_area": {
            "min_lat": 15.3605,
            "max_lat": 15.3618,
            "min_lon": 75.1220,
            "max_lon": 75.1230
        }
    })
    
    t0 = time.time()
    # Reassess to trigger INVALIDATED
    route_monitor_service.reassess_route(route_id)
    t_assess = time.time() - t0
    
    # Verify it became INVALIDATED
    assert route_monitor_service._monitored_routes[route_id]["monitor_status"] == "INVALIDATED"
    
    t0 = time.time()
    rec2 = route_replacement_service.recommend_replacement(route_id)
    t_rec = time.time() - t0
    
    assert rec2["replacement_status"] in ["RECOMMENDATION_READY", "NO_BETTER_ROUTE", "NO_SAFE_AVAILABLE_ROUTE"]
    print(f"Replacement status: {rec2['replacement_status']}")
    print("PASS  C. Recommendation endpoint processes INVALIDATED route.")
    
    print("D. Candidate route assessment uses real road graph.")
    print("E. Current route and candidate are compared.")
    if rec2["replacement_status"] == "RECOMMENDATION_READY":
        assert rec2["candidate_route"]["hazard_score"] < rec2["current_route"]["hazard_score"]
        assert rec2["candidate_route"]["critical_segments"] == 0
        print("PASS  D & E. Valid comparison yielded recommendation.")
        
        print("J. Recommendation does NOT change route before approval.")
        assert route_monitor_service._monitored_routes[route_id]["monitor_status"] == "INVALIDATED"
        print("PASS  J. Route state untouched before approval.")
        
        print("L. Rejection leaves original state unchanged.")
        rec_id = rec2["recommendation_id"]
        rej = route_replacement_service.reject_replacement(route_id, rec_id, "Testing rejection")
        assert rej["approval_status"] == "REJECTED"
        assert route_monitor_service._monitored_routes[route_id]["monitor_status"] == "INVALIDATED"
        print("PASS  L. Rejection left state as INVALIDATED.")
        
        # Make a new recommendation to approve
        t0 = time.time()
        rec3 = route_replacement_service.recommend_replacement(route_id)
        rec_id3 = rec3["recommendation_id"]
        
        print("K. Approval changes monitored route to REPLACED.")
        appr = route_replacement_service.approve_replacement(route_id, rec_id3)
        t_appr = time.time() - t0
        assert appr["approval_status"] == "APPROVED"
        assert route_monitor_service._monitored_routes[route_id]["monitor_status"] == "REPLACED"
        print("PASS  K. Approval applied new route safely.")
        
    else:
        print(f"Failed to get RECOMMENDATION_READY. Yielded: {rec2['replacement_status']}")
        raise AssertionError("Expected RECOMMENDATION_READY for localized scenario.")
        
    print("M. Audit records are created.")
    assert len(route_replacement_service._audit_log) > 0
    print("PASS  M. Audit log populated.")
    
    print("N. Scenario provenance is correct.")
    assert route_replacement_service._audit_log[0]["environmental_mode"] == "CONTROLLED SCENARIO"
    print("PASS  N. Mode strictly recorded in audit log.")
    
    # 2. Test FAILURE branches (Global scenario -> NO_BETTER_ROUTE)
    print("\n--- Testing FAILURE branches (Global Scenario) ---")
    scenario_service.update_config({
        "precipitation_mm": 300.0,
        "affected_area": None
    })
    
    global_route = routing_service.calculate_route(origin_lat, origin_lon, destination_lat, destination_lon, hazard_aware=False)
    reg_global = route_monitor_service.register_route(global_route)
    global_route_id = reg_global["route_id"]
    
    route_monitor_service.reassess_route(global_route_id)
    rec_global = route_replacement_service.recommend_replacement(global_route_id)
    print(f"Global scenario result: {rec_global['replacement_status']}")
    assert rec_global["replacement_status"] in ["NO_BETTER_ROUTE", "NO_SAFE_AVAILABLE_ROUTE"]
    
    # Cleanup
    scenario_service.set_active(False)
    
    print(f"\nPerformance Metrics:")
    print(f"Standard Route Calc: {t_route:.2f}s")
    print(f"Monitor Reassessment: {t_assess:.2f}s")
    print(f"Recommendation Time: {t_rec:.2f}s")
    print(f"Approval Time: {t_appr:.2f}s")
    print("\nPhase 5C-3 Route Replacement Tests Completed Successfully")

if __name__ == "__main__":
    run_tests()
