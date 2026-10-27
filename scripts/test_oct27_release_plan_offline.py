#!/usr/bin/env python3
"""Zero-network dry-run validation of the October 27 one-time releases."""
import os,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,"scripts")
import launch_scheduled_initial_oct27 as plan
os.environ["N8N_API_KEY"]="DUMMY_KEY_NO_NETWORK_TEST_ONLY"
def no_network_api(method,path):
    assert method=="GET","Unapproved API write in offline test"
    data={
      "/workflows/ymCruFvw0MQe-jfBKFGxt":{"nodes":[{"name":"Send QA To SELF Only","credentials":{"gmailOAuth2":{"id":"DUMMY_GMAIL","name":"hyder@exampleabc.com"}}}]},
      "/workflows/MoW6SECTxE1mNYpxGy7Tc":{"nodes":[{"name":"Update ONLY Automation QA","credentials":{"googleSheetsOAuth2Api":{"id":"DUMMY_SHEETS","name":"ExampleABC Google Sheets"}}}]}
    }
    if path not in data:raise RuntimeError("Unanticipated API endpoint "+path)
    return data[path]
plan.api=no_network_api
for b in plan.BATCHES:
    approved={"batch_id":b["batch"],"expected_count":20,
              "id_first":b["id_first"],"id_last":b["id_last"],
              "recipients_hash":"0123abcd","content_hash":"9b93ca2f"}
    w,token=plan.build_release(b,approved)
    assert w["active"] is False and len(w["nodes"])==28
    assert len(token)==64
    n={x["name"]:x for x in w["nodes"]}
    assert "0123abcd" in n["Prepare Queue and Gmail Search"]["parameters"]["jsCode"]
    assert "9b93ca2f" in n["Prepare Queue and Gmail Search"]["parameters"]["jsCode"]
    assert "hyder@exampleabc.com" in n["Build Strict ExampleABC Initial MIME"]["parameters"]["jsCode"]
    assert b["approval"] in n["Require exact batch approval"]["parameters"]["jsCode"]
    sends=[x for x in w["nodes"] if x["type"]=="n8n-nodes-base.httpRequest"]
    assert len(sends)==1 and sends[0]["parameters"]["method"]=="POST"
    assert sends[0]["parameters"]["url"]==plan.GMAIL_URL
    assert sends[0]["credentials"]["gmailOAuth2"]["name"]=="hyder@exampleabc.com"
    assert sends[0]["disabled"] is False
    assert not any(x["type"]=="n8n-nodes-base.gmail" and x["parameters"].get("operation") in ("send","reply") for x in w["nodes"])
    writes=[x for x in w["nodes"] if x["type"]=="n8n-nodes-base.googleSheets" and x["parameters"].get("operation")=="update"]
    assert len(writes)==5 and all(x["disabled"] is False for x in writes)
    assert len([x for x in w["nodes"] if x["type"]=="n8n-nodes-base.webhook"])==1
    for node in w["nodes"]:
        if node["type"]!="n8n-nodes-base.code":continue
        script="async function nodeRunner(){\n"+node["parameters"]["jsCode"]+"\n}\n"
        with tempfile.NamedTemporaryFile(mode="w",suffix=".js",delete=False) as f:
            f.write(script);name=f.name
        try:
            p=subprocess.run(["node","--check",name],capture_output=True,text=True)
            if p.returncode:raise RuntimeError("Code syntax in "+b["key"]+" / "+node["name"]+": "+p.stderr[:500])
        finally:Path(name).unlink()
    print("PASS",b["key"],"28 nodes, one explicit sender, 5 writebacks, signed gate, exact-recipient hash, JS syntax")
print("PASS: No live n8n API calls, no prospect emails sent, no Sheets writes.")
