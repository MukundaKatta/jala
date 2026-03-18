"""CLI for jala."""
import sys, json, argparse
from .core import Jala

def main():
    parser = argparse.ArgumentParser(description="Jala — Smart Irrigation. AI-powered irrigation scheduling using soil moisture and weather forecasting.")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "run", "info"])
    parser.add_argument("--input", "-i", default="")
    args = parser.parse_args()
    instance = Jala()
    if args.command == "status":
        print(json.dumps(instance.get_stats(), indent=2))
    elif args.command == "run":
        print(json.dumps(instance.process(input=args.input or "test"), indent=2, default=str))
    elif args.command == "info":
        print(f"jala v0.1.0 — Jala — Smart Irrigation. AI-powered irrigation scheduling using soil moisture and weather forecasting.")

if __name__ == "__main__":
    main()
