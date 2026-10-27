#!/usr/bin/env python3
"""Run a read-only, signed-webhook Batch07 preflight. No sending, no Sheet writes."""
import hashlib,json,os,time,urllib.parse,urllib.request
from pathlib import Path
from deploy_locked_n8n import api,pages
HOST="https://auto.exampleabc.com"
FILE="ExampleABC_QA15_Batch07_20_Prospect_Preflight_ReadOnly.json"
NAME="ExampleABC QA15 - Batch07 20 Prospect Preflight READ ONLY"
PATH="exampleabc-qa15-batch07-safe-20-preflight-12ea320a2d6c41369a7be1634726c56a"
def main():
    w=json.loads(Path(FILE).read_text())
    if w["name"]!=NAME or w.get("active") is not False or len(w["nodes"])!=13:
        raise RuntimeError("Unexpected QA15 source metadata.")
    for n in w["nodes"]:
        t=n["type"];op=n.get("parameters",{}).get("operation")
        if t=="n8n-nodes-base.gmail" and op!="getAll":raise RuntimeError("QA15 Gmail not read only.")
        if t=="n8n-nodes-base.googleSheets" and op!="read":raise RuntimeError("QA15 Sheet is not read only.")
        if t=="n8n-nodes-base.httpRequest":raise RuntimeError("Unexpected QA15 HTTP node.")
    known={
        "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA"),
        "gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only")
    }
    for typ,(wf,nodeName) in known.items():
        x=api("GET","/workflows/"+wf)
        nodes=[n for n in x["nodes"] if n["name"]==nodeName]
        if len(nodes)!=1:raise RuntimeError("Trusted ExampleABC credential workflow missing.")
        c=nodes[0]["credentials"].get(typ)
        if not c or not c.get("id"):raise RuntimeError("Trusted ExampleABC credential missing ID.")
        if typ=="googleSheetsOAuth2Api" and c.get("name")!="ExampleABC Google Sheets":raise RuntimeError("Wrong Google Sheets account.")
        if typ=="gmailOAuth2" and c.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):raise RuntimeError("Wrong Gmail account.")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):n["credentials"][typ]={"id":c["id"],"name":c["name"]}
    token=hashlib.sha256(("ExampleABC-QA15-READONLY:"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    guard=next(n for n in w["nodes"] if n["name"]=="QA15 Auth Guard")
    if "__QA15_TOKEN__" not in guard["parameters"]["jsCode"]:raise RuntimeError("QA15 token missing.")
    guard["parameters"]["jsCode"]=guard["parameters"]["jsCode"].replace("__QA15_TOKEN__",token)
    matches=[n for n in pages("/workflows") if n.get("name")==NAME]
    if len(matches)>1:raise RuntimeError("Ambiguous QA15 duplicate.")
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    if matches:
        id=str(matches[0]["id"])
        old=api("GET","/workflows/"+id)
        if old.get("active"):raise RuntimeError("QA15 previously active, stop.")
        api("PUT","/workflows/"+id,payload)
    else:id=str(api("POST","/workflows",payload)["id"])
    if len(api("GET","/workflows/"+id)["nodes"])!=13:raise RuntimeError("QA15 saved node count mismatch.")
    previous={str(e["id"]) for e in api("GET","/executions?workflowId="+id+"&limit=10").get("data",[])}
    active=False
    try:
        api("POST","/workflows/"+id+"/activate");active=True
        req=urllib.request.Request(HOST+"/webhook/"+PATH,data=b"{}",method="POST",headers={"Content-Type":"application/json","X-ExampleABC-QA-Token":token})
        try:
            with urllib.request.urlopen(req,timeout=35) as resp:
                if resp.status>=300:raise RuntimeError("Webhook not 2xx")
        except urllib.error.HTTPError as err:
            raise RuntimeError("QA15 webhook HTTP "+str(err.code)) from None
        deadline=time.monotonic()+90
        ex=None
        while time.monotonic()<deadline:
            candidates=[e for e in api("GET","/executions?workflowId="+id+"&limit=10").get("data",[]) if str(e["id"]) not in previous]
            if candidates:
                ex=candidates[0]
                if ex.get("status") in ("success","error","crashed","canceled"):break
            time.sleep(4)
        if not ex:raise RuntimeError("QA15 execution not observed.")
        if ex.get("status")!="success":raise RuntimeError("QA15 failed: "+str(ex.get("status"))+", execution ID "+str(ex["id"]))
        full=api("GET","/executions/"+str(ex["id"])+"?includeData=true")
        runs=full.get("data",{}).get("resultData",{}).get("runData",{})
        last=runs.get("Verify 20 Matches and No Previous Gmail",[])
        if len(last)!=1:raise RuntimeError("QA15 final validation node not executed exactly once")
        results=last[0].get("data",{}).get("main",[[]])[0]
        if len(results)!=1 or results[0].get("json",{}).get("eligible")!=20 or results[0].get("json",{}).get("status")!="QA15_PASS":
            raise RuntimeError("QA15 output did not confirm exactly 20 safe recipients.")
        print("QA15 PASS: Exact production initial-outreach preflight matched 20 candidates and zero existing Gmail conversations.")
        print("QA15 workflow: "+HOST+"/workflow/"+id)
        print("QA15 execution ID: "+str(ex["id"]))
    finally:
        if active:
            try:
                api("POST","/workflows/"+id+"/deactivate")
                print("QA15 deactivated; no Gmail or Sheets write nodes exist in this workflow.")
            except Exception:raise RuntimeError("CRITICAL QA15 failed to deactivate")
if __name__=="__main__":
    try:main()
    except Exception as e:
        import sys
        print("SAFE QA15 STOPPED: "+str(e),file=sys.stderr)
        raise SystemExit(1)
