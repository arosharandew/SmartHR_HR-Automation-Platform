import sys
import asyncio
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from Login_SignUp.Login_Signup import login, signup
from Orchestrator import Orchestrator

def get_authenticated_user():
    print("=== HR Automation Platform ===\n")
    while True:
        print("1. Login\n2. Signup\n3. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            identifier = input("Email / Phone / User ID: ")
            pwd = input("Password: ")
            res = login(identifier, pwd)
            print(res["message"])
            if res["success"]:
                return res["user"]["user_id"]
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
            print(res["message"])
            if res["success"]:
                print("Auto‑logging in...")
                login_res = login(email, pwd)
                print(login_res["message"])
                if login_res["success"]:
                    return login_res["user"]["user_id"]
        elif choice == "3":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice.\n")

async def main():
    user_id = get_authenticated_user()
    orch = Orchestrator()
    session_id = f"cli_{user_id}_{int(time.time())}"
    print(f"\n✅ Logged in as {user_id}. You can now chat with the HR assistant.")
    print("Type 'exit' to quit.\n")
    while True:
        inp = input("You: ").strip()
        if inp.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if not inp:
            continue
        result = await orch.process(user_id, session_id, inp)
        print(f"Agent: {result['response']}\n")

if __name__ == "__main__":
    asyncio.run(main())