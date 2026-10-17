from getpass import getpass
from datetime import datetime, timezone

from app.db.connection import mongo_manager
from app.db.collections import COLLECTION_USERS
from app.core.security import hash_password, verify_password

email = input("Admin email: ").strip().lower()
password = getpass("Enter NEW admin password (minimum 8 characters): ")
confirm = getpass("Confirm NEW admin password: ")

if len(password) < 8:
    print("ERROR: Password must be at least 8 characters.")
    raise SystemExit(1)

if password != confirm:
    print("ERROR: Passwords do not match.")
    raise SystemExit(1)

try:
    db = mongo_manager.connect()
    users = db[COLLECTION_USERS]
    user = users.find_one({"email": email})

    if not user:
        print("ERROR: Admin account not found.")
        raise SystemExit(1)

    if user.get("role") != "admin" or user.get("status") != "ACTIVE":
        print("ERROR: Account is not an active admin. No changes made.")
        raise SystemExit(1)

    new_hash = hash_password(password)

    result = users.update_one(
        {"_id": user["_id"], "role": "admin", "status": "ACTIVE"},
        {"$set": {
            "passwordHash": new_hash,
            "updatedAt": datetime.now(timezone.utc)
        }}
    )

    if result.modified_count == 1:
        print("SUCCESS: Admin password reset.")
        print("Password verification:", verify_password(password, new_hash))
        print("Now log in using this email and your new password.")
    else:
        print("ERROR: Password was not changed. Check the account and retry.")
finally:
    mongo_manager.close()
