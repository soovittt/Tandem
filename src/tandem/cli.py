"""
Terminal REPL for talking to the agent -- the pre-UI way to exercise the whole
system end to end. The web app will later replace this front end, calling the
exact same Agent underneath.
"""

from __future__ import annotations

from tandem.agent.approval import ConsoleApproval
from tandem.app import build_agent


def main() -> None:
    agent = build_agent(approval=ConsoleApproval())
    print("Tandem — your private brain. Type a message; Ctrl-C or Ctrl-D to exit.")

    while True:
        try:
            user_text = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return

        if not user_text:
            continue

        response = agent.send(user_text)
        print(f"\ntandem > {response.text}")
        if response.sources:
            print("\nsources:")
            for source in response.sources:
                print(f"  - {source.title}: {source.url}")


if __name__ == "__main__":
    main()
