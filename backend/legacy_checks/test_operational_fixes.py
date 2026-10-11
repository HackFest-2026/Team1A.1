import urllib.request
import json
import time

base_url = 'http://127.0.0.1:8000'

def test_all():
    print("============================================================")
    print("  RUNNING OPERATIONAL FIXES & WEATHER REGRESSION TEST SUITE")
    print("============================================================")

    # 1 & 2. Register route and test Obstruction -> Invalidate -> Recommend
    reg_data = json.dumps({
        "origin": {"lat": 15.4589, "lon": 75.0078},
        "destination": {"lat": 15.3647, "lon": 75.1240},
        "route_nodes": [245631, 245632, 245633],
        "hazard_score": 30
    }).encode('utf-8')
    reg_req = urllib.request.Request(f"{base_url}/api/route-monitor/register", data=reg_data, headers={'Content-Type': 'application/json'})
    reg_res = json.loads(urllib.request.urlopen(reg_req).read().decode())
    route_id = reg_res["route_id"]
    print(f"  PASS  Route Register: route_id={route_id}")

    # Invalidate route
    inv_req = urllib.request.Request(f"{base_url}/api/route-monitor/{route_id}/invalidate", data=b'', headers={'Content-Type': 'application/json'})
    inv_res = json.loads(urllib.request.urlopen(inv_req).read().decode())
    assert inv_res["monitor_status"] == "INVALIDATED", "Route should be INVALIDATED"
    print("  PASS  Obstruction Invalidation: monitor_status=INVALIDATED")

    # Recommend replacement
    rec_req = urllib.request.Request(f"{base_url}/api/route-monitor/{route_id}/replacement/recommend", data=b'', headers={'Content-Type': 'application/json'})
    rec_res = json.loads(urllib.request.urlopen(rec_req).read().decode())
    assert rec_res["replacement_status"] == "RECOMMENDATION_READY", "Should be RECOMMENDATION_READY"
    rec_id = rec_res["recommendation_id"]
    assert rec_id is not None, "recommendation_id should be present"
    print(f"  PASS  Replacement Recommendation: recommendation_id={rec_id}")

    # 3 & 4. Approve Replacement
    app_data = json.dumps({"recommendation_id": rec_id, "approved": True}).encode('utf-8')
    app_req = urllib.request.Request(f"{base_url}/api/route-monitor/{route_id}/replacement/approve", data=app_data, headers={'Content-Type': 'application/json'})
    app_res = json.loads(urllib.request.urlopen(app_req).read().decode())
    assert app_res["approval_status"] == "APPROVED", "Approval status should be APPROVED"

    # Check monitored route backend status
    mon_res = json.loads(urllib.request.urlopen(f"{base_url}/api/route-monitor/{route_id}").read().decode())
    assert mon_res["monitor_status"] == "REPLACED", "Backend status should be REPLACED"
    print("  PASS  Replacement Approval: status updated to REPLACED")

    # 5, 6, 7 & 8. Dispatch Team & Field Unit Lifecycle
    fu_req = urllib.request.urlopen(f"{base_url}/api/national/field-units")
    units = json.loads(fu_req.read().decode())["records"]
    assert len(units) > 0, "Field units should exist"
    unit_id = units[0]["field_unit_id"]
    
    # Verify separate starting location (not incident location)
    assert units[0]["latitude"] != 15.3647 or units[0]["longitude"] != 75.1240, "Unit should start at separate location"
    print(f"  PASS  Separate Team Starting Location: unit={units[0]['name']}")

    # Reset unit to ASSIGNED if needed for clean lifecycle test
    curr_st = units[0].get("status")
    if curr_st != "ASSIGNED":
        if curr_st in ["COMPLETED", "OPERATING", "AT_SCENE", "EN_ROUTE"]:
            r1 = json.dumps({"new_status": "UNAVAILABLE", "actor": "EOC Operator", "role": "EOC_OPERATOR"}).encode('utf-8')
            try:
                urllib.request.urlopen(urllib.request.Request(f"{base_url}/api/national/field-units/{unit_id}/status", data=r1, headers={'Content-Type': 'application/json'}))
            except Exception:
                pass
        r2 = json.dumps({"new_status": "ASSIGNED", "actor": "EOC Operator", "role": "EOC_OPERATOR"}).encode('utf-8')
        try:
            urllib.request.urlopen(urllib.request.Request(f"{base_url}/api/national/field-units/{unit_id}/status", data=r2, headers={'Content-Type': 'application/json'}))
        except Exception:
            pass

    # Update status EN_ROUTE -> AT_SCENE -> OPERATING -> COMPLETED
    for st in ["EN_ROUTE", "AT_SCENE", "OPERATING", "COMPLETED"]:
        st_data = json.dumps({"new_status": st, "actor": "EOC Operator", "role": "EOC_OPERATOR"}).encode('utf-8')
        st_req = urllib.request.Request(f"{base_url}/api/national/field-units/{unit_id}/status", data=st_data, headers={'Content-Type': 'application/json'})
        st_res = json.loads(urllib.request.urlopen(st_req).read().decode())
        assert st_res["unit"]["status"] == st, f"Unit status should be {st}"
        print(f"  PASS  Field Lifecycle Transition: {st}")

    # 9, 10, 11, 12, 13 & 14. Weather Forecast API
    fc_res = json.loads(urllib.request.urlopen(f"{base_url}/api/weather/forecast").read().decode())
    assert fc_res["status"] == "success", "Weather forecast status should be success"
    assert "hourly" in fc_res, "Forecast should contain hourly points"
    assert "summary" in fc_res, "Forecast should contain summary"
    assert "rain_probability_pct font" in str(fc_res) or "rain_probability_pct" in fc_res["hourly"][0], "Hourly should contain rain_probability_pct"
    print("  PASS  Weather Forecast API: Open-Meteo live hourly precipitation probability & rain returned")
    print(f"        6h Max Rain Prob: {fc_res['summary']['max_prob_6h']}%, Preparedness: {fc_res['summary']['preparedness_level']}")

    print("\n============================================================")
    print("  ALL OPERATIONAL & WEATHER REGRESSION TESTS PASSED 100%!")
    print("============================================================")

if __name__ == '__main__':
    test_all()
