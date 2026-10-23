#!/usr/bin/env python3
"""Deploy only preapproved, hard-locked ExampleABC n8n workflows via public API.

Requires N8N_API_KEY in environment (e.g. GitHub Actions secret).
NO execution, activation, credential creation, or API key printing.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://auto.exampleabc.com"
ROOT = HOST + "/api/v1"
ALLOWED = {
    "ExampleABC_Batch06_FINAL_REVIEW_SENDING_LOCKED.json",
    "ExampleABC_Batch34_Followups_THREAD_REPLIES_LOCKED.json",
}
SENSITIVE_GMAIL = {"send", "reply", "sendAndWait"}
SENSITIVE_SHEETS = {"append", "appendOrUpdate", "update", "delete", "clear", "create", "upsert"}
CREDENTIAL_TYPES = {"gmailOAuth2", "googleSheetsOAuth2Api"}

def api(method, path, body=None):
    key = os.environ["N8N_API_KEY"]
    if not key or len(key) < 12:
        raise RuntimeError("N8N_API_KEY secret missing/invalid.")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        ROOT + path, data=data, method=method,
        headers={"X-N8N-API-KEY": key, "Accept": "application/json",
                 "Content-Type": "application/json", "User-Agent": "ExampleABC-safe-deployer/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.load(r)
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"n8n Public API returned HTTP {err.code} for {method} {path}. "
                           "Verify API key permissions and API availability.") from None

def pages(path):
    rows, cursor = [], None
    for _ in range(10):
        q = ("&cursor=" + urllib.parse.quote(cursor)) if cursor else ""
        data = api("GET", path + ("&" if "?" in path else "?") + "limit=100" + q)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise RuntimeError("Unexpected n8n API paginated response")
        rows += data["data"]
        cursor = data.get("nextCursor")
        if not cursor: break
    else:
        raise RuntimeError("Pagination unexpectedly exceeded ten pages")
    return rows

def validate_locked(workflow):
    if not workflow["name"].endswith("LOCKED"):
        raise RuntimeError("Only workflows ending in LOCKED may be deployed.")
    if workflow.get("active") not in (False, None):
        raise RuntimeError("Deployment refused: source workflow active=true.")
    sends = 0
    for node in workflow["nodes"]:
        typ = node["type"]
        params = node.get("parameters", {})
        op = params.get("operation", "")
        if typ == "n8n-nodes-base.gmail" and op in SENSITIVE_GMAIL:
            sends += 1
            if node.get("disabled") is not True:
                raise RuntimeError("Unsafe Gmail action not disabled: " + node["name"])
        if typ == "n8n-nodes-base.googleSheets" and op in SENSITIVE_SHEETS:
            if node.get("disabled") is not True:
                raise RuntimeError("Unsafe Sheets write not disabled: " + node["name"])
        if typ == "n8n-nodes-base.httpRequest":
            raise RuntimeError("HTTP request node prohibited in locked deployment.")
    if sends == 0:
        raise RuntimeError("No sender found: wrong workflow file?")
    if not workflow.get("connections") or len(workflow["nodes"]) < 10:
        raise RuntimeError("Workflow appears incomplete.")
    return workflow

def main():
    filenames = sys.argv[1:] or sorted(ALLOWED)
    if set(filenames) - ALLOWED:
        raise RuntimeError("Only explicitly whitelisted locked workflows can be deployed.")
    creds = pages("/credentials")
    wanted = {}
    for c in creds:
        if c.get("type") in CREDENTIAL_TYPES:
            wanted[(c.get("type"), c.get("name"))] = c["id"]
    if not wanted:
        raise RuntimeError("Credential listing empty. Need API credential:list scope.")
    workflows = pages("/workflows")
    for filename in filenames:
        source = validate_locked(json.loads(Path(filename).read_text(encoding="utf-8")))
        for node in source["nodes"]:
            for typ, ref in node.get("credentials", {}).items():
                if typ not in CREDENTIAL_TYPES:
                    raise RuntimeError("Unexpected credential type: " + typ)
                key = (typ, ref.get("name"))
                if key not in wanted:
                    raise RuntimeError(f"Missing authorized credential: {key[1]} ({typ}). "
                                       "No fallback to Jafaria credentials permitted.")
                ref["id"] = wanted[key]
        matches = [x for x in workflows if x.get("name") == source["name"]]
        if len(matches) > 1:
            raise RuntimeError("Ambiguous existing workflows with same name; abort")
        payload = {k:source[k] for k in ("name", "nodes", "connections", "settings")}
        if matches:
            wf_id = matches[0]["id"]
            current = api("GET", "/workflows/" + urllib.parse.quote(str(wf_id)))
            if current.get("active") or current.get("isActive"):
                raise RuntimeError("Existing workflow is active/published; refusing update")
            updated = api("PUT", "/workflows/" + urllib.parse.quote(str(wf_id)), payload)
        else:
            updated = api("POST", "/workflows", payload)
            wf_id = updated["id"]
        actual = api("GET", "/workflows/" + urllib.parse.quote(str(wf_id)))
        if len(actual.get("nodes", [])) != len(source["nodes"]):
            raise RuntimeError("Persisted workflow node count mismatch")
        validate_locked(actual)
        print(f"LOCKED workflow deployed and verified: {actual['name']} ({len(actual['nodes'])} nodes)")
        print("Review in n8n: " + HOST + "/workflow/" + str(wf_id))
    print("No workflow was executed, activated, or used to send messages.")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print("SAFE DEPLOYMENT STOPPED: " + str(e), file=sys.stderr)
        raise SystemExit(1)
