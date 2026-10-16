"""
Initial Government Admin Bootstrap CLI Utility.

Creates the initial administrative officer account in the users collection.
Enforces password hashing, input validation, and audit recording.
No default password or public registration endpoint is permitted.
"""

import sys
import getpass
import argparse
import re
from datetime import datetime, timezone
from pymongo.database import Database

from app.config import settings
from app.db.connection import mongo_manager, DatabaseConnectionError
from app.db.collections import COLLECTION_USERS, COLLECTION_AUDIT_LOGS
from app.core.security import hash_password

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


def bootstrap_admin(
    email: str,
    name: str,
    employee_id: str,
    password: str,
    department: str = "Traffic Enforcement HQ",
    rank: str = "Assistant Commissioner of Police",
    db: Database = None,
) -> dict:
    """
    Validates and provisions the initial administrative officer account.
    """
    email_clean = email.strip().lower()
    if not re.match(EMAIL_REGEX, email_clean):
        raise ValueError(f"Invalid email address format: '{email}'")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long for government admin accounts.")

    emp_clean = employee_id.strip().upper()
    name_clean = name.strip()

    target_db = db if db is not None else mongo_manager.connect()

    users_col = target_db[COLLECTION_USERS]

    # Check for existing user collision
    existing = users_col.find_one({"$or": [{"email": email_clean}, {"employeeId": emp_clean}]})
    if existing:
        raise ValueError(
            f"User with email '{email_clean}' or employee ID '{emp_clean}' already exists in system records."
        )

    now = datetime.now(timezone.utc)
    hashed_pwd = hash_password(password)

    user_doc = {
        "employeeId": emp_clean,
        "name": name_clean,
        "email": email_clean,
        "passwordHash": hashed_pwd,
        "role": "admin",
        "department": department,
        "rank": rank,
        "status": "ACTIVE",
        "lastLoginAt": None,
        "createdAt": now,
        "updatedAt": now,
    }

    result = users_col.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Log bootstrap event in audit_logs
    audit_col = target_db[COLLECTION_AUDIT_LOGS]
    audit_doc = {
        "timestamp": now,
        "actorUserId": result.inserted_id,
        "actorNameSnapshot": name_clean,
        "actorRoleSnapshot": "admin",
        "action": "ADMIN_BOOTSTRAP_PROVISIONED",
        "entityType": "user",
        "entityId": user_id,
        "notes": f"Initial government administrator account provisioned via secure CLI utility.",
        "metadata": {
            "email": email_clean,
            "employeeId": emp_clean,
            "department": department,
        },
        "requestId": "CLI_BOOTSTRAP",
    }
    audit_col.insert_one(audit_doc)

    return {
        "id": user_id,
        "employeeId": emp_clean,
        "name": name_clean,
        "email": email_clean,
        "role": "admin",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TrafficGuard AI — Initial Government Administrator Bootstrap CLI"
    )
    parser.add_argument("--email", type=str, help="Official admin email (e.g. admin@traffic.gov.in)")
    parser.add_argument("--name", type=str, help="Full name of administrator")
    parser.add_argument("--employee-id", type=str, help="Unique employee code (e.g. TG-ADM-001)")
    parser.add_argument("--password", type=str, help="Password (prompted securely if omitted)")
    parser.add_argument("--department", type=str, default="Traffic Enforcement Central Command")
    parser.add_argument("--rank", type=str, default="Deputy Commissioner of Police")

    args = parser.parse_args()

    print("=" * 70)
    print("  TrafficGuard AI — Secure Administrator Bootstrap Utility")
    print("=" * 70)

    try:
        email = args.email or input("Enter Administrator Email: ").strip()
        name = args.name or input("Enter Full Name: ").strip()
        emp_id = args.employee_id or input("Enter Employee ID (e.g. TG-ADM-001): ").strip()

        if args.password:
            password = args.password
        else:
            password = getpass.getpass("Enter Secure Password (min 8 chars): ")
            confirm = getpass.getpass("Confirm Password: ")
            if password != confirm:
                print("\n[ERROR] Passwords do not match.")
                return 1

        print("\nProvisioning administrator account...")
        res = bootstrap_admin(
            email=email,
            name=name,
            employee_id=emp_id,
            password=password,
            department=args.department,
            rank=args.rank,
        )

        print("\n[SUCCESS] Administrator successfully provisioned!")
        print(f"  ID:          {res['id']}")
        print(f"  Employee ID: {res['employeeId']}")
        print(f"  Name:        {res['name']}")
        print(f"  Email:       {res['email']}")
        print(f"  Role:        admin (Active)")
        print("\nYou can now authenticate via POST /api/v1/auth/login")
        return 0

    except (ValueError, DatabaseConnectionError) as err:
        print(f"\n[ERROR] Provisioning aborted: {err}")
        return 1
    except Exception as exc:
        print(f"\n[FATAL] Unexpected error during bootstrap: {exc}")
        return 1
    finally:
        mongo_manager.close()


if __name__ == "__main__":
    sys.exit(main())
