#!/usr/bin/env python3
"""Exactly one controlled self-only Gmail API send + Sheets writeback; never prospects."""
import hashlib,json,os,sys,time,urllib.request,urllib.error
from pathlib import Path
from deploy_locked_n8n import api,pages
NAME="ExampleABC QA13 - One Self-Only Gmail API Send and Sheet Log"
FILE="ExampleABC_QA13_Gmail_Explicit_Sender_To_Sheets_SelfOnly.json"
PATH="exampleabc-qa13-one-self-only-with-ledger-6530a9100dfb4292a4f94f025f038d24"
HOST="https://auto.exampleabc.com"
def main():
    w=json.loads(Path(FILE).read_text())
    if w.get("name")!=NAME or w.get("active") is not False or len(w.get("nodes",[]))!=10:
        raise RuntimeError("Unexpected QA13 source")
    posts=[n for n in w["nodes"] if n["type"]=="n8n-nodes-base.httpRequest"]
    if len(posts)!=1 or posts[0]["parameters"]["url"]!="https://gmail.googleapis.com/gmail/v1/users/me/messages/send" or posts[0]["parameters"]["method"]!="POST":
        raise RuntimeError("Unsafe HTTP endpoint")
    sheets=[n for n in w["nodes"] if n["type"]=="n8n-nodes-base.googleSheets"]
    if len(sheets)!=3 or any(n["parameters"]["sheetName"]["value"]!="Automation QA" for n in sheets):
        raise RuntimeError("Unexpected Sheet tab")
    mime=[n for n in w["nodes"] if n["name"]=="Build Self-Only ExampleABC MIME"]
    if len(mime)!=1 or "'hyder@exampleabc.com'" not in mime[0]["parameters"]["jsCode"] or "'hakpilot@gmail.com'" not in mime[0]["parameters"]["jsCode"]:
        raise RuntimeError("Missing exact self-only sender/recipient")
    trusted={
       "gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
       "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA"),
    }
    for typ,(wf_id,source_node) in trusted.items():
        old=api("GET","/workflows/"+wf_id)
        matches=[n for n in old["nodes"] if n["name"]==source_node]
        if len(matches)!=1:raise RuntimeError("QA13 trusted credential source missing")
        ref=matches[0].get("credentials",{}).get(typ,{})
        if not ref.get("id"):raise RuntimeError("QA13 credential ID missing")
        if typ=="gmailOAuth2" and ref.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Unexpected Gmail credential name")
        if typ=="googleSheetsOAuth2Api" and ref.get("name")!="ExampleABC Google Sheets":
            raise RuntimeError("Unexpected Sheets credential name")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):
                n["credentials"][typ]={"id":ref["id"],"name":ref["name"]}
    token=hashlib.sha256(("ExampleABC-QA13-selfonly:"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    gate=next(n for n in w["nodes"] if n["name"]=="Require QA13 Signature")
    if "__QA13_TOKEN__" not in gate["parameters"]["jsCode"]:raise RuntimeError("QA13 header guard absent")
    gate["parameters"]["jsCode"]=gate["parameters"]["jsCode"].replace("__QA13_TOKEN__",token)
    if any(x.get("name")==NAME for x in pages("/workflows")):
        raise RuntimeError("QA13 workflow already created, cannot safely execute twice")
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    wid=str(api("POST","/workflows",payload)["id"])
    if len(api("GET","/workflows/"+wid)["nodes"])!=10:raise RuntimeError("Persisted workflow node count mismatch")
    active=False
    try:
        api("POST","/workflows/"+wid+"/activate");active=True
        req=urllib.request.Request(HOST+"/webhook/"+PATH,method="POST",data=b"{}",headers={"Content-Type":"application/json","X-ExampleABC-QA13-Token":token})
        try:
            with urllib.request.urlopen(req,timeout=35) as resp:
                if resp.status>=300:raise RuntimeError("QA13 webhook non-2xx")
        except urllib.error.HTTPError as e:
            raise RuntimeError("QA13 webhook HTTP "+str(e.code)) from None
        end=time.monotonic()+85;out=None
        while time.monotonic()<end:
            rows=api("GET","/executions?workflowId="+wid+"&limit=5").get("data",[])
            if rows:
                out=rows[0]
                if out.get("status") in ("success","error","crashed","canceled"):break
            time.sleep(3)
        if not out:raise RuntimeError("QA13 execution unobserved, do not retry")
        detail=api("GET","/executions/"+str(out["id"])+"?includeData=true")
        rd=detail.get("data",{}).get("resultData",{})
        runs=rd.get("runData",{})
        if out.get("status")!="success":
            err=rd.get("error",{})
            raise RuntimeError("QA13 failed node "+str(rd.get("lastNodeExecuted"))+": "+str(err.get("message") or "")[:350])
        names=["Gmail API Send - QA13 to Personal Mailbox","Confirm API Gmail ID and QA Source","Write QA13 SENT to Automation QA"]
        if any(len(runs.get(n,[]))!=1 for n in names):
            raise RuntimeError("QA13 Gmail and spreadsheet write step counts not 1")
        confirm=runs["Confirm API Gmail ID and QA Source"][0]["data"]["main"][0][0]["json"]
        if confirm.get("Status")!="QA13_SENT" or not confirm.get("Message ID"):
            raise RuntimeError("QA13 Gmail receipt missing")
        print("QA13 PASS: Explicit Gmail API accepted one self-only send and wrote one Google Sheets receipt.")
        print("QA13 Gmail ID:",confirm["Message ID"])
        print("QA13 workflow:",HOST+"/workflow/"+wid)
    finally:
        if active:
            try:
                api("POST","/workflows/"+wid+"/deactivate")
                print("QA13 self-only test webhook deactivated.")
            except Exception:raise RuntimeError("CRITICAL QA13 could not deactivate test workflow")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("QA13 SAFE STOP: "+str(e),file=sys.stderr)
        raise SystemExit(1)
