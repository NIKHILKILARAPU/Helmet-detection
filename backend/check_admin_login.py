from getpass import getpass
from app.db.connection import mongo_manager
from app.db.collections import COLLECTION_USERS
from app.core.security import verify_password

email = input("Admin email: ").strip().lower()
password = getpass("Enter the password to test: ")

try:
    db = mongo_manager.connect()
    user = db[COLLECTION_USERS].find_one({"email": email})

    if not user:
        print("RESULT: Account not found.")
    else:
        print("RESULT: Account found.")
        print("Role:", user.get("role"))
        print("Status:", user.get("status"))
        print("Password matches:", verify_password(
            password, user.get("passwordHash", "")
        ))
finally:
    mongo_manager.close()
