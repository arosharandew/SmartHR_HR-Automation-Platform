import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.Orchestrator import Orchestrator

def main():
    print("Loading agent...")
    orch = Orchestrator()
    print("\n📞 Hybrid Call Assistant ready. Ask anything (type 'exit' to quit).\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        answer = orch.answer(user_input)
        print(f"\n🤖 {answer}\n")
        print("-" * 60)

if __name__ == "__main__":
    main()