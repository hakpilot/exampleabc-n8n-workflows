#!/usr/bin/env python3
"""Read-only one-shot n8n Gmail metadata check of existing SELF-ONLY QA13 message."""
import json,os,hashlib,time,urllib.request,urllib.error,sys
from pathlib import Path
from deploy_locked_n8n import api,pages
NAME="ExampleABC QA14 - Read Actual Gmail Headers SELF ONLY"
FILE="ExampleABC_QA14_Actual_Gmail_Metadata_ReadOnly.json"
PATH="exampleabc-qa14-self-only-read-metadata-1576ad0e44524e0eb26f6ff5cd7f0493"
def main():
    w=json.loads(Path(FILE).read_text())
    if w.get("name")!=NAME or w.get("active") is not False or len(w["nodes"])!=5:
        raise RuntimeError("Unexpected QA14 source")
    http=[n for n in w["nodes"] if n["type"]=="n8n-nodes-base.httpRequest"]
    if len(http)!=1 or http[0]["parameters"].get("method")!="GET" or http[0]["parameters"].get("url")!="https://gmail.googleapis.com/gmail/v1/users/me/messages/1a17b0d46939c5cd?format=metadata":
        raise RuntimeError("Only known self-owned message may be retrieved")
    if any(n["type"] in ("n8n-nodes-base.gmail","n8n-nodes-base.googleSheets") for n in w["nodes"]):
        raise RuntimeError("QA14 must have NO send or Sheets nodes")
    trusted=api("GET","/workflows/ymCruFvw0MQe-jfBKFGxt")
    refs=[n for n in trusted["nodes"] if n["name"]=="Send QA To SELF Only"]
    if len(refs)!=1:raise RuntimeError("QA14 trusted OAuth node unavailable")
    ref=refs[0]["credentials"]["gmailOAuth2"]
    if ref["name"] not in ("hyder@exampleabc.com","ExampleABC Gmail"):
        raise RuntimeError("Unauthorized credential")
    http[0]["credentials"]["gmailOAuth2"]={"id":ref["id"],"name":ref["name"]}
    token=hashlib.sha256(("QA14-READ-METADATA:"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    gate=next(n for n in w["nodes"] if n["name"]=="Require QA14 Signature")
    gate["parameters"]["jsCode"]=gate["parameters"]["jsCode"].replace("__QA14_TOKEN__",token)
    if any(x.get("name")==NAME for x in pages("/workflows")):
        raise RuntimeError("QA14 already exists; no repeat")
    ident=str(api("POST","/workflows",{k:w[k] for k in ("name","nodes","connections","settings")})["id"])
    active=False
    try:
        api("POST","/workflows/"+ident+"/activate");active=True
        req=urllib.request.Request("https://auto.exampleabc.com/webhook/"+PATH,method="POST",data=b"{}",
            headers={"Content-Type":"application/json","X-ExampleABC-QA14-Token":token})
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.status>=300:raise RuntimeError("QA14 webhook failed")
        end=time.monotonic()+70;ex=None
        while time.monotonic()<end:
            runs=api("GET","/executions?workflowId="+ident+"&limit=5")["data"]
            if runs:
                ex=runs[0]
                if ex.get("status") in ("success","error","crashed","canceled"):break
            time.sleep(3)
        if not ex:raise RuntimeError("QA14 not observed; do not repeat")
        full=api("GET","/executions/"+str(ex["id"])+"?includeData=true")
        data=full.get("data",{}).get("resultData",{})
        if ex["status"]!="success":
            err=data.get("error") or {}
            raise RuntimeError("QA14 failure "+str(data.get("lastNodeExecuted"))+": "+str(err.get("message") or "")[:300])
        audit=data.get("runData",{}).get("Verify RFC822 From To Cc Bcc",[])
        if len(audit)!=1:raise RuntimeError("QA14 verifier missing")
        values=audit[0]["data"]["main"][0][0]["json"]
        if values.get("status")!="PASS" or not all(values.get(k) is True for k in ("verified_business_sender","sole_personal_recipient","has_no_cc_bcc")):
            raise RuntimeError("QA14 headers did not pass")
        print("QA14 PASS: Real n8n Gmail HTTP GET metadata confirmed exact self-only From and To, no Cc/Bcc")
    finally:
        if active:
            api("POST","/workflows/"+ident+"/deactivate")
            print("QA14 read-only webhook deactivated.")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("QA14 STOP: "+str(e),file=sys.stderr);raise SystemExit(1)
