#!/usr/bin/env python3
"""One-off cross-account internal Gmail reply-to-sent QA; never contact prospects."""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from deploy_locked_n8n import api, pages

HOST="https://auto.exampleabc.com"
PATH="exampleabc-qa5-owned-accounts-reply-6b3aac7142de48118b35c93fa91b6218"
NAME="ExampleABC QA5 - Self-Owned Cross-Account Thread Reply"
FILE="ExampleABC_QA5_Cross_Account_Thread_Reply.json"
def bind():
    w=json.loads(Path(FILE).read_text())
    if w.get("active") is not False or w.get("name")!=NAME or len(w.get("nodes",[]))!=13:
        raise RuntimeError("Unexpected QA5 workflow source.")
    sn=[n for n in w["nodes"] if n["type"]=="n8n-nodes-base.gmail"]
    if len(sn)!=2 or {n["parameters"].get("operation") for n in sn}!={"send","reply"}:
        raise RuntimeError("QA5 must have exactly one internal send and one reply.")
    source_code=next(n["parameters"]["jsCode"] for n in w["nodes"] if n["name"]=="Generate One Internal Cross-Account Message")
    if "'hakpilot@gmail.com'" not in source_code:
        raise RuntimeError("QA5 destination not user's personal account.")
    for n in w["nodes"]:
        if n["type"]=="n8n-nodes-base.googleSheets" and n["parameters"]["sheetName"]["value"]!="Automation QA":
            raise RuntimeError("QA5 cannot modify any prospect spreadsheet data.")
        if n["type"]=="n8n-nodes-base.httpRequest":
            raise RuntimeError("QA5 unapproved HTTP node.")
        if n["type"]=="n8n-nodes-base.webhook" and n["parameters"]["path"]!=PATH:
            raise RuntimeError("QA5 webhook path mismatch.")
    sources={
        "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA"),
        "gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only")
    }
    for typ,(wf_id,node_name) in sources.items():
        trusted=api("GET","/workflows/"+wf_id)
        source=[n for n in trusted["nodes"] if n["name"]==node_name]
        if len(source)!=1: raise RuntimeError("Known working QA source missing.")
        ref=source[0].get("credentials",{}).get(typ,{})
        if not ref.get("id") or not ref.get("name"): raise RuntimeError("Missing approved credential reference.")
        if typ=="googleSheetsOAuth2Api" and ref["name"]!="ExampleABC Google Sheets":
            raise RuntimeError("Unexpected Google Sheets credential")
        if typ=="gmailOAuth2" and ref["name"] not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Unexpected Gmail credential")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):
                n["credentials"][typ]={"id":ref["id"],"name":ref["name"]}
    token=hashlib.sha256(("ExampleABC-QA5-Original-Thread-v1:"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    g=next(n for n in w["nodes"] if n["name"]=="QA5 Signature Gate")
    code=g["parameters"]["jsCode"]
    if "__INJECT_QA5_TOKEN__" not in code: raise RuntimeError("QA5 auth guard missing.")
    g["parameters"]["jsCode"]=code.replace("__INJECT_QA5_TOKEN__",token)
    return w,token

def call_webhook(token):
    request=urllib.request.Request(HOST+"/webhook/"+PATH,data=b"{}",method="POST",
        headers={"Content-Type":"application/json","X-ExampleABC-QA-Token":token})
    try:
        with urllib.request.urlopen(request,timeout=35) as resp:
            if resp.status>=300: raise RuntimeError("QA5 webhook failed HTTP 2xx check.")
    except urllib.error.HTTPError as exc:
        raise RuntimeError("QA5 webhook returned HTTP "+str(exc.code)) from None

def get_runs(wfid):
    return api("GET","/executions?workflowId="+urllib.parse.quote(str(wfid))+"&limit=10").get("data",[])

def main():
    w,token=bind()
    existing=[x for x in pages("/workflows") if x.get("name")==NAME]
    if len(existing)>1: raise RuntimeError("Duplicate QA5 workflows.")
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    if existing:
        id=str(existing[0]["id"])
        old=api("GET","/workflows/"+id)
        if old.get("active") or old.get("isActive"): raise RuntimeError("QA5 already active.")
        api("PUT","/workflows/"+id,payload)
    else:
        id=str(api("POST","/workflows",payload)["id"])
    saved=api("GET","/workflows/"+id)
    if len(saved.get("nodes",[]))!=13: raise RuntimeError("QA5 persisted node mismatch.")
    previously={str(x["id"]) for x in get_runs(id)}
    activated=False
    try:
        api("POST","/workflows/"+id+"/activate")
        activated=True
        call_webhook(token)
        print("QA5 accepted one signed internal Original -> Reply test request.")
        deadline=time.monotonic()+90
        found=None
        while time.monotonic()<deadline:
            new=[x for x in get_runs(id) if str(x["id"]) not in previously]
            if new:
                found=new[0]
                if found.get("status") in ("success","error","crashed","canceled"): break
            time.sleep(4)
        if not found: raise RuntimeError("QA5 execution not visible; inspect Gmail before retry.")
        if found.get("status")!="success":
            raise RuntimeError("QA5 execution was "+str(found.get("status"))+" ID="+str(found["id"])+"; DO NOT RETRY before checking personal Gmail.")
        details=api("GET","/executions/"+str(found["id"])+"?includeData=true")
        run=details.get("data",{}).get("resultData",{}).get("runData",{})
        count={k:len(run.get(k,[])) for k in ["Send Original to Personal Account","Reply to Original Sent Message","Log QA5 Thread Reply Result"]}
        if any(x!=1 for x in count.values()):
            raise RuntimeError("QA5 execution incomplete: "+str(count))
        print("QA5 passed n8n node execution: one initial cross-account email, one Gmail Reply, and one QA row update.")
        print("QA5 workflow: "+HOST+"/workflow/"+id)
        print("QA5 execution ID: "+str(found["id"]))
        print("Check Gmail Sent to verify reply recipient is the personal account and thread matches.")
    finally:
        if activated:
            try:
                api("POST","/workflows/"+id+"/deactivate")
                print("QA5 deactivated after test.")
            except Exception:
                raise RuntimeError("CRITICAL: Could not deactivate internal QA5; disable it manually.")

if __name__=="__main__":
    try: main()
    except Exception as exc:
        import sys
        print("SAFE QA5 STOPPED: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
