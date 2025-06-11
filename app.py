import argparse
import json
import requests
import sys

def load_json(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(path) as f:
        return json.load(f)

def main():
    p = argparse.ArgumentParser(description="Invoke MCP server tools via HTTP")
    p.add_argument("tool", choices=["get_token","mcid_search","submit_medical","all"])
    p.add_argument("--url", default="http://localhost:8000", help="Base server URL")
    p.add_argument("--body", help="Path to JSON file or '-' for stdin")
    args = p.parse_args()

    endpoint = f"{args.url.rstrip('/')}/tool/{args.tool}"
    if args.tool in ["mcid_search","submit_medical"]:
        if not args.body:
            p.error(f"--body is required for {args.tool}")
        payload = load_json(args.body)
    else:
        payload = {}

    r = requests.post(endpoint, json=payload)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))

if __name__ == "__main__":
    main()
