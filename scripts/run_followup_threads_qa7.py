#!/usr/bin/env python3
"""Read-only verification of 16 already sent ExampleABC Gmail threads in n8n."""
import json,os,hashlib,time,urllib.parse,urllib.request,sys
from pathlib import Path
from deploy_locked_n8n import api,pages
HOST="https://auto.exampleabc.com"
NAME="ExampleABC QA7 - Verify 16 Gmail Threads READ ONLY"
PATH="exampleabc-qa7-readonly-original-threads-89a9d8ae2ec54c1a97483b6839bba17c"
def main():
    w=json.loads(Path("ExampleABC_QA7_Verify16Threads_ReadOnly.json").read_text())
    if w["name"]!=NAME or w.get("active") is not False or len(w["nodes"])!=15:
        raise RuntimeError("Wrong QA7 workflow source")
    for n in w["nodes"]:
        t=n["type"];op=n.get("parameters",{}).get("operation","")
        if t=="n8n-nodes-base.gmail" and op!="get":raise RuntimeError("QA7 Gmail node not READ ONLY")
        if t=="n8n-nodes-base.googleSheets" and op!="read":raise RuntimeError("QA7 Sheet node not READ ONLY")
        if t=="n8n-nodes-base.httpRequest":raise RuntimeError("QA7 HTTP node forbidden")
    refs={
        "gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
        "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA")
    }
    for typ,(trusted_wf, trusted_name) in refs.items():
        source=api("GET","/workflows/"+trusted_wf)
        matched=[n for n in source["nodes"] if n["name"]==trusted_name]
        if len(matched)!=1:raise RuntimeError("Trusted credential source missing "+trusted_name)
        c=matched[0]["credentials"][typ]
        if typ=="gmailOAuth2" and c["name"] not in ("hyder@exampleabc.com","ExampleABC Gmail"):raise RuntimeError("Wrong Gmail identity")
        if typ=="googleSheetsOAuth2Api" and c["name"]!="ExampleABC Google Sheets":raise RuntimeError("Wrong Sheets identity")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):n["credentials"][typ]={"id":c["id"],"name":c["name"]}
    token=hashlib.sha256(("ExampleABC-QA7-readonly:"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    guard=next(n for n in w["nodes"] if n["name"]=="QA7 Auth Guard")
    if "__QA7_TOKEN__" not in guard["parameters"]["jsCode"]:raise RuntimeError("Auth guard missing")
    guard["parameters"]["jsCode"]=guard["parameters"]["jsCode"].replace("__QA7_TOKEN__",token)
    existing=[x for x in pages("/workflows") if x.get("name")==NAME]
    if len(existing)>1:raise RuntimeError("Ambiguous QA7 workflows")
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    if existing:
        id=str(existing[0]["id"])
        if api("GET","/workflows/"+id).get("active"):raise RuntimeError("QA7 already active")
        api("PUT","/workflows/"+id,payload)
    else:id=str(api("POST","/workflows",payload)["id"])
    if len(api("GET","/workflows/"+id).get("nodes",[]))!=15:raise RuntimeError("QA7 persisted node mismatch")
    old_ids={str(x["id"]) for x in api("GET","/executions?workflowId="+id+"&limit=10").get("data",[])}
    active=False
    try:
        api("POST","/workflows/"+id+"/activate");active=True
        request=urllib.request.Request(HOST+"/webhook/"+PATH,data=b"{}",method="POST",headers={"Content-Type":"application/json","X-ExampleABC-QA-Token":token})
        try:
            with urllib.request.urlopen(request,timeout=35) as r:
                if r.status>=300:raise RuntimeError("Webhook failed")
        except urllib.error.HTTPError as e:raise RuntimeError("Webhook HTTP "+str(e.code)) from None
        end=time.monotonic()+110
        run=None
        while time.monotonic()<end:
            n=[x for x in api("GET","/executions?workflowId="+id+"&limit=10").get("data",[]) if str(x["id"]) not in old_ids]
            if n:
                run=n[0]
                if run.get("status") in ("success","error","crashed","canceled"):break
            time.sleep(4)
        if not run:raise RuntimeError("QA7 execution not observed")
        if run.get("status")!="success":
            details=api("GET","/executions/"+str(run["id"])+"?includeData=true")
            result=details.get("data",{}).get("resultData",{})
            e=result.get("error",{})
            node=result.get("lastNodeExecuted","unknown")
            msg=str(e.get("message") or e.get("description") or "No error detail returned")[:600]
            raise RuntimeError("QA7 execution "+str(run["id"])+" status "+str(run.get("status"))+"; failing node="+str(node)+"; error="+msg)
        full=api("GET","/executions/"+str(run["id"])+"?includeData=true")
        data=full.get("data",{}).get("resultData",{}).get("runData",{})
        original_count=len(data.get("Inspect Original Gmail Thread",[]))
        approved_count=len(data.get("Fail Closed on Replies or Additional Messages",[]))
        if original_count!=16 or approved_count!=16 or not data.get("QA7 Read-Only Verification Complete"):
            raise RuntimeError("QA7 read counts failed: originals "+str(original_count)+" checked "+str(approved_count))
        print("QA7 PASS: 16 original Gmail threads fetched and screened against current followup prospect records, 0 sends.")
        print("QA7 workflow: "+HOST+"/workflow/"+id)
        print("QA7 execution ID: "+str(run["id"]))
    finally:
        if active:
            try:
                api("POST","/workflows/"+id+"/deactivate")
                print("QA7 deactivated")
            except Exception:raise RuntimeError("CRITICAL QA7 deactivation failed")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("SAFE QA7 STOPPED: "+str(e),file=sys.stderr)
        raise SystemExit(1)
