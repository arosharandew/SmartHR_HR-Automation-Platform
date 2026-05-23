"""
Login_Signup.py - Handles user authentication using Helper.py.
"""

import re
import bcrypt
from Database.Helper import (
    create_user, get_user_by_email, get_user_by_any, update_last_login,
    get_last_user_id, get_or_create_leave_balance
)

def generate_next_user_id() -> str:
    last_id = get_last_user_id()
    if not last_id:
        return "CD001"
    match = re.search(r"(\d+)$", last_id)
    if not match:
        return "CD001"
    num = int(match.group(1)) + 1
    return f"CD{num:03d}"

def validate_email(email: str) -> bool:
    return re.match(r"^[^@]+@[^@]+\.[^@]+$", email) is not None

def validate_phone(phone: str) -> bool:
    return re.match(r"^07\d{8}$", phone) is not None

def validate_password_strength(password: str) -> bool:
    return len(password) >= 6

def signup(name: str, email: str, password: str, nic: str, phone: str,
           designation: str, department: str) -> dict:
    if not validate_email(email):
        return {"success": False, "message": "Invalid email format. Must contain @ and ."}
    if not validate_phone(phone):
        return {"success": False, "message": "Phone must start with 07 and be exactly 10 digits."}
    if not validate_password_strength(password):
        return {"success": False, "message": "Password must be at least 6 characters."}

    user_id = generate_next_user_id()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    success = create_user(user_id, name.strip(), email.strip(), password_hash,
                          nic.strip(), phone.strip(), designation.strip(), department.strip())
    if not success:
        return {"success": False, "message": "Email already registered."}

    get_or_create_leave_balance(user_id)
    return {"success": True,
            "message": f"Signup successful. Welcome {name}, your user ID is {user_id}!",
            "user_id": user_id}

def login(identifier: str, password: str) -> dict:
    user = get_user_by_any(identifier)  # works with email, phone, or user_id
    if not user:
        return {"success": False, "message": "User not found with that email/phone/user_id."}

    stored_hash = user["password_hash"]
    if bcrypt.checkpw(password.encode(), stored_hash.encode()):
        update_last_login(user["user_id"])
        return {"success": True,
                "message": f"Login successful. Welcome back {user['name']}!",
                "user": user}
    else:
        return {"success": False, "message": "Incorrect password."}

# ---------- CLI for testing (optional) ----------
def main():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    if not Path("Database/hr_platform.db").exists():
        print("❌ Database not found. Run Database/database.py first.")
        return
    print("=== HR Automation Platform ===\n")
    while True:
        print("1. Login\n2. Signup\n3. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            ident = input("Email/Phone/User ID: ")
            pwd = input("Password: ")
            res = login(ident, pwd)
            print(res["message"], "\n")
            if res["success"]:
                print("User details:", res["user"])
                break
        elif choice == "2":
            print("\n--- Signup ---")
            first = input("First name: ")
            last = input("Last name: ")
            name = f"{first} {last}"
            email = input("Email: ")
            pwd = input("Password (min 6 chars): ")
            nic = input("NIC: ")
            phone = input("Phone (07xxxxxxxx): ")
            desig = input("Designation: ")
            dept = input("Department: ")
            res = signup(name, email, pwd, nic, phone, desig, dept)
            print(res["message"], "\n")
            if res["success"]:
                print("Auto‑logging in...")
                login_res = login(email, pwd)
                print(login_res["message"])
                if login_res["success"]:
                    break
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.\n")

if __name__ == "__main__":
    main()