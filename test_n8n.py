import requests
from database import SessionLocal, Company, Employee
import time

def trigger_webhook():
    session = SessionLocal()
    # Find any employee
    employee = session.query(Employee).first()
    if not employee:
        print("No employee found in DB.")
        return
        
    URL = "http://127.0.0.1:8000/log-activity"
    payload = {
        "activation_key": employee.activation_key,
        "status": "Away"
    }
    
    print(f"\n🚀 Sending AWAY event for {employee.name} to {URL}...")
    try:
        r = requests.post(URL, json=payload)
        print(f"FastAPI Server Response: {r.status_code}")
    except Exception as e:
        print(f"❌ Failed to reach local server: {e}")

if __name__ == "__main__":
    trigger_webhook()
    time.sleep(2)
    print("\nCheck FastAPI logs for 'Slack response: 200' from the n8n webhook")
