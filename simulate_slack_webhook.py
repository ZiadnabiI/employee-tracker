import requests
from database import SessionLocal, Company, Employee
import time

def setup_test_webhook():
    session = SessionLocal()
    
    # Check if we have a company we can use
    company = session.query(Company).first()
    if not company:
        company = Company(name="Test Webhook Company")
        session.add(company)
        session.commit()
        session.refresh(company)
        
    old_webhook = company.slack_webhook_url
    
    # We will use httpbin to inspect the payload
    # Or just a mock URL that we can verify is called
    test_webhook_url = "https://httpbin.org/post"
    company.slack_webhook_url = test_webhook_url
    session.commit()
    
    # Ensure we have an employee for this company
    employee = session.query(Employee).filter(Employee.company_id == company.id).first()
    if not employee:
        employee = Employee(name="Test User", activation_key="HOOK-TEST-123", company_id=company.id)
        session.add(employee)
        session.commit()
        session.refresh(employee)
        
    print(f"✅ Setup: Webhook for Company '{company.name}' temporarily set to {test_webhook_url}")
    print(f"✅ Setup: Using Employee '{employee.name}' with key '{employee.activation_key}'")
    
    return employee.activation_key, company.id, old_webhook

def trigger_webhook(activation_key):
    URL = "http://127.0.0.1:8000/log-activity"
    payload = {
        "activation_key": activation_key,
        "status": "Away"
    }
    
    print(f"\n🚀 Sending AWAY event to {URL}...")
    try:
        r = requests.post(URL, json=payload)
        print(f"Server Response: {r.status_code}")
        if r.status_code == 200:
            print("Event logged successfully. The server should trigger the webhook in the background.")
        else:
            print(f"❌ Server Error: {r.text}")
    except Exception as e:
        print(f"❌ Failed to reach local server: {e}")

def restore_webhook(company_id, old_webhook):
    session = SessionLocal()
    company = session.query(Company).filter(Company.id == company_id).first()
    if company:
        company.slack_webhook_url = old_webhook
        session.commit()
        print(f"\n✅ Restored: Webhook URL reverted to original state.")

if __name__ == "__main__":
    key, comp_id, old_url = setup_test_webhook()
    trigger_webhook(key)
    
    # Wait a moment for background thread to execute
    time.sleep(2)
    
    restore_webhook(comp_id, old_url)
    print("\nCheck your FastAPI server terminal logs! You should see 'Slack response: 200'")
