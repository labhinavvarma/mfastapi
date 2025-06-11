
# mcp_cli_client.py
"""
Simple command-line client for Milliman MCP server.

Usage:
  python mcp_cli_client.py [--url BASE_URL] TOOL [--body BODY_JSON]

Examples:
  python mcp_cli_client.py get_token
  python mcp_cli_client.py all
  python mcp_cli_client.py mcid_search --body mcid.json
  python mcp_cli_client.py submit_medical --body medical.json
  cat mcid.json | python mcp_cli_client.py mcid_search --url http://server:8000 --body -
"""
import argparse
import json
import requests
import sys

def load_json(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="CLI client for Milliman MCP server tools"
    )
    parser.add_argument(
        '--url', '-u',
        default='http://localhost:8000',
        help='Base URL of the MCP server (default: http://localhost:8000)'
    )
    parser.add_argument(
        'tool',
        choices=['get_token', 'mcid_search', 'submit_medical', 'all'],
        help='Name of the tool to invoke'
    )
    parser.add_argument(
        '--body', '-b',
        help='Path to JSON file for tool body, or "-" to read from stdin'
    )
    args = parser.parse_args()

    # Determine endpoint URL
    endpoint = f"{args.url.rstrip('/')}/tool/{args.tool}"

    # Prepare payload
    if args.tool in ['get_token', 'all']:
        payload = {}
    else:
        if not args.body:
            parser.error(f"--body is required for tool '{args.tool}'")
        try:
            payload = load_json(args.body)
        except Exception as e:
            print(f"Error loading JSON body: {e}", file=sys.stderr)
            sys.exit(1)

    # Invoke
    try:
        resp = requests.post(endpoint, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Pretty-print result
    try:
        data = resp.json()
        print(json.dumps(data, indent=2))
    except ValueError:
        print(resp.text)

if __name__ == '__main__':
    main()
