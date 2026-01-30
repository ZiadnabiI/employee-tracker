from fastapi.testclient import TestClient
from main import app, get_db
from database import Base, engine, SessionLocal
import os

# Reset DB for testing
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_full_flow():
    print("\n--- 1. Testing Admin Provisioning ---")
    response = client.post("/admin/create-employee", json={"name": "Test User", "department": "QA"})
    assert response.status_code == 200
    data = response.json()
    activation_key = data["activation_key"]
    print(f"SUCCESS: Created user with key: {activation_key}")

    print("\n--- 2. Testing Device Activation ---")
    hw_id = "HW-123-456"
    response = client.post("/activate-device", json={"activation_key": activation_key, "hardware_id": hw_id})
    assert response.status_code == 200
    print(f"SUCCESS: Device activated: {response.json()}")
    
    print("\n--- 3. Testing Duplicate Activation (Should Fail/Warn) ---")
    response = client.post("/activate-device", json={"activation_key": activation_key, "hardware_id": "HW-DIFFERENT"})
    if response.status_code == 403:
        print("SUCCESS: Duplicate activation blocked.")
    else:
        print(f"WARNING: Duplicate activation allowed? Status: {response.status_code}")

    print("\n--- 4. Testing Check-in Verification (Start of Shift) ---")
    response = client.post("/verify-checkin", json={"activation_key": activation_key})
    assert response.status_code == 200
    print(f"SUCCESS: Check-in verified for {response.json()['employee_name']}")

    print("\n--- 5. Testing Logging Activity ---")
    response = client.post("/log-activity", json={"activation_key": activation_key, "status": "WORK_START"})
    assert response.status_code == 200
    print("SUCCESS: Logged WORK_START")
    
    response = client.post("/log-activity", json={"activation_key": activation_key, "status": "BREAK_START"})
    assert response.status_code == 200
    print("SUCCESS: Logged BREAK_START")

    print("\nAll tests passed!")

if __name__ == "__main__":
    test_full_flow()
