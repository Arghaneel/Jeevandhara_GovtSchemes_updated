"""End-to-end check of the Jeevandhara API.

Start the backend first (python backend/main.py), then run:
    python scratch/test_api_flow.py
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def call(path, method="GET", body=None):
    """Return (status_code, json_body) without raising on 4xx/5xx."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8") or "null")


def check(condition, message):
    if not condition:
        print(f"   FAILED: {message}")
        sys.exit(1)


def test_api():
    print("=== STARTING API FLOW INTEGRATION TEST ===")

    try:
        status, home = call("/")
    except urllib.error.URLError:
        print(f"Backend is not running at {BASE_URL}. Start it with: python backend/main.py")
        sys.exit(1)
    print("0. Status:", status, home)

    # 1. Register (409 means the user exists from an earlier run, which is fine)
    farmer = {
        "username": "ramesh_farmer",
        "password": "securepassword123",
        "name": "Ramesh Kumar",
        "age": 38,
        "income": 75000.0,
        "land_size": 1.8,  # acres
        "state": "Punjab",
        "district": "Amritsar",
    }
    status, response = call("/register", "POST", farmer)
    print("1. Registration:", status, response)
    check(status in (201, 409), "registration should succeed or report an existing user")

    # 2. Login
    status, response = call("/login", "POST", {"username": "ramesh_farmer", "password": "securepassword123"})
    print("2. Login:", status, response)
    check(status == 200 and response.get("status") == "success", "login failed")
    user_id = response["user_id"]

    status, response = call("/login", "POST", {"username": "ramesh_farmer", "password": "wrong"})
    check(status == 401, "a wrong password must be rejected")

    # 3. Dashboard
    status, response = call(f"/dashboard/{user_id}")
    check(status == 200, "dashboard failed")
    recommendations = response["recommendations"]
    print("\n3. Dashboard:")
    print(f"   Farmer: {response['profile']['name']}, land {response['profile']['land_size']} acres")
    print(f"   Eligible: {recommendations['total_eligible']} of {recommendations['total_schemes']}")
    for scheme in recommendations["eligible_schemes"]:
        print(f"     - {scheme['scheme_name']}: {scheme['title']}")

    # 4. Chatbot (works without Ollama; uses it when it's running)
    for question in ("What is KCC and who can apply?", "Documents required?", "Which schemes am I eligible for?"):
        status, response = call(f"/ask/{user_id}", "POST", {"question": question})
        check(status == 200 and response.get("answer"), f"chatbot failed for: {question}")
        print(f"\n4. Q: {question}  [scheme={response.get('scheme')}, source={response.get('source')}]")
        print("   " + response["answer"][:300].replace("\n", "\n   "))

    # 5. Chat history
    status, response = call(f"/chat-history/{user_id}")
    check(status == 200 and len(response) >= 3, "chat history missing")
    print(f"\n5. Chat history: {len(response)} entries; latest: {response[0]['question']!r}")

    # 6. Unknown user
    status, response = call("/dashboard/999999")
    check(status == 404, "unknown user should return 404")

    print("\n=== ALL API FLOW INTEGRATION TESTS COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    test_api()
