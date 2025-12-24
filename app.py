from flask import Flask, request, jsonify
import requests
import json
import time
import threading
from queue import Queue
from byte import Encrypt_ID, encrypt_api

app = Flask(__name__)

# Region-wise base URLs
REGION_URLS = {
    "bd": "https://clientbp.ggblueshark.com/RequestAddingFriend",
    "ind": "https://client.ind.freefiremobile.com/RequestAddingFriend"
}

REGION_TOKENS = {
    "bd": "token_bd.json",
    "ind": "token_ind.json"
}

# Task queue
task_queue = Queue()

def load_tokens(token_file):
    try:
        with open(token_file, "r") as f:
            data = json.load(f)
        return [item["token"] for item in data]
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return []

def send_friend_request(uid, token, url, results):
    encrypted_id = Encrypt_ID(uid)
    payload = f"08a7c4839f1e10{encrypted_id}1801"
    encrypted_payload = encrypt_api(payload)

    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB51",
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": "16",
        'User-Agent': "ART/2.2.0 (Linux; U; Android 14; SAMSUNG_S25 Build/UP1A.240905.001)",
        "Host": "clientbp.ggblueshark.com",
        "Connection": "close",
        "Accept-Encoding": "gzip, deflate, br"
    }

    try:
        response = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload))
        if response.status_code == 200:
            results["success"] += 1
        else:
            results["failed"] += 1
    except Exception as e:
        print(f"Request error: {e}")
        results["failed"] += 1

# Worker to process tasks sequentially
def worker():
    while True:
        task = task_queue.get()
        if task is None:
            break
        uid = task['uid']
        region = task['region']
        results = {"success": 0, "failed": 0}

        url = REGION_URLS[region]
        tokens = load_tokens(REGION_TOKENS[region])

        for token in tokens[:110]:
            send_friend_request(uid, token, url, results)
            time.sleep(0)  # 2-second delay per request

        task['results'] = results
        task['done'] = True
        task_queue.task_done()

# Start background worker thread
threading.Thread(target=worker, daemon=True).start()

@app.route("/send_requests", methods=["GET"])
def send_requests():
    uid = request.args.get("uid")
    region = request.args.get("region", "bd").lower()

    if not uid:
        return jsonify({"error": "uid parameter is required"}), 400
    if region not in REGION_URLS:
        return jsonify({"error": "Invalid region. Use 'bd' or 'ind'."}), 400

    # Player info
    try:
        info = requests.get(f"https://jamiinfoapi.vercel.app/player-info?uid={uid}").json()
        player_name = info.get("basicInfo", {}).get("nickname", "Unknown")
    except:
        player_name = "Unknown"

    # Add task to queue
    task = {"uid": uid, "region": region, "done": False}
    task_queue.put(task)

    # Wait until task is done
    while not task.get('done', False):
        time.sleep(0.5)

    results = task['results']
    status = 1 if results["success"] > 0 else 2

    return jsonify({
        "region": region,
        "uid": uid,
        "player_name": player_name,
        "success": results["success"],
        "failed": results["failed"],
        "status": status
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=False)
