#!/usr/bin/env python3
"""Deploy TWO MANUAL-TRIGGER n8n one-use outbound releases. Does not execute messages.

The original locked workflows remain unmodified. Each release enforces the user's
Batch Control dropdown, 20 exact prospect IDs, frozen recipient+draft hashes,
Gmail history suppression, explicit ExampleABC-only From/To, verified actual
Gmail headers, single-use RUNNING token, write-ahead Gmail ID receipt,
and full Google Sheets reconciliation. No automatic schedule or webhook.
"""
import argparse,hashlib,json,os,sys,subprocess,tempfile
from pathlib import Path
from deploy_locked_n8n import api,pages,validate_locked

HOST="https://auto.exampleabc.com"
MANIFEST="release_requests/oct27_initial_batches.json"
SENDER="hyder@exampleabc.com"
SPECS={
  "batch06":{"filename":"ExampleABC_Batch06_FINAL_REVIEW_SENDING_LOCKED.json",
   "batch_id":"BATCH06-20261022","first":56,"last":75,"control":"Batch06 Control",
   "release_name":"ExampleABC MANUAL ONE-TIME Batch06 - 20 Verified New Emails",
   "expected_source":"ExampleABC - Batch06 FINAL REVIEW - SENDING LOCKED"},
  "batch07":{"filename":"ExampleABC_Batch07_FINAL_REVIEW_SENDING_LOCKED.json",
   "batch_id":"BATCH07-20261027","first":76,"last":95,"control":"Batch07 Control",
   "release_name":"ExampleABC MANUAL ONE-TIME Batch07 - 20 Verified New Emails",
   "expected_source":"ExampleABC - Batch07 FINAL REVIEW - SENDING LOCKED"}
}
SEND="Send Explicit ExampleABC Initial via Gmail API - LOCKED"
SENSITIVE_BASE={"Consume single-use approval - RUNNING", SEND,"Log Gmail ID first - SEND LEDGER",
 "Update original Prospect sent status","Update original Email Draft sent status"}
TRUSTED={
 "gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
 "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA")
}

def approve_manifest():
    j=json.loads(Path(MANIFEST).read_text())
    if j.get("approved_by_user") is not True or j.get("authorized_for_date")!="2026-10-27":
        raise RuntimeError("User's approved frozen release manifest is missing")
    if j.get("business_sender")!=SENDER or j.get("sole_to_per_message") is not True or j.get("allow_cc_bcc") is not False:
        raise RuntimeError("Business identity approval mismatch")
    if set(j.get("batches",{}))!=set(SPECS):raise RuntimeError("Incorrect batch count")
    return j

def frozen_js(approved):
    for key in ("recipients_hash","content_hash"):
        v=approved[key]
        if not isinstance(v,str) or len(v)!=8 or any(c not in "0123456789abcdef" for c in v):
            raise RuntimeError("Invalid verified approval fingerprint")
    return r"""
// FROZEN review: exact 20 recipients, subjects and bodies approved by the user.
// An altered recipient/body fails closed BEFORE any Gmail API POST.
function fnv32(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16).padStart(8,'0');}
const signedRecipients=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()).join('|'));
const signedContent=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()+':'+String(c.subject)+':'+String(c.body)).join('|'));
if(signedRecipients!=='%s'||signedContent!=='%s')throw Error('STOP: frozen approved recipients or message content changed; no emails sent.');
""" % (approved["recipients_hash"],approved["content_hash"])

def prepare(key,manifest):
    spec=SPECS[key];f=spec["filename"]
    workflow=validate_locked(json.loads(Path(f).read_text(encoding="utf8")))
    if workflow.get("name")!=spec["expected_source"] or len(workflow["nodes"])!=29 or workflow.get("active") is not False:
        raise RuntimeError("Original production locked source changed unexpectedly: "+f)
    nodes={n["name"]:n for n in workflow["nodes"]}
    sensitive=SENSITIVE_BASE | {"Mark "+("Batch06" if key=="batch06" else "Batch07")+" COMPLETE"}
    for n in workflow["nodes"]:
        typ=n["type"];p=n.get("parameters",{})
        if typ=="n8n-nodes-base.googleSheets" and p.get("operation") in ("update","append","appendOrUpdate"):
            if n["name"] not in sensitive or n.get("disabled") is not True:raise RuntimeError("Unexpected Sheet writer "+n["name"])
        elif typ=="n8n-nodes-base.httpRequest" and p.get("method")=="POST":
            if n["name"]!=SEND or n.get("disabled") is not True or p.get("url")!="https://gmail.googleapis.com/gmail/v1/users/me/messages/send":
                raise RuntimeError("Unexpected outbound sender")
        elif typ=="n8n-nodes-base.gmail" and p.get("operation") in ("send","reply","sendAndWait"):
            raise RuntimeError("Native Gmail Send/Reply prohibited")
        elif typ in ("n8n-nodes-base.webhook","n8n-nodes-base.scheduleTrigger"):
            raise RuntimeError("No unsolicited triggers allowed")
    if not sensitive.issubset(nodes):raise RuntimeError("Missing required send/ledger/approval nodes")
    if any(nodes[n].get("disabled") is not True for n in sensitive):raise RuntimeError("Unexpected source sensitive flags")
    trigger=nodes.get("MANUAL Execute only - no schedule")
    if not trigger or trigger["type"]!="n8n-nodes-base.manualTrigger":raise RuntimeError("Missing manual trigger")
    if "Require Actual From/To Headers Match" not in nodes or "Read Actual Sent Gmail Headers - Read Only" not in nodes:
        raise RuntimeError("No post-send RFC822 verification")
    raw=nodes["Build Strict ExampleABC Initial MIME"]["parameters"]["jsCode"]
    if ("const from='hyder@exampleabc.com'" not in raw or "'To: '+to" not in raw or
        "c.authorized_to_send!==true" not in raw or "hyder@hiratechnologies.net" not in raw):
        raise RuntimeError("Identity/recipient restriction removed")
    hdr=nodes["Require Actual From/To Headers Match"]["parameters"]["jsCode"]
    if ("f[0]!=='hyder@exampleabc.com'" not in hdr or "t.length!==1" not in hdr or "||cc||bcc" not in hdr):
        raise RuntimeError("Post-send Gmail actual-header gate weakened")
    gate=nodes["Require exact batch approval"]["parameters"]["jsCode"]
    expectedApproval="APPROVE BATCH "+("06" if key=="batch06" else "07")
    if expectedApproval not in gate or spec["batch_id"] not in gate:raise RuntimeError("Approval dropdown not validated")
    queue=nodes["Prepare Queue and Gmail Search"]["parameters"]["jsCode"]
    rangeClause="for(let id=%s;id<=%s;id++)"%(spec["first"],spec["last"])
    if rangeClause not in queue or queue.count("const gmail_query=")!=1 or "candidates.length!==20" not in queue:
        raise RuntimeError("Exact 20 ID-range validation changed")
    item=manifest["batches"][key]
    if item["batch_id"]!=spec["batch_id"] or item["id_first"]!=spec["first"] or item["id_last"]!=spec["last"] or item["expected_count"]!=20:
        raise RuntimeError("Approved batch manifest ID range mismatch")
    queue=queue.replace("const gmail_query=",frozen_js(item)+"\nconst gmail_query=",1)
    nodes["Prepare Queue and Gmail Search"]["parameters"]["jsCode"]=queue
    for n in workflow["nodes"]:
        if n["name"] in sensitive:n["disabled"]=False
    if len([n for n in workflow["nodes"] if n["type"]=="n8n-nodes-base.httpRequest" and n["parameters"].get("method")=="POST"])!=1:
        raise RuntimeError("More than one outbound sender")
    if len([n for n in workflow["nodes"] if n["type"]=="n8n-nodes-base.googleSheets" and n["parameters"].get("operation")=="update" and n.get("disabled") is False])!=5:
        raise RuntimeError("Expected exactly five ledger/control writers")
    # Manually triggered n8n workflows stay unpublished/inactive: editor Execute only.
    workflow["name"]=spec["release_name"]
    workflow["active"]=False
    note=next((n for n in workflow["nodes"] if n["type"]=="n8n-nodes-base.stickyNote"),None)
    if note:
        note["parameters"]["content"] = (
            "## ONE-TIME MANUAL RELEASE - "+key.upper()+"\n"
            "User approved "+spec["batch_id"]+" in Google Sheets. Open editor; click Execute Workflow ONCE only.\n"
            "No webhooks or schedules. First run changes "+spec["control"]+" B2 from APPROVE to RUNNING.\n"
            "If anything fails: DO NOT click Execute again; reconcile Gmail Sent and the Batch Send Log.\n"
            "Exact 20 frozen recipients + content, opt-outs, Gmail correspondence check, no Cc/Bcc,\n"
            "From: hyder@exampleabc.com, actual Gmail header check after each message,\n"
            "write Gmail message ID and update Prospects + Email Drafts, and mark COMPLETE.\n"
            "Run Batch06 first; only run Batch07 after Batch06 confirmed COMPLETE.\n"
            "Original locked source remains untouched."
        )
    for n in workflow["nodes"]:
        if n["type"]=="n8n-nodes-base.code":
            src=n["parameters"]["jsCode"]
            with tempfile.NamedTemporaryFile(mode="w",suffix=".js",delete=False) as tmp:
                tmp.write("async function n8nCode() {\n"+src+"\n}\n");name=tmp.name
            try:
                r=subprocess.run(["node","--check",name],capture_output=True,text=True)
                if r.returncode:raise RuntimeError("JS syntax "+n["name"]+": "+r.stderr[:350])
            finally:Path(name).unlink()
    return workflow

def credentials():
    refs={}
    for typ,(workflow_id,node_name) in TRUSTED.items():
        wf=api("GET","/workflows/"+workflow_id)
        src=[n for n in wf.get("nodes",[]) if n.get("name")==node_name]
        if len(src)!=1:raise RuntimeError("Trusted credential source missing: "+node_name)
        c=src[0].get("credentials",{}).get(typ,{})
        if not c.get("id") or not c.get("name"):raise RuntimeError("Trusted credential reference missing")
        if typ=="gmailOAuth2" and c["name"] not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Unexpected Gmail OAuth credential")
        if typ=="googleSheetsOAuth2Api" and c["name"]!="ExampleABC Google Sheets":
            raise RuntimeError("Unexpected Sheets OAuth credential")
        refs[typ]={"id":c["id"],"name":c["name"]}
    return refs

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--deploy",action="store_true",help="create two manual, unpublished n8n workflows WITHOUT executing")
    args=p.parse_args()
    manifest=approve_manifest()
    releases=[prepare(key,manifest) for key in SPECS]
    print("PASS OFFLINE: both batches have 29-node, manual-only, one-time approved explicit sender, original headers and content frozen.")
    if not args.deploy:
        print("DRY RUN ONLY. No n8n/API calls and no emails sent.")
        return
    existing=pages("/workflows")
    for release in releases:
        if any(n.get("name")==release["name"] for n in existing):
            raise RuntimeError("This manual release was already deployed. Refusing a duplicate release.")
    refs=credentials()
    for wf in releases:
        for n in wf["nodes"]:
            for typ,c in n.get("credentials",{}).items():
                if typ not in refs:raise RuntimeError("Untrusted n8n credential node "+n["name"])
                n["credentials"][typ]=refs[typ]
    for wf in releases:
        payload={k:wf[k] for k in ("name","nodes","connections","settings")}
        made=api("POST","/workflows",payload)
        wid=str(made["id"])
        saved=api("GET","/workflows/"+wid)
        if saved.get("active") or len(saved.get("nodes",[]))!=29:
            raise RuntimeError("Persisted manual release has wrong state/nodes "+wid)
        for n in saved["nodes"]:
            if n["name"]==SEND and n.get("disabled") is True:
                raise RuntimeError("Gmail sender still disabled after deployment")
        print("MANUAL WORKFLOW READY (NOT RUN): "+HOST+"/workflow/"+wid)
    print("NO EMAILS SENT. User must open Batch06 and press Execute Workflow ONCE, confirm COMPLETE, then Batch07.")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("MANUAL RELEASE STOPPED: "+str(e),file=sys.stderr)
        sys.exit(1)
