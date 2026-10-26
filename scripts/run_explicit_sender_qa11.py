#!/usr/bin/env python3
"""ONE self-only Gmail API sendAs experiment. Never addresses a prospect."""
import hashlib,json,os,sys,time,urllib.request,urllib.error
from pathlib import Path
from deploy_locked_n8n import api,pages

NAME="ExampleABC QA11 - Explicit Business SendAs SELF ONLY"
PATH="exampleabc-qa11-sendas-selfonly-a87d1246dbf84bf69011cf14b458a336"
HOST="https://auto.exampleabc.com"
FILE="ExampleABC_QA11_Explicit_Sender_SelfOnly.json"

def run():
    w=json.loads(Path(FILE).read_text())
    if w.get("active") is not False or w.get("name")!=NAME or len(w.get("nodes",[]))!=6:
        raise RuntimeError("QA11 source validation failed")
    h=[n for n in w["nodes"] if n["type"]=="n8n-nodes-base.httpRequest"]
    if len(h)!=1 or h[0]["name"]!="Send Gmail API Self-Only Raw MIME":
        raise RuntimeError("Unexpected external HTTP node")
    params=h[0]["parameters"]
    if params.get("url")!="https://gmail.googleapis.com/gmail/v1/users/me/messages/send" or params.get("method")!="POST" or params.get("nodeCredentialType")!="gmailOAuth2" or params.get("authentication")!="predefinedCredentialType":
        raise RuntimeError("QA11 HTTP endpoint or credential unexpected")
    if any(n["type"] in ("n8n-nodes-base.gmail","n8n-nodes-base.googleSheets") for n in w["nodes"]):
        raise RuntimeError("QA11 cannot contain native send or spreadsheet writes")
    mime=[n for n in w["nodes"] if n["name"]=="Build Exact Self-Only MIME"]
    if len(mime)!=1 or "to='hakpilot@gmail.com'" not in mime[0]["parameters"]["jsCode"] or "from='hyder@exampleabc.com'" not in mime[0]["parameters"]["jsCode"]:
        raise RuntimeError("No verified exact self-test recipient and sender")
    known=api("GET","/workflows/ymCruFvw0MQe-jfBKFGxt")
    target=[n for n in known.get("nodes",[]) if n.get("name")=="Send QA To SELF Only"]
    if len(target)!=1:raise RuntimeError("Known OAuth source not found")
    ref=target[0].get("credentials",{}).get("gmailOAuth2",{})
    if not ref.get("id") or ref.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):
        raise RuntimeError("Incorrect OAuth reference")
    h[0]["credentials"]["gmailOAuth2"]={"id":ref["id"],"name":ref["name"]}
    key=os.environ["N8N_API_KEY"]
    token=hashlib.sha256(("ExampleABC-QA11-SelfOnly-Test:"+key).encode()).hexdigest()
    gate=[n for n in w["nodes"] if n["name"]=="Require Internal QA11 Signature"]
    if len(gate)!=1 or "__QA11_TOKEN__" not in gate[0]["parameters"]["jsCode"]:
        raise RuntimeError("Missing signed webhook authentication")
    gate[0]["parameters"]["jsCode"]=gate[0]["parameters"]["jsCode"].replace("__QA11_TOKEN__",token)
    if any(x.get("name")==NAME for x in pages("/workflows")):
        raise RuntimeError("QA11 already exists: never run self-only send twice.")
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    wid=str(api("POST","/workflows",payload)["id"])
    saved=api("GET","/workflows/"+wid)
    if len(saved.get("nodes",[]))!=6 or saved.get("active"):
        raise RuntimeError("QA11 persisted workflow did not validate")
    active=False
    try:
        api("POST","/workflows/"+wid+"/activate");active=True
        req=urllib.request.Request(HOST+"/webhook/"+PATH,method="POST",data=b"{}",headers={"Content-Type":"application/json","X-ExampleABC-QA11-Token":token})
        try:
            with urllib.request.urlopen(req,timeout=35) as rsp:
                if rsp.status>=300:raise RuntimeError("QA11 webhook error")
        except urllib.error.HTTPError as err:
            raise RuntimeError("QA11 webhook HTTP "+str(err.code)) from None
        end=time.monotonic()+70
        found=None
        while time.monotonic()<end:
            items=api("GET","/executions?workflowId="+wid+"&limit=5").get("data",[])
            if items:
                found=items[0]
                if found.get("status") in ("success","error","crashed","canceled"):break
            time.sleep(3)
        if not found:raise RuntimeError("QA11 execution not visible, inspect Gmail Sent before retry")
        if found.get("status")!="success":
            full=api("GET","/executions/"+str(found["id"])+"?includeData=true")
            result=full.get("data",{}).get("resultData",{})
            err=result.get("error") or {}
            raise RuntimeError("QA11 failed node="+str(result.get("lastNodeExecuted"))+" error="+str(err.get("message") or "")[:500])
        details=api("GET","/executions/"+str(found["id"])+"?includeData=true")
        runs=details.get("data",{}).get("resultData",{}).get("runData",{})
        if len(runs.get("Send Gmail API Self-Only Raw MIME",[]))!=1 or len(runs.get("Require One Gmail Confirmation",[]))!=1:
            raise RuntimeError("QA11 internal send confirmation missing")
        result=runs["Require One Gmail Confirmation"][0]["data"]["main"][0][0]["json"]
        print("QA11 Gmail API accepted exactly one self-only message id:",result.get("id"))
        print("Inspect RFC822 From and To for this message before approving any production operation.")
        print("QA11 workflow URL: "+HOST+"/workflow/"+wid)
    finally:
        if active:
            try:
                api("POST","/workflows/"+wid+"/deactivate")
                print("QA11 one-time webhook deactivated.")
            except Exception:raise RuntimeError("CRITICAL QA11 deactivation failure")
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("QA11 SAFE STOP: "+str(e),file=sys.stderr)
        raise SystemExit(1)
