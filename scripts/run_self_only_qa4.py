#!/usr/bin/env python3
"""Execute exactly TWO internal ExampleABC self-test Gmail messages through n8n.

Reads N8N_API_KEY from GitHub Actions secret; never prints keys or auth tokens.
Creates a manual-review-independent, temporarily active, signed webhook QA workflow.
Never executes, enables, or changes live prospect outreach workflows.
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from deploy_locked_n8n import api, pages

ROOT = "https://auto.exampleabc.com"
WORKFLOW = "ExampleABC_QA4_Self_Only_2_Emails.json"
NAME = "ExampleABC QA4 - AUTHORIZED Self-Only Loop 2"
TARGET = "hyder@exampleabc.com"
WEBHOOK_PATH = "exampleabc-20261023-self-only-qa4-4d2d5f3af6b54eb6b1254dcbd70f2801"

def validate_and_bind():
    source = json.loads(Path(WORKFLOW).read_text(encoding="utf8"))
    if source["name"] != NAME or source.get("active") is not False:
        raise RuntimeError("Wrong QA file or active source.")
    nodes = source["nodes"]
    webhooks = [n for n in nodes if n["type"] == "n8n-nodes-base.webhook"]
    sends = [n for n in nodes if n["type"] == "n8n-nodes-base.gmail" and n.get("parameters", {}).get("operation") == "send"]
    sheets = [n for n in nodes if n["type"] == "n8n-nodes-base.googleSheets"]
    if len(webhooks) != 1 or webhooks[0]["parameters"].get("path") != WEBHOOK_PATH:
        raise RuntimeError("Webhook QA path mismatch")
    if len(sends) != 1 or sends[0]["name"] != "Send QA to Self":
        raise RuntimeError("Unexpected QA Gmail send nodes")
    if len(sheets) != 3 or any(n["parameters"]["sheetName"]["value"] != "Automation QA" for n in sheets):
        raise RuntimeError("QA source must ONLY read/write Automation QA tab")
    if TARGET not in next(n["parameters"]["jsCode"] for n in nodes if n["name"] == "Prepare Exactly TWO Self Messages"):
        raise RuntimeError("QA self-recipient missing.")
    if any(n["type"] == "n8n-nodes-base.httpRequest" for n in nodes):
        raise RuntimeError("Unapproved HTTP request node")
    if "__INJECT_QA_TOKEN__" not in next(n["parameters"]["jsCode"] for n in nodes if n["name"] == "Require Secure QA Request"):
        raise RuntimeError("QA authentication token template absent")

    creds = {
        "gmailOAuth2": ("ymCruFvw0MQe-jfBKFGxt", "Send QA To SELF Only"),
        "googleSheetsOAuth2Api": ("MoW6SECTxE1mNYpxGy7Tc", "Update ONLY Automation QA"),
    }
    for typ, (source_id, source_node) in creds.items():
        trusted = api("GET", "/workflows/" + source_id)
        matching = [n for n in trusted["nodes"] if n["name"] == source_node]
        if len(matching) != 1:
            raise RuntimeError("Trusted QA workflow node not found: " + source_node)
        ref = matching[0].get("credentials", {}).get(typ, {})
        if not ref.get("id") or not ref.get("name"):
            raise RuntimeError("Trusted QA credential ID/name missing")
        if typ == "gmailOAuth2" and ref["name"] not in ("hyder@exampleabc.com", "ExampleABC Gmail"):
            raise RuntimeError("Unexpected Gmail credential name")
        if typ == "googleSheetsOAuth2Api" and ref["name"] != "ExampleABC Google Sheets":
            raise RuntimeError("Unexpected Google Sheets credential name")
        for node in nodes:
            if typ in node.get("credentials", {}):
                node["credentials"][typ] = {"id":ref["id"], "name":ref["name"]}

    key = os.environ["N8N_API_KEY"]
    token = hashlib.sha256(("ExampleABC-SelfQA4-v1:" + key).encode()).hexdigest()
    guard = next(n for n in nodes if n["name"] == "Require Secure QA Request")
    guard["parameters"]["jsCode"] = guard["parameters"]["jsCode"].replace("__INJECT_QA_TOKEN__", token)
    return source, token

def trigger(token):
    req = urllib.request.Request(
        ROOT + "/webhook/" + WEBHOOK_PATH,
        data=b'{}', method="POST",
        headers={"Content-Type":"application/json","X-ExampleABC-QA-Token":token}
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            if resp.status >= 300:
                raise RuntimeError("Webhook did not return a 2xx response")
    except urllib.error.HTTPError as e:
        raise RuntimeError("QA webhook returned HTTP "+str(e.code)) from None

def executions(workflow_id):
    data = api("GET", "/executions?workflowId="+urllib.parse.quote(str(workflow_id))+"&limit=10")
    return data.get("data", [])

def main():
    source,token = validate_and_bind()
    live = [w for w in pages("/workflows") if w.get("name") == NAME]
    if len(live)>1:
        raise RuntimeError("Multiple QA4 workflows exist. Stopping.")
    payload = {k:source[k] for k in ("name","nodes","connections","settings")}
    if live:
        workflow_id = str(live[0]["id"])
        before = api("GET","/workflows/"+workflow_id)
        if before.get("active") or before.get("isActive"):
            raise RuntimeError("QA4 already active, refusing overwrite")
        api("PUT","/workflows/"+workflow_id,payload)
    else:
        created = api("POST","/workflows",payload)
        workflow_id = str(created["id"])
    verified=api("GET","/workflows/"+workflow_id)
    if len(verified.get("nodes",[])) != 14:
        raise RuntimeError("Persisted QA4 node count mismatch")
    old_ids={str(x["id"]) for x in executions(workflow_id)}
    print("QA4 installed and verified; token protected; two recipients limited to the owner's ExampleABC mailbox.")
    activated=False
    try:
        api("POST","/workflows/"+workflow_id+"/activate")
        activated=True
        print("QA4 activated temporarily for one signed webhook request.")
        trigger(token)
        print("QA4 webhook accepted. Checking one new n8n execution.")
        deadline=time.monotonic()+100
        outcome=None
        while time.monotonic() < deadline:
            fresh=[x for x in executions(workflow_id) if str(x.get("id")) not in old_ids]
            if fresh:
                outcome=fresh[0]
                if outcome.get("status") in ("success","error","crashed","canceled","waiting"):
                    break
            time.sleep(4)
        if not outcome:
            raise RuntimeError("QA4 execution not visible within timeout. Check Gmail before retry.")
        status=outcome.get("status")
        if status!="success":
            raise RuntimeError("QA4 execution status "+str(status)+"; inspect "+str(outcome.get("id"))+"; do NOT retry before reconciling.")
        details=api("GET","/executions/"+str(outcome["id"])+"?includeData=true")
        runs=details.get("data",{}).get("resultData",{}).get("runData",{})
        ns=len(runs.get("Send QA to Self",[]))
        nl=len(runs.get("Write Confirmed QA Send to QA Row",[]))
        if ns!=2 or nl!=2:
            raise RuntimeError("QA4 incomplete: Gmail send runs="+str(ns)+"; Sheets update runs="+str(nl)+"; do NOT retry.")
        print("QA4 PASS: two self-only Gmail send executions and two Automation QA writeback executions.")
        print("n8n QA4 URL: "+ROOT+"/workflow/"+workflow_id)
        print("Execution ID: "+str(outcome["id"]))
    finally:
        if activated:
            try:
                api("POST","/workflows/"+workflow_id+"/deactivate")
                print("QA4 deactivated after controlled test.")
            except Exception:
                raise RuntimeError("URGENT: QA4 deactivation failed. Disable it immediately in n8n.")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        import sys
        print("SAFE QA4 STOPPED: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
