#!/usr/bin/env python3
"""One-time October 27, 2026 ExampleABC INITIAL-outreach release, after 8AM ET.

ONLY sends approved Batch06 and Batch07 through n8n (20 unique contacts each).
Requires independent spreadsheet approval, fixed hashes of reviewed addresses and
draft content, live Gmail duplicate/opt-out guards, strict explicit MIME From/To,
per-message Gmail send log, and single-use signed webhooks. No blind retries.
"""
import hashlib,json,os,sys,time,urllib.parse,urllib.request,urllib.error
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from deploy_locked_n8n import api,pages,validate_locked

HOST="https://auto.exampleabc.com"
TZ=ZoneInfo("America/New_York")
REQUEST="release_requests/oct27_initial_batches.json"
TARGET_DATE="2026-10-27"
BATCHES=[
    {
        "key":"batch06","batch":"BATCH06-20261022","name":"ExampleABC - Batch06 OCT27 RELEASE - ONE TIME",
        "source":"ExampleABC_Batch06_FINAL_REVIEW_SENDING_LOCKED.json",
        "source_name":"ExampleABC - Batch06 FINAL REVIEW - SENDING LOCKED",
        "control":"Batch06 Control","send_log":"Batch06 Send Log","id_first":56,"id_last":75,
        "approval":"APPROVE BATCH 06","webhook":"exampleabc-batch06-oct27-signed-2026-8d429e19a9e142c1",
        "webhook_id":"2f59b845-e695-4f1c-95f0-3bb150e67ad2"
    },
    {
        "key":"batch07","batch":"BATCH07-20261027","name":"ExampleABC - Batch07 OCT27 RELEASE - ONE TIME",
        "source":"ExampleABC_Batch07_FINAL_REVIEW_SENDING_LOCKED.json",
        "source_name":"ExampleABC - Batch07 FINAL REVIEW - SENDING LOCKED",
        "control":"Batch07 Control","send_log":"Batch07 Send Log","id_first":76,"id_last":95,
        "approval":"APPROVE BATCH 07","webhook":"exampleabc-batch07-oct27-signed-2026-3a11592debcf47fa",
        "webhook_id":"b7dd39b4-d9f9-4415-a141-8f508a910cc8"
    }
]
SEND_NODE="Send Explicit ExampleABC Initial via Gmail API - LOCKED"
GMAIL_URL="https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

def schedule_gate():
    now=datetime.now(TZ)
    desired=datetime(2026,10,27,8,0,tzinfo=TZ)
    earliest=desired-timedelta(minutes=10)
    latest=desired+timedelta(minutes=40)
    if now<earliest:
        raise RuntimeError("Too early to arm release: scheduled 8AM ET on Oct 27 only.")
    if now>latest:
        raise RuntimeError("8AM release missed 40-minute execution window. DO NOT send late or rerun.")
    if now<desired:
        secs=(desired-now).total_seconds()
        print("Scheduled 8AM ET guard: waiting "+str(round(secs))+" seconds. No emails yet.",flush=True)
        time.sleep(secs)
    checked=datetime.now(TZ)
    if checked.date().isoformat()!=TARGET_DATE or checked.hour!=8:
        raise RuntimeError("Local timestamp outside authorized October 27 8AM window.")
    print("Execution permitted at: "+checked.isoformat(),flush=True)

def read_manifest():
    m=json.loads(Path(REQUEST).read_text(encoding="utf8"))
    if m.get("authorized_for_date")!=TARGET_DATE or m.get("approved_by_user") is not True:
        raise RuntimeError("No user authorization for October 27 release")
    if m.get("business_sender")!="hyder@exampleabc.com":
        raise RuntimeError("Invalid approved sender")
    if set(m.get("batches",{}).keys())!={"batch06","batch07"}:
        raise RuntimeError("Exact two initial batches required")
    for b in BATCHES:
        item=m["batches"][b["key"]]
        if (item.get("batch_id")!=b["batch"] or item.get("expected_count")!=20 or
            item.get("id_first")!=b["id_first"] or item.get("id_last")!=b["id_last"]):
            raise RuntimeError("Approved batch and ID range do not match source")
        for k in ("recipients_hash","content_hash"):
            v=item.get(k,"")
            if len(v)!=8 or any(ch not in "0123456789abcdef" for ch in v):
                raise RuntimeError("Invalid frozen approval fingerprint")
    return m

def build_release(b,approval):
    w=validate_locked(json.loads(Path(b["source"]).read_text(encoding="utf8")))
    if w.get("name")!=b["source_name"] or w.get("active") is not False or len(w.get("nodes",[]))!=27:
        raise RuntimeError("Wrong or changed locked 27-node initial-outreach source")
    node={n["name"]:n for n in w["nodes"]}
    expected={
        "MANUAL Execute only - no schedule",
        "Read "+("Batch06" if b["key"]=="batch06" else "Batch07")+" Control",
        "Require exact batch approval","Consume single-use approval - RUNNING",
        "Read Prospects","Store Prospects","Read Email Drafts","Store Drafts",
        "Read Contact Exceptions","Store Exceptions",
        "Read "+("Batch06" if b["key"]=="batch06" else "Batch07")+" Send Log",
        "Prepare Queue and Gmail Search","Find ALL prior Gmail correspondence",
        "Block if ANY prior Gmail match","Loop One Email At A Time",
        "Verify Queued Recipient","Build Strict ExampleABC Initial MIME",
        SEND_NODE,"Require Gmail ID and restore candidate",
        "Log Gmail ID first - SEND LEDGER","Update original Prospect sent status",
        "Update original Email Draft sent status","Throttle 5 seconds",
        "Re-read "+("Batch06" if b["key"]=="batch06" else "Batch07")+" Ledger After Loop",
        "Require 20 Gmail IDs From Final Ledger",
        "Mark "+("Batch06" if b["key"]=="batch06" else "Batch07")+" COMPLETE"
    }
    if not expected.issubset(set(node)):
        raise RuntimeError("Required n8n safety/ledger nodes missing")
    trigger=node["MANUAL Execute only - no schedule"]
    if trigger["type"]!="n8n-nodes-base.manualTrigger":
        raise RuntimeError("Unsafe trigger")
    sensitive=[]
    for n in w["nodes"]:
        typ=n["type"];p=n.get("parameters",{});operation=p.get("operation")
        if typ=="n8n-nodes-base.httpRequest":
            if (p.get("method")!="POST" or p.get("url")!=GMAIL_URL or
                p.get("authentication")!="predefinedCredentialType" or
                p.get("nodeCredentialType")!="gmailOAuth2" or
                n["name"]!=SEND_NODE or n.get("disabled") is not True):
                raise RuntimeError("Unapproved HTTP method, endpoint, auth or enabled sender")
            sensitive.append(n)
        elif typ=="n8n-nodes-base.googleSheets" and operation in ("update","append","appendOrUpdate"):
            if operation!="update" or n.get("disabled") is not True:
                raise RuntimeError("Unsafe spreadsheet write source")
            sensitive.append(n)
        elif typ=="n8n-nodes-base.gmail" and operation in ("send","reply","sendAndWait"):
            raise RuntimeError("Native Gmail sender/reply is PROHIBITED after incident")
        elif typ in ("n8n-nodes-base.scheduleTrigger","n8n-nodes-base.webhook"):
            raise RuntimeError("Unapproved event trigger in locked source")
    if len(sensitive)!=6:
        raise RuntimeError("Incorrect sensitive node count; 1 Gmail API POST + 5 Sheets updates expected")
    sent=node[SEND_NODE]["parameters"]
    if "raw:$json.raw" not in sent.get("jsonBody",""):
        raise RuntimeError("Missing Gmail API raw MIME body")
    code=node["Build Strict ExampleABC Initial MIME"]["parameters"]["jsCode"]
    if ("const from='hyder@exampleabc.com'" not in code or
        "'To: '+to" not in code or
        "'From: Hyder Khan <'+from+'>'" not in code or
        "hyder@hiratechnologies.net" not in code):
        raise RuntimeError("Sender identity and recipient suppression code changed")
    if b["batch"] not in node["Prepare Queue and Gmail Search"]["parameters"]["jsCode"]:
        raise RuntimeError("Queue Code batch ID mismatch")
    if b["approval"] not in node["Require exact batch approval"]["parameters"]["jsCode"]:
        raise RuntimeError("Approval gate mismatch")
    for n in w["nodes"]:
        if n["type"]=="n8n-nodes-base.googleSheets":
            tab=n["parameters"]["sheetName"]["value"]
            if tab not in {"Prospects","Email Drafts","Contact Exceptions",b["control"],b["send_log"]}:
                raise RuntimeError("Unauthorized Sheet tab in release: "+tab)

    # Freeze BOTH recipient identities and full message content exactly as approved.
    q=node["Prepare Queue and Gmail Search"]
    qcode=q["parameters"]["jsCode"]
    marker="const gmail_query="
    if qcode.count(marker)!=1:raise RuntimeError("Cannot find exact queue approval hook")
    security="""
function fnv32(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16).padStart(8,'0');}
const recipients_hash=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()).join('|'));
const content_hash=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()+':'+String(c.subject)+':'+String(c.body)).join('|'));
if(recipients_hash!=='%s'||content_hash!=='%s')throw Error('APPROVAL HOLD: recipients or email body/subject changed since authorization. No sends.');
""" %(approval["recipients_hash"],approval["content_hash"])
    q["parameters"]["jsCode"]=qcode.replace(marker,security+"\n"+marker,1)

    token=hashlib.sha256(("ExampleABC-one-time-20261027-"+b["key"]+":"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    trigger["name"]="One-Time Oct27 Signed Webhook"
    trigger["type"]="n8n-nodes-base.webhook"
    trigger["typeVersion"]=2.1
    trigger["parameters"]={"httpMethod":"POST","path":b["webhook"],"responseMode":"onReceived","options":{}}
    trigger["webhookId"]=b["webhook_id"]
    guard={"id":"signed-"+b["key"],"name":"Require Exact Oct27 Approval Signature","type":"n8n-nodes-base.code",
           "typeVersion":2,"position":[240,300],"parameters":{"mode":"runOnceForAllItems",
           "jsCode":"const h=$input.first().json.headers||{};if(h['x-exampleabc-release-token']!=='"+token+"')throw Error('Unauthorized release');return [{json:{approved:true}}];"}}
    w["nodes"].append(guard)
    w["connections"].pop("MANUAL Execute only - no schedule",None)
    w["connections"][trigger["name"]]={"main":[[{"node":guard["name"],"type":"main","index":0}]]}
    w["connections"][guard["name"]]={"main":[[{"node":"Read "+("Batch06" if b["key"]=="batch06" else "Batch07")+" Control","type":"main","index":0}]]}

    for n in sensitive:n["disabled"]=False
    trusted={"gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
             "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA")}
    for typ,(source_id,nodename) in trusted.items():
        original=api("GET","/workflows/"+source_id)
        matches=[n for n in original["nodes"] if n["name"]==nodename]
        if len(matches)!=1:raise RuntimeError("Trusted ExampleABC credential source missing")
        cred=matches[0].get("credentials",{}).get(typ,{})
        if not cred.get("id"):raise RuntimeError("Credential reference has no ID")
        if typ=="gmailOAuth2" and cred.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Untrusted Gmail credential name")
        if typ=="googleSheetsOAuth2Api" and cred.get("name")!="ExampleABC Google Sheets":
            raise RuntimeError("Untrusted Google Sheets credential name")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):
                n["credentials"][typ]={"id":cred["id"],"name":cred["name"]}
    w["name"]=b["name"]
    return w,token

def launch_one(b,approval):
    if any(x.get("name")==b["name"] for x in pages("/workflows")):
        raise RuntimeError("One-time release workflow already exists: no retries, no duplicates.")
    w,token=build_release(b,approval)
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    made=api("POST","/workflows",payload)
    wid=str(made["id"])
    saved=api("GET","/workflows/"+wid)
    if saved.get("active") or len(saved.get("nodes",[]))!=28:
        raise RuntimeError("Unsafe persisted one-time workflow")
    old_ids={str(r["id"]) for r in api("GET","/executions?workflowId="+wid+"&limit=10").get("data",[])}
    active=False
    print("One-time "+b["key"]+" release created: "+HOST+"/workflow/"+wid,flush=True)
    try:
        api("POST","/workflows/"+wid+"/activate");active=True
        req=urllib.request.Request(HOST+"/webhook/"+b["webhook"],data=b"{}",method="POST",
             headers={"Content-Type":"application/json","X-ExampleABC-Release-Token":token})
        try:
            with urllib.request.urlopen(req,timeout=35) as response:
                if response.status>=300:raise RuntimeError("n8n rejected signed webhook")
        except urllib.error.HTTPError as exc:
            raise RuntimeError("n8n webhook HTTP "+str(exc.code)) from None
        print(b["key"]+" signed webhook accepted; monitoring send log. DO NOT RETRY on errors.",flush=True)
        deadline=time.monotonic()+730;result=None
        while time.monotonic()<deadline:
            fresh=[r for r in api("GET","/executions?workflowId="+wid+"&limit=10").get("data",[]) if str(r["id"]) not in old_ids]
            if fresh:
                result=fresh[0]
                if result.get("status") in ("success","error","crashed","canceled"):
                    break
            time.sleep(5)
        if not result:raise RuntimeError("Release execution not observed before timeout; reconcile Gmail Sent and Sheets; never retry.")
        detail=api("GET","/executions/"+str(result["id"])+"?includeData=true")
        data=detail.get("data",{}).get("resultData",{})
        nodes=data.get("runData",{})
        if result.get("status")!="success":
            err=data.get("error") or {}
            last=data.get("lastNodeExecuted")
            raise RuntimeError("Release "+b["key"]+" incomplete; execution "+str(result["id"])+" at "+str(last)+": "+str(err.get("message") or "")[:300]+"; manual reconciliation required")
        checks=[SEND_NODE,"Log Gmail ID first - SEND LEDGER","Update original Prospect sent status","Update original Email Draft sent status"]
        counts={name:len(nodes.get(name,[])) for name in checks}
        if any(n!=20 for n in counts.values()) or len(nodes.get("Mark "+("Batch06" if b["key"]=="batch06" else "Batch07")+" COMPLETE",[]))!=1:
            raise RuntimeError("Release "+b["key"]+" claims success but not all send/update/complete counts matched. "+str(counts))
        print("SUCCESS "+b["key"]+": 20 unique Gmail API sends, 20 send logs, 20 Prospect updates, 20 Draft updates; batch COMPLETE. Execution "+str(result["id"]),flush=True)
    finally:
        if active:
            try:
                api("POST","/workflows/"+wid+"/deactivate")
                print("One-time "+b["key"]+" workflow deactivated.",flush=True)
            except Exception:
                raise RuntimeError("URGENT: one-time release workflow "+wid+" could not deactivate!")

def main():
    approval=read_manifest()
    schedule_gate()
    for b in BATCHES:
        launch_one(b,approval["batches"][b["key"]])
        print("Batch "+b["key"]+" reconciled inside n8n; advancing to next authorized queue.",flush=True)
    print("All authorized October 27 initial outreach batches completed.",flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("OCT27 RELEASE SAFE STOP: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
