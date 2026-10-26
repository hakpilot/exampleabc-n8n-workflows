#!/usr/bin/env python3
"""Single-use n8n release for 16 explicitly approved first follow-ups in original threads."""
import hashlib,json,os,sys,time,urllib.parse,urllib.request
from pathlib import Path
from deploy_locked_n8n import api,pages,validate_locked

HOST="https://auto.exampleabc.com"
SOURCE="ExampleABC_Batch34_Followups_THREAD_REPLIES_LOCKED.json"
REQUEST="release_requests/Batch34_Followups_Approved.json"
NAME="ExampleABC - Batch34 Followup RELEASE - ONE TIME"
PATH="exampleabc-batch34-release-9c35fb5c14e94283b5ac2f54ba5c8c06"
def approval():
    r=json.loads(Path(REQUEST).read_text())
    if r.get("batch")!="BATCH34-FOLLOWUP-20261023" or r.get("approved") is not True:
        raise RuntimeError("Follow-up batch approval not present")
    if r.get("expected_count")!=16 or r.get("approval_phrase")!="I APPROVE BATCH 34: SEND 16 FIRST FOLLOWUPS":
        raise RuntimeError("Exact 16-thread approval is missing.")
    f=r.get("contact_fingerprint","")
    if len(f)!=8 or any(x not in "0123456789abcdef" for x in f):
        raise RuntimeError("Invalid reviewed recipient fingerprint")
    return r
def build(req):
    w=validate_locked(json.loads(Path(SOURCE).read_text()))
    if len(w["nodes"])!=24 or w["name"]!="ExampleABC - Batch34 Followups - THREAD REPLIES LOCKED":
        raise RuntimeError("Unexpected follow-up locked source version")
    important=[]
    for n in w["nodes"]:
        typ=n["type"];op=n.get("parameters",{}).get("operation")
        if typ=="n8n-nodes-base.gmail" and op in ("send","reply"):
            important.append(n)
            if op!="reply" or n["name"]!="Reply In Original Gmail Thread - DEACTIVATED":
                raise RuntimeError("Unapproved Gmail operation")
        if typ=="n8n-nodes-base.googleSheets" and op in ("update","append","appendOrUpdate"):
            important.append(n)
        if typ in ("n8n-nodes-base.httpRequest","n8n-nodes-base.scheduleTrigger"):
            raise RuntimeError("No HTTP/scheduled triggers in release")
    if len(important)!=5 or any(n.get("disabled") is not True for n in important):
        raise RuntimeError("Follow-up locked source has unexpected active writes")
    trigger=[n for n in w["nodes"] if n["name"]=="Manual Review Trigger"]
    if len(trigger)!=1 or trigger[0]["type"]!="n8n-nodes-base.manualTrigger":
        raise RuntimeError("Unexpected followup manual trigger")
    token=hashlib.sha256(("ExampleABC-Approved-Followups-v1:"+os.environ["N8N_API_KEY"]).encode()).hexdigest()
    tr=trigger[0]
    tr["name"]="Approved Followup Signed Webhook"
    tr["type"]="n8n-nodes-base.webhook"
    tr["typeVersion"]=2.1
    tr["parameters"]={"httpMethod":"POST","path":PATH,"responseMode":"onReceived","options":{}}
    tr["webhookId"]="3d158f3b-9f11-4c0e-9319-7c92d85bd3dd"
    gate={"id":"batch34signed","name":"Require Followup Release Signature","type":"n8n-nodes-base.code",
          "typeVersion":2,"position":[200,300],"parameters":{"mode":"runOnceForAllItems",
          "jsCode":"const h=$input.first().json.headers||{};if(h['x-exampleabc-release-token']!=='"+token+"')throw Error('Unauthorized followup release');return [{json:{authorized:true}}];"}}
    w["nodes"].append(gate)
    w["connections"].pop("Manual Review Trigger",None)
    w["connections"][tr["name"]]={"main":[[{"node":gate["name"],"type":"main","index":0}]]}
    w["connections"][gate["name"]]={"main":[[{"node":"Read Followup Control","type":"main","index":0}]]}
    code_node=[n for n in w["nodes"] if n["name"]=="Build Verified Thread Reply Queue"]
    if len(code_node)!=1:raise RuntimeError("Missing followup preflight code")
    code=code_node[0]["parameters"]["jsCode"]
    marker="return queue.map(x=>({json:x}));"
    if marker not in code:raise RuntimeError("Cannot insert recipient fingerprint")
    extra="""
function fnv32(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16).padStart(8,'0');}
const reviewed=fnv32(queue.slice().sort((a,b)=>a.id-b.id).map(c=>String(c.id)+':'+String(c.to).toLowerCase().trim()).join('\\n'));
if(reviewed!=='%s')throw Error('Follow-up recipients differ from the 16 user-reviewed contact addresses. Do NOT reply.');
""" % req["contact_fingerprint"]
    code_node[0]["parameters"]["jsCode"]=code.replace(marker,extra+"\n"+marker,1)
    for n in important:n["disabled"]=False
    sources={"gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
             "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA")}
    for typ,(source_id,source_node) in sources.items():
        wf=api("GET","/workflows/"+source_id)
        hits=[n for n in wf["nodes"] if n["name"]==source_node]
        if len(hits)!=1:raise RuntimeError("Approved credential source missing")
        c=hits[0]["credentials"][typ]
        if not c.get("id"):raise RuntimeError("Approved credential reference missing")
        if typ=="gmailOAuth2" and c.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Wrong Gmail identity")
        if typ=="googleSheetsOAuth2Api" and c.get("name")!="ExampleABC Google Sheets":
            raise RuntimeError("Wrong Sheets identity")
        for n in w["nodes"]:
            if typ in n.get("credentials",{}):
                n["credentials"][typ]={"id":c["id"],"name":c["name"]}
    w["name"]=NAME
    return w,token
def executions(wfid):
    return api("GET","/executions?workflowId="+urllib.parse.quote(str(wfid))+"&limit=10").get("data",[])
def main():
    # INCIDENT_20261026_SENDER_SAFETY_HOLD: no external sending until From/To header QA passes.
    raise RuntimeError('SAFETY HOLD: Gmail OAuth uses HIRA account and native reply-all includes an internal address. Do not release; repair explicit sender and recipient MIME first.')
    r=approval()
    if any(x.get("name")==NAME for x in pages("/workflows")):
        raise RuntimeError("Followup release already exists; would risk duplicate replies. Stop.")
    w,token=build(r)
    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    wid=str(api("POST","/workflows",payload)["id"])
    w_saved=api("GET","/workflows/"+wid)
    if len(w_saved.get("nodes",[]))!=25 or w_saved.get("active"):
        raise RuntimeError("Followup release saved node count or state mismatch.")
    old_ids={str(x["id"]) for x in executions(wid)}
    print("One-time approved 16-thread reply release installed with signed webhook, fingerprint and one-use Sheets gate.")
    print("n8n release: "+HOST+"/workflow/"+wid)
    active=False
    try:
        api("POST","/workflows/"+wid+"/activate");active=True
        request=urllib.request.Request(HOST+"/webhook/"+PATH,data=b"{}",method="POST",
            headers={"Content-Type":"application/json","X-ExampleABC-Release-Token":token})
        try:
            with urllib.request.urlopen(request,timeout=35) as rsp:
                if rsp.status>=300:raise RuntimeError("Webhook response not 2xx.")
        except urllib.error.HTTPError as exc:
            raise RuntimeError("Followup release webhook HTTP "+str(exc.code)) from None
        print("One signed followup batch run accepted. Do not retry a partial run.")
        until=time.monotonic()+540
        run=None
        while time.monotonic()<until:
            new=[x for x in executions(wid) if str(x["id"]) not in old_ids]
            if new:
                run=new[0]
                if run.get("status") in ("success","error","crashed","canceled"):break
            time.sleep(5)
        if not run:raise RuntimeError("Followup execution not visible within timeout. Reconcile before retry.")
        if run.get("status")!="success":
            raise RuntimeError("Followup release stopped with "+str(run.get("status"))+" execution "+str(run["id"])+". Do not retry.")
        detail=api("GET","/executions/"+str(run["id"])+"?includeData=true")
        data=detail.get("data",{}).get("resultData",{}).get("runData",{})
        counts={n:len(data.get(n,[])) for n in ["Reply In Original Gmail Thread - DEACTIVATED","Update Followup Send Log - DEACTIVATED","Write Prospect Follow-up Timestamp - DEACTIVATED"]}
        if any(v!=16 for v in counts.values()):
            raise RuntimeError("Followup release count mismatch; inspect "+str(counts)+" before retry.")
        if len(data.get("Set Followup Control COMPLETE - DEACTIVATED",[]))!=1:
            raise RuntimeError("Followup COMPLETE flag not written")
        print("FOLLOWUP SUCCESS: 16 original-thread replies, 16 send logs and 16 prospect status updates.")
        print("Followup execution ID: "+str(run["id"]))
    finally:
        if active:
            try:
                api("POST","/workflows/"+wid+"/deactivate")
                print("One-time followup release deactivated.")
            except Exception:
                raise RuntimeError("CRITICAL: Followup release still active; disable manually.")
if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("FOLLOWUP RELEASE STOPPED: "+str(ex),file=sys.stderr)
        raise SystemExit(1)
