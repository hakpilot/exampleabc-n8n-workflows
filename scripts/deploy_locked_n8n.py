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
    "ExampleABC_Batch05_Followups_THREAD_REPLIES_LOCKED.json",
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
            url = str(params.get("url", ""))
            method = str(params.get("method", "GET")).upper()
            if (params.get("authentication") != "predefinedCredentialType" or
                    params.get("nodeCredentialType") != "gmailOAuth2" or
                    "gmailOAuth2" not in node.get("credentials", {})):
                raise RuntimeError("HTTP node lacks verified Gmail OAuth credential")
            if method == "POST":
                if url != "https://gmail.googleapis.com/gmail/v1/users/me/messages/send":
                    raise RuntimeError("Unapproved Gmail API write endpoint")
                sends += 1
                if node.get("disabled") is not True:
                    raise RuntimeError("Explicit Gmail API sender MUST remain disabled in locked source")
            elif method == "GET":
                # Only metadata on an original Gmail message, with a fixed official API prefix.
                if not (url.startswith("={{ 'https://gmail.googleapis.com/gmail/v1/users/me/messages/'") and
                        url.endswith(" + '?format=metadata' }}")):
                    raise RuntimeError("Unapproved read-only Gmail API URL expression")
            else:
                raise RuntimeError("Unapproved Gmail API HTTP method")
    if sends == 0:
        raise RuntimeError("No sender found: wrong workflow file?")
    if not workflow.get("connections") or len(workflow["nodes"]) < 10:
        raise RuntimeError("Workflow appears incomplete.")
    return workflow

def main():
    filenames = sys.argv[1:] or sorted(ALLOWED)
    if set(filenames) - ALLOWED:
        raise RuntimeError("Only explicitly whitelisted locked workflows can be deployed.")
    # n8n v2.3.1 Public API does not expose GET /credentials (returns 405).
    # Resolve only from two EXISTING ExampleABC workflows that were already
    # tested successfully. Read-only; never reads credential secret data.
    approved_source_nodes = {
        "googleSheetsOAuth2Api": ("MoW6SECTxE1mNYpxGy7Tc", "Update ONLY Automation QA"),
        "gmailOAuth2": ("ymCruFvw0MQe-jfBKFGxt", "Send QA To SELF Only"),
    }
    wanted = {}
    for typ, (workflow_id, node_name) in approved_source_nodes.items():
        wf = api("GET", "/workflows/" + urllib.parse.quote(workflow_id))
        matching = [n for n in wf.get("nodes", []) if n.get("name") == node_name]
        if len(matching) != 1:
            raise RuntimeError(f"Trusted QA source missing expected node: {node_name}")
        ref = matching[0].get("credentials", {}).get(typ, {})
        if not ref.get("id") or not ref.get("name"):
            raise RuntimeError(f"Trusted QA credential reference absent for {node_name}")
        if typ == "googleSheetsOAuth2Api" and ref["name"] != "ExampleABC Google Sheets":
            raise RuntimeError("QA Sheets credential is NOT the verified ExampleABC account.")
        if typ == "gmailOAuth2" and ref["name"] not in ("hyder@exampleabc.com", "ExampleABC Gmail"):
            raise RuntimeError("QA Gmail credential is NOT an approved ExampleABC identity.")
        wanted[typ] = {"id": ref["id"], "name": ref["name"]}
    workflows = pages("/workflows")
    for filename in filenames:
        source = validate_locked(json.loads(Path(filename).read_text(encoding="utf-8")))
        for node in source["nodes"]:
            for typ, ref in node.get("credentials", {}).items():
                if typ not in CREDENTIAL_TYPES:
                    raise RuntimeError("Unexpected credential type: " + typ)
                if typ not in wanted:
                    raise RuntimeError("Trusted ExampleABC credential not found for " + typ)
                if typ == "googleSheetsOAuth2Api" and ref.get("name") != "ExampleABC Google Sheets":
                    raise RuntimeError("Sheets node references an unauthorized credential name")
                if typ == "gmailOAuth2" and ref.get("name") not in ("hyder@exampleabc.com", "ExampleABC Gmail"):
                    raise RuntimeError("Gmail node references an unauthorized credential name")
                ref.update(wanted[typ])
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
