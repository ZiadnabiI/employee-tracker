import requests

# This script simulates a user taking a break to trigger a Slack notification.
# Ensure 'main.py' is running before executing this.

URL = "http://127.0.0.1:8000/log-activity"
activation_key = "KEY-TEST" # We might need a valid key if your DB is empty, but let's try.

# 1. Create a dummy employee first (if DB is empty, log-activity might fail with Unauthorized)
try:
    requests.post("http://127.0.0.1:8000/admin/create-employee", json={"name": "Slack Tester", "department": "QA"})
except:
    pass # Maybe already exists or server down

# 2. Get a valid key (Quick hack: get any key from DB or just use one if you know it)
# For this test, let's create a new one to be sure.
resp = requests.post("http://127.0.0.1:8000/admin/create-employee", json={"name": "Slack Tester", "department": "QA"})
if resp.status_code == 200:
    key = resp.json()["activation_key"]
    print(f"Created Test User with Key: {key}")
    
    # 3. Send Away (This triggers Slack)
    payload = {
        "activation_key": key,
        "status": "Away"
    }
    
    print(f"Sending AWAY event to {URL}...")
    r = requests.post(URL, json=payload)
    
    if r.status_code == 200:
        print("✅ Success! Check your Slack channel now.")
    else:
        print(f"❌ Failed: {r.text}")
else:
    print("❌ Could not create test user. Is server running?")
