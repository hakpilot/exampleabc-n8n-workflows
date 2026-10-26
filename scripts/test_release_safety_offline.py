#!/usr/bin/env python3
"""Offline safety/syntax checks for one-time production release plans. NEVER calls n8n."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,"scripts")
import launch_approved_batch06 as first
import launch_approved_followups as follow
import launch_approved_batch05_followups as batch05

os.environ["N8N_API_KEY"]="OFFLINE_TEST_TOKEN_NO_API_CONNECTION"

def stub(method,path):
    assert method=="GET", "Release plan unit test attempted to write to an API"
    if path.endswith("/ymCruFvw0MQe-jfBKFGxt"):
        return {"nodes":[{"name":"Send QA To SELF Only","credentials":{"gmailOAuth2":{"id":"qa-only-fake-gmail-id","name":"hyder@exampleabc.com"}}}]}
    if path.endswith("/MoW6SECTxE1mNYpxGy7Tc"):
        return {"nodes":[{"name":"Update ONLY Automation QA","credentials":{"googleSheetsOAuth2Api":{"id":"qa-only-fake-sheets-id","name":"ExampleABC Google Sheets"}}}]}
    raise RuntimeError("Unexpected external API request in offline test: "+path)
first.api=stub
follow.api=stub
batch05.api=stub

cases=[
("Batch06",first,{"contact_fingerprint":"0123abcd"},27,"Gmail Send Approved Initial Only",6),
("Followups",follow,{"contact_fingerprint":"0123abcd"},25,"Reply In Original Gmail Thread - DEACTIVATED",5),
("Batch05",batch05,{"contact_fingerprint":"0123abcd"},25,"Reply In Original Gmail Thread - DEACTIVATED",5)
]
for title,module,approval,expected_nodes,send_name,sensitive_count in cases:
    workflow,token=module.build(approval)
    nodes=workflow["nodes"]
    assert len(nodes)==expected_nodes
    assert workflow["name"].endswith("ONE TIME")
    sends=[n for n in nodes if n["type"]=="n8n-nodes-base.gmail" and n.get("parameters",{}).get("operation") in ("send","reply")]
    writes=[n for n in nodes if n["type"]=="n8n-nodes-base.googleSheets" and n.get("parameters",{}).get("operation")=="update"]
    assert len(sends)==1 and sends[0]["name"]==send_name
    assert len(sends+writes)==sensitive_count
    assert all(n.get("disabled") is False for n in sends+writes)
    assert len([n for n in nodes if n["type"]=="n8n-nodes-base.webhook"])==1
    assert len([n for n in nodes if n["type"]=="n8n-nodes-base.manualTrigger"])==0
    assert all(n.get("credentials",{}).get("gmailOAuth2",{}).get("id")!="real" for n in nodes)
    assert any("0123abcd" in n.get("parameters",{}).get("jsCode","") for n in nodes)
    assert len(token)==64
    for node in [n for n in nodes if n["type"]=="n8n-nodes-base.code"]:
        script="async function executeNode(){\n"+node["parameters"]["jsCode"]+"\n}\n"
        with tempfile.NamedTemporaryFile(mode="w",suffix=".js",delete=False) as f:
            f.write(script)
            fn=f.name
        try:
            result=subprocess.run(["node","--check",fn],text=True,capture_output=True)
            if result.returncode:
                raise RuntimeError(title+" JavaScript syntax error in '"+node["name"]+"': "+result.stderr[:900])
        finally:
            Path(fn).unlink()
    print(title+": release planned offline, "+str(len(nodes))+" nodes and all JavaScript passed syntax check. NO API calls or messages.")
print("PASS: No release request files created; no prospect sends attempted.")
