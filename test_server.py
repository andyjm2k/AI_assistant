
import sys
import json

def main():
    for line in sys.stdin:
        try:
            message = json.loads(line.strip())
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"test": "echo"}
            }))
        except:
            pass

if __name__ == "__main__":
    main()
