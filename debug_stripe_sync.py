
import os
import sys
import stripe
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import update_stripe_usage, Company, Employee
from database import SessionLocal

def test_sync():
    print("--- Starting Stripe Sync Debug ---")
    print(f"Stripe Library Version: {getattr(stripe, '__version__', 'Unknown')}")
    # print(f"Stripe Attributes: {dir(stripe)}")
    if hasattr(stripe, 'SubscriptionItem'):
        print(f"SubscriptionItem Attributes: {dir(stripe.SubscriptionItem)}")
    
    # Check env vars
    sk = os.getenv("STRIPE_SECRET_KEY")
    if not sk:
        print("⚠️  STRIPE_SECRET_KEY not found in environment.")
        sk = input("Please enter your Stripe Secret Key (sk_test_...): ").strip()
        if not sk:
            print("❌ No key provided. Exiting.")
            return

    stripe.api_key = sk
    # Patch main module's variable just in case
    import main
    main.STRIPE_SECRET_KEY = sk
    print(f"✅ Stripe Key set: {sk[:4]}...{sk[-4:]}")

    db = SessionLocal()
    try:
        # 1. Get the first company with a stripe_customer_id
        company = db.query(Company).filter(Company.stripe_customer_id != None).first()
        
        if not company:
            print("❌ No company found with a stripe_customer_id.")
            print("Please register a company and ensure it has a Stripe Customer ID.")
            return

        print(f"Checking Company: {company.name} (ID: {company.id})")
        print(f"Stripe Customer ID: {company.stripe_customer_id}")

        # 2. Count Employees
        count = db.query(Employee).filter(Employee.company_id == company.id).count()
        print(f"Local Employee Count: {count}")

        # 3. Check current Stripe State
        print("Fetching Stripe Subscription...")
        try:
            subs = stripe.Subscription.list(customer=company.stripe_customer_id, status='active', limit=1)
            if not subs.data:
                print("❌ No active subscription found in Stripe for this customer.")
                return
            
            sub = subs.data[0]
            item = sub['items']['data'][0]
            print(f"DEBUG: Item Type: {type(item)}")
            print(f"DEBUG: Item Keys: {item.keys() if hasattr(item, 'keys') else 'No keys'}")
            
            # Try dict access first, then attribute
            current_qty = item.get('quantity') if hasattr(item, 'get') else item.quantity
            print(f"Current Stripe Quantity: {current_qty}")
            
            if current_qty == count:
                print("⚠️ Quantity already matches. I will force an update anyway to test logs.")
            
        except Exception as e:
            print(f"❌ Error fetching Stripe data: {e}")
            return

        # 4. Run the Sync Function
        print(f"\n>>> Running update_stripe_usage({company.id})...")
        update_stripe_usage(company.id, db)
        print("<<< Function completed.")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_sync()
