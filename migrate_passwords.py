"""
Password Migration Script for PR #3 (SHA-256 -> bcrypt)

This script rehashes existing passwords with bcrypt by setting temporary passwords
that you can share with your users.

Run this ONCE after deploying PR #3.

Usage:
    python migrate_passwords.py
"""
import os
import sys
import secrets
import string

# Set a temporary SECRET_KEY for migration if not set
if not os.getenv("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "temp-migration-key-will-not-be-used"

from database import SessionLocal, Supervisor, Employee
from auth import hash_password

def generate_temp_password():
    """Generate a readable temporary password"""
    # 8 characters: mix of letters and digits, easy to read
    chars = string.ascii_letters + string.digits
    # Avoid confusing characters like 0/O, 1/l
    chars = chars.replace('0', '').replace('O', '').replace('l', '').replace('1', '')
    return ''.join(secrets.choice(chars) for _ in range(10))

def migrate_passwords():
    """
    Migration strategy:
    - Generate new temporary passwords for users with old SHA-256 hashes
    - Hash them with bcrypt
    - Print the credentials so admin can share with users
    """
    session = SessionLocal()
    
    try:
        # Get all supervisors with old password hashes
        supervisors = session.query(Supervisor).filter(
            Supervisor.password_hash.isnot(None)
        ).all()
        
        print(f"\n📋 Found {len(supervisors)} supervisors with passwords")
        
        credentials_to_share = []
        
        for sup in supervisors:
            # Check if already bcrypt (starts with $2b$)
            if sup.password_hash and sup.password_hash.startswith('$2b$'):
                print(f"  ⏭️  {sup.email} - Already bcrypt, skipping")
                continue
            
            # Old SHA-256 hash detected - generate new password
            temp_password = generate_temp_password()
            sup.password_hash = hash_password(temp_password)
            
            credentials_to_share.append({
                'type': 'Supervisor',
                'email': sup.email,
                'name': sup.name,
                'temp_password': temp_password
            })
            
            print(f"  🔄 {sup.email} - New temporary password generated")
        
        # Also check employees (if they have passwords)
        employees = session.query(Employee).filter(
            Employee.password_hash.isnot(None)
        ).all()
        
        print(f"\n📋 Found {len(employees)} employees with passwords")
        
        for emp in employees:
            if emp.password_hash and emp.password_hash.startswith('$2b$'):
                print(f"  ⏭️  {emp.name} - Already bcrypt, skipping")
                continue
            
            temp_password = generate_temp_password()
            emp.password_hash = hash_password(temp_password)
            
            credentials_to_share.append({
                'type': 'Employee',
                'email': emp.email,
                'name': emp.name,
                'temp_password': temp_password
            })
            
            print(f"  🔄 {emp.name} - New temporary password generated")
        
        if credentials_to_share:
            print("\n" + "=" * 60)
            print("⚠️  NEW TEMPORARY CREDENTIALS - SAVE THESE!")
            print("=" * 60)
            
            for cred in credentials_to_share:
                print(f"\n  {cred['type']}: {cred['name']}")
                print(f"  Email: {cred['email']}")
                print(f"  Temp Password: {cred['temp_password']}")
            
            print("\n" + "=" * 60)
            confirm = input(f"\n⚠️  Apply these {len(credentials_to_share)} new passwords? (yes/no): ")
            if confirm.lower() != 'yes':
                print("❌ Migration cancelled")
                session.rollback()
                return
            
            session.commit()
            
            # Print again after commit for easy copy
            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETE - SHARE THESE WITH YOUR USERS:")
            print("=" * 60)
            for cred in credentials_to_share:
                print(f"\n{cred['type']}: {cred['email']}")
                print(f"Password: {cred['temp_password']}")
            print("\n" + "=" * 60)
            print("⚠️  Users should change their password after logging in!")
            
        else:
            print("\n✅ No migration needed - all passwords already bcrypt or empty")
            
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def show_status():
    """Show current password hash status without making changes"""
    session = SessionLocal()
    
    try:
        supervisors = session.query(Supervisor).all()
        print("\n📊 Supervisor Password Status:")
        print("-" * 50)
        
        for sup in supervisors:
            if not sup.password_hash:
                status = "❌ No password set"
            elif sup.password_hash.startswith('$2b$'):
                status = "✅ bcrypt"
            else:
                status = "⚠️  SHA-256 (needs migration)"
            
            print(f"  {sup.email}: {status}")
        
        employees = session.query(Employee).filter(
            Employee.password_hash.isnot(None)
        ).all()
        
        if employees:
            print("\n📊 Employee Password Status:")
            print("-" * 50)
            for emp in employees:
                if emp.password_hash.startswith('$2b$'):
                    status = "✅ bcrypt"
                else:
                    status = "⚠️  SHA-256 (needs migration)"
                print(f"  {emp.name}: {status}")
                
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        show_status()
    else:
        print("=" * 60)
        print("PASSWORD MIGRATION: SHA-256 → bcrypt")
        print("=" * 60)
        show_status()
        print("\n" + "=" * 60)
        migrate_passwords()
