import urllib.request
import urllib.error
import json

def trigger_collect():
    url = "http://127.0.0.1:8080/api/collect/monthly"
    data = json.dumps({"max_urls_per_domain": 2}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    
    print(f"Triggering collection at {url}...")
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            status = response.getcode()
            res_body = response.read().decode('utf-8')
            print(f"Status: {status}")
            print(f"Response: {json.dumps(json.loads(res_body), indent=2, ensure_ascii=False)}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Body: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    trigger_collect()
