#!/usr/bin/env python3
"""Launch the EXACT user-approved Batch06 only once from a signed webhook.

Never run this script until the user explicitly reviews and approves all 20
recipients and the spreadsheet Batch06 Control is updated to APPROVE BATCH 06.
Source files remain locked. This runner creates a separate one-time workflow,
safely verifies its steps, then always deactivates it.
"""
import hashlib,json,os,sys,time,urllib.parse,urllib.request
from pathlib import Path
from deploy_locked_n8n import api,pages,validate_locked

HOST="https://auto.exampleabc.com"
SOURCE="ExampleABC_Batch06_FINAL_REVIEW_SENDING_LOCKED.json"
REQUEST="release_requests/Batch06_Approved.json"
NAME="ExampleABC - Batch06 RELEASE - ONE TIME"
PATH="exampleabc-batch06-release-6147c25ec61a45a5b8446257de0c3a2f"

def inspect_request():
    r=json.loads(Path(REQUEST).read_text())
    if r.get("batch")!="BATCH06-20261022" or r.get("approved") is not True:
        raise RuntimeError("No explicit Batch06 approval request on file.")
    if r.get("expected_count")!=20 or r.get("approval_phrase")!="I APPROVE BATCH 06: SEND 20 INITIAL EMAILS":
        raise RuntimeError("Explicit user approval phrase or count is missing.")
    fingerprint=r.get("contact_fingerprint","")
    if len(fingerprint)!=8 or any(c not in "0123456789abcdef" for c in fingerprint):
        raise RuntimeError("Reviewed 20-recipient fingerprint is invalid.")
    return r

def build(request):
    w=validate_locked(json.loads(Path(SOURCE).read_text()))
    if len(w["nodes"])!=26:
        raise RuntimeError("Expected 26 verified Batch06 nodes.")
    if w["name"]!="ExampleABC - Batch06 FINAL REVIEW - SENDING LOCKED":
        raise RuntimeError("Wrong locked source.")
    sensitive=[]
    for n in w["nodes"]:
        op=n.get("parameters",{}).get("operation")
        if n["type"]=="n8n-nodes-base.gmail" and op in ("send","reply"):
            sensitive.append(n)
            if op!="send" or n["name"]!="Gmail Send Approved Initial Only":
                raise RuntimeError("Unexpected Gmail send operation")
        if n["type"]=="n8n-nodes-base.googleSheets" and op in ("update","append","appendOrUpdate"):
            sensitive.append(n)
    if len(sensitive)!=6 or any(n.get("disabled") is not True for n in sensitive):
        raise RuntimeError("Incorrect or unlocked source action nodes.")
    if any(n["type"] in ("n8n-nodes-base.scheduleTrigger","n8n-nodes-base.httpRequest") for n in w["nodes"]):
        raise RuntimeError("Unapproved trigger or HTTP access.")
    original=[n for n in w["nodes"] if n["name"]=="MANUAL Execute only - no schedule"]
    if len(original)!=1 or original[0]["type"]!="n8n-nodes-base.manualTrigger":
        raise RuntimeError("Wrong original trigger.")
    key=os.environ["N8N_API_KEY"]
    token=hashlib.sha256(("ExampleABC-Approved-Batch06-v1:"+key).encode()).hexdigest()
    trigger=original[0]
    trigger["name"]="Approved Batch06 Signed Webhook"
    trigger["type"]="n8n-nodes-base.webhook"
    trigger["typeVersion"]=2.1
    trigger["parameters"]={"httpMethod":"POST","path":PATH,"responseMode":"onReceived","options":{}}
    trigger["webhookId"]="415ec5e6-9c8a-4ce1-88b2-d899cf69a81c"
    guard={"id":"signed-batch06-auth","name":"Require Batch06 Release Signature","type":"n8n-nodes-base.code",
           "typeVersion":2,"position":[250,300],"parameters":{"mode":"runOnceForAllItems",
           "jsCode":"const h=$input.first().json.headers||{};if(h['x-exampleabc-release-token']!=='"+token+"')throw Error('Unauthorized batch release');return [{json:{authorized:true}}];"}}
    w["nodes"].append(guard)
    w["connections"]["Approved Batch06 Signed Webhook"]={"main":[[{"node":guard["name"],"type":"main","index":0}]]}
    w["connections"][guard["name"]]={"main":[[{"node":"Read Batch06 Control","type":"main","index":0}]]}
    w["connections"].pop("MANUAL Execute only - no schedule",None)

    p=[n for n in w["nodes"] if n["name"]=="Prepare Queue and Gmail Search"]
    if len(p)!=1:raise RuntimeError("Recipient preflight Code node missing.")
    code=p[0]["parameters"]["jsCode"]
    tag="const gmail_query="
    if tag not in code:raise RuntimeError("Cannot insert reviewed-recipient fingerprint check")
    sha=request["contact_fingerprint"]
    extra="""
function fnv32(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16).padStart(8,'0');}
const reviewed=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()).join('\\n'));
if(reviewed!=='%s')throw Error('Batch06 recipients differ from the user-reviewed 20-contact list; do NOT send.');
""" % sha
    p[0]["parameters"]["jsCode"]=code.replace(tag,extra+"\n"+tag,1)
    for n in sensitive:n["disabled"]=False

    credential_sources={
        "gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
        "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA"),
    }
    for typ,(trusted_workflow,source_node) in credential_sources.items():
        t=api("GET","/workflows/"+trusted_workflow)
        nodes=[n for n in t["nodes"] if n["name"]==source_node]
        if len(nodes)!=1:raise RuntimeError("Trusted credential source missing")
        cred=nodes[0]["credentials"][typ]
        if not cred.get("id"):raise RuntimeError("Approved credential ID missing")
        if typ=="gmailOAuth2" and cred.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Wrong Gmail account")
        if typ=="googleSheetsOAuth2Api" and cred.get("name")!="ExampleABC Google Sheets":
            raise RuntimeError("Wrong Google Sheets account")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):
                n["credentials"][typ]={"id":cred["id"],"name":cred["name"]}
    w["name"]=NAME
    return w,token

def call_webhook(token):
    req=urllib.request.Request(HOST+"/webhook/"+PATH,data=b"{}",method="POST",
        headers={"Content-Type":"application/json","X-ExampleABC-Release-Token":token})
    try:
        with urllib.request.urlopen(req,timeout=35) as response:
            if response.status>=300:raise RuntimeError("Release webhook refused.")
    except urllib.error.HTTPError as err:
        raise RuntimeError("Release webhook HTTP "+str(err.code)) from None

def get_execs(wfid):
    return api("GET","/executions?workflowId="+urllib.parse.quote(str(wfid))+"&limit=10").get("data",[])

def main():
    request=inspect_request()
    if any(x.get("name")==NAME for x in pages("/workflows")):
        raise RuntimeError("Release workflow already exists; refusing to create a duplicate or resend.")
    wf,token=build(request)
    payload={k:wf[k] for k in ("name","nodes","connections","settings")}
    release=api("POST","/workflows",payload)
    wfid=str(release["id"])
    saved=api("GET","/workflows/"+wfid)
    if len(saved.get("nodes",[]))!=27 or saved.get("active"):
        raise RuntimeError("Persisted release workflow does not match 27-node inactive source.")
    old={str(x["id"]) for x in get_execs(wfid)}
    active=False
    print("Authorized 20-recipient workflow saved; awaiting sheet's independent single-use batch approval gate.")
    print("Release review URL: "+HOST+"/workflow/"+wfid)
    try:
        api("POST","/workflows/"+wfid+"/activate")
        active=True
        call_webhook(token)
        print("One signed batch release request accepted by n8n. No retry is permitted.")
        deadline=time.monotonic()+520
        result=None
        while time.monotonic()<deadline:
            fresh=[x for x in get_execs(wfid) if str(x["id"]) not in old]
            if fresh:
                result=fresh[0]
                if result.get("status") in ("success","error","crashed","canceled"):
                    break
            time.sleep(5)
        if not result:
            raise RuntimeError("Release execution unseen or timed out; MUST reconcile Gmail Sent and Send Log before action.")
        status=result.get("status")
        if status!="success":
            raise RuntimeError("Release halted with "+str(status)+"; execution ID "+str(result.get("id"))+". DO NOT RETRY; reconcile any partial Gmail sends.")
        detail=api("GET","/executions/"+str(result["id"])+"?includeData=true")
        data=detail.get("data",{}).get("resultData",{}).get("runData",{})
        names=["Gmail Send Approved Initial Only","Log Gmail ID first - SEND LEDGER","Update original Prospect sent status","Update original Email Draft sent status"]
        counts={name:len(data.get(name,[])) for name in names}
        if any(x!=20 for x in counts.values()):
            raise RuntimeError("Release incomplete despite success; expected twenty runs each, got "+str(counts))
        if len(data.get("Mark Batch06 COMPLETE",[]))!=1:
            raise RuntimeError("Batch06 completion flag was not written")
        print("BATCH06 SUCCESS: Exactly 20 Gmail sends, 20 Gmail IDs logged, 20 Prospect and 20 Draft updates; batch marked COMPLETE.")
        print("Production execution ID: "+str(result["id"]))
    finally:
        if active:
            try:
                api("POST","/workflows/"+wfid+"/deactivate")
                print("Production release webhook deactivated after single execution.")
            except Exception:
                raise RuntimeError("CRITICAL: One-time release could not be deactivated. Disable it in n8n immediately.")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("BATCH06 RELEASE STOPPED: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
