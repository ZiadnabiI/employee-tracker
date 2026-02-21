from database import SessionLocal, Company

session = SessionLocal()
companies = session.query(Company).all()

n8n_url = "https://abdo-alio.app.n8n.cloud/webhook-test/6ca80100-d727-4adb-b2a8-f3b9ea2e052a/webhook"

for c in companies:
    c.slack_webhook_url = n8n_url

session.commit()
print("All companies updated with new n8n webhook URL.")
