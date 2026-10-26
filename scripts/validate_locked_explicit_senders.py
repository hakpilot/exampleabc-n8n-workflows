#!/usr/bin/env python3
"""Offline validation of safely locked ExampleABC explicit Gmail API sender workflows.

This script never reads a key, invokes n8n, sends mail or updates spreadsheets.
"""
import json
import subprocess
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, "scripts")
from deploy_locked_n8n import validate_locked

FILES = {
    "ExampleABC_Batch06_FINAL_REVIEW_SENDING_LOCKED.json": (27, 0),
    "ExampleABC_Batch34_Followups_THREAD_REPLIES_LOCKED.json": (26, 1),
    "ExampleABC_Batch05_Followups_THREAD_REPLIES_LOCKED.json": (26, 1),
}

for filename, (expected_count, expected_gets) in FILES.items():
    wf=json.loads(Path(filename).read_text())
    validate_locked(wf)
    nodes=wf["nodes"]
    assert wf["active"] is False and len(nodes)==expected_count, filename
    sends=[n for n in nodes if n["type"]=="n8n-nodes-base.httpRequest" and n["parameters"].get("method")=="POST"]
    gets=[n for n in nodes if n["type"]=="n8n-nodes-base.httpRequest" and n["parameters"].get("method")=="GET"]
    assert len(sends)==1 and len(gets)==expected_gets, filename
    assert sends[0].get("disabled") is True, filename
    assert all(n.get("disabled") is True for n in nodes
               if n["type"]=="n8n-nodes-base.googleSheets" and n["parameters"].get("operation")=="update"),filename
    assert not any(n["type"]=="n8n-nodes-base.gmail" and n["parameters"].get("operation") in ("send","reply")
                   for n in nodes),filename
    assert all(n.get("credentials",{}).get("gmailOAuth2",{}).get("name")=="hyder@exampleabc.com"
               for n in sends+gets),filename
    body="\n".join(n["parameters"]["jsCode"] for n in nodes if n["type"]=="n8n-nodes-base.code")
    assert "From: Hyder Khan <'+from+'>'" in body
    assert "To: '+to" in body
    assert "hyder@exampleabc.com" in body
    if expected_gets:
        assert "In-Reply-To" in body and "References:" in body and "orig_thread_id" in body
    for n in nodes:
        if n["type"]!="n8n-nodes-base.code":continue
        # JavaScript Code node may contain top-level returns. Wrap for syntax checking only.
        content="async function n8nCodeNodeMock() {\n"+n["parameters"]["jsCode"]+"\n}\n"
        with tempfile.NamedTemporaryFile("w",suffix=".js",delete=False) as temp:
            temp.write(content)
            tempname=temp.name
        try:
            check=subprocess.run(["node","--check",tempname],capture_output=True,text=True)
            if check.returncode:
                raise RuntimeError("JavaScript syntax: "+filename+" / "+n["name"]+" / "+check.stderr[:400])
        finally:
            Path(tempname).unlink()
    print(f"PASS: {filename}; {expected_count} nodes, exactly one disabled explicit Gmail sender, {expected_gets} metadata reads; Code JS syntax checked.")

for filename in ("scripts/launch_approved_batch06.py","scripts/launch_approved_followups.py","scripts/launch_approved_batch05_followups.py"):
    text=Path(filename).read_text()
    assert "INCIDENT_20261026_SENDER_SAFETY_HOLD" in text
    assert "raise RuntimeError('SAFETY HOLD:" in text
    print("SAFE HOLD: "+filename)
print("No prospect messaging or API calls occurred.")
