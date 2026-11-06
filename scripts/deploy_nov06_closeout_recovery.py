#!/usr/bin/env python3
import json, sys
from pathlib import Path
from deploy_locked_n8n import api, pages, validate_locked

OLD_WORKFLOW="OZ7YirujEI8BfUlh"
NAME="ExampleABC - Nov06 Closeout RECOVERY - ONE TIME 17"
SOURCE="ExampleABC_Batch07_FINAL_REVIEW_SENDING_LOCKED.json"
BATCH="NOV06-CLOSEOUT-RECOVERY-20261106"
CONTROL="Nov06 Closeout Recovery Control"
LOG="Nov06 Closeout Recovery Log"
FIRST=538
LAST=554
COUNT=17
RECIPIENTS_HASH="8478f5ff"
CONTENT_HASH="ca8cf923"
SEND="Send Explicit ExampleABC Initial via Gmail API - LOCKED"

def main():
    try:
        api("POST","/workflows/"+OLD_WORKFLOW+"/deactivate")
        print("Deactivated prior failed closeout workflow",OLD_WORKFLOW)
    except Exception as e:
        print("Prior workflow deactivate note:",str(e)[:300])

    if any(x.get("name")==NAME for x in pages("/workflows")):
        print("Recovery workflow already exists; refusing duplicate deployment.")
        return

    w=validate_locked(json.loads(Path(SOURCE).read_text(encoding="utf8")))
    nodes={n["name"]:n for n in w["nodes"]}
    trigger=nodes.get("MANUAL Execute only - no schedule")
    if not trigger or trigger.get("type")!="n8n-nodes-base.manualTrigger":
        raise RuntimeError("Expected locked manual trigger missing")

    for n in w["nodes"]:
        p=n.get("parameters",{})
        if n.get("type")=="n8n-nodes-base.googleSheets":
            sh=p.get("sheetName",{}).get("value")
            if sh=="Batch07 Control": p["sheetName"]["value"]=CONTROL
            elif sh=="Batch07 Send Log": p["sheetName"]["value"]=LOG

    replacements={
        "BATCH07-20261027":BATCH,
        "APPROVE BATCH 07":"APPROVE NOV06 CLOSEOUT RECOVERY",
        "Batch07 Control":CONTROL,
        "for(let id=76;id<=95;id++)":f"for(let id={FIRST};id<={LAST};id++)",
        "candidates.length!==20":f"candidates.length!=={COUNT}",
        "expected:20":f"expected:{COUNT}",
        "Number(c.prospect_id)<76||Number(c.prospect_id)>95":f"Number(c.prospect_id)<{FIRST}||Number(c.prospect_id)>{LAST}",
        "const expected=new Set([76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95]);":
            "const expected=new Set(["+",".join(str(i) for i in range(FIRST,LAST+1))+"]);"
    }
    for n in w["nodes"]:
        if n.get("type")=="n8n-nodes-base.code":
            src=n["parameters"].get("jsCode","")
            for a,b in replacements.items():
                src=src.replace(a,b)
            n["parameters"]["jsCode"]=src

    gate=nodes["Require exact batch approval"]["parameters"]["jsCode"]
    gate=gate.replace('Number(c["Expected Count"])!==20',f'Number(c["Expected Count"])!=={COUNT}')
    nodes["Require exact batch approval"]["parameters"]["jsCode"]=gate

    q=nodes["Prepare Queue and Gmail Search"]
    marker="const gmail_query="
    qcode=q["parameters"]["jsCode"]
    freeze=r"""
function fnv32(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16).padStart(8,'0');}
const recipients_hash=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()).join('|'));
const content_hash=fnv32(candidates.map(c=>String(c.prospect_id)+':'+String(c.to).toLowerCase().trim()+':'+String(c.subject)+':'+String(c.body)).join('|'));
if(recipients_hash!=='%s'||content_hash!=='%s')throw Error('APPROVAL HOLD: recipients or email content changed after Nov06 recovery freeze. No sends.');
""" % (RECIPIENTS_HASH,CONTENT_HASH)
    if qcode.count(marker)!=1: raise RuntimeError("Queue insertion point missing")
    q["parameters"]["jsCode"]=qcode.replace(marker,freeze+"\n"+marker,1)

    for node_name in ("Verify Queued Recipient","Build Strict ExampleABC Initial MIME","Require Gmail ID and restore candidate"):
        code=nodes[node_name]["parameters"]["jsCode"]
        if BATCH not in code or str(FIRST) not in code or str(LAST) not in code:
            raise RuntimeError("Range guard not retargeted in "+node_name)

    enabled=0
    for n in w["nodes"]:
        p=n.get("parameters",{})
        if n.get("type")=="n8n-nodes-base.httpRequest" and p.get("method")=="POST":
            if n["name"]!=SEND or p.get("url")!="https://gmail.googleapis.com/gmail/v1/users/me/messages/send":
                raise RuntimeError("Unexpected HTTP POST")
            n["disabled"]=False; enabled+=1
        elif n.get("type")=="n8n-nodes-base.googleSheets" and p.get("operation")=="update":
            if n.get("disabled") is not True:
                raise RuntimeError("Locked writer unexpectedly enabled")
            n["disabled"]=False; enabled+=1
    if enabled!=6: raise RuntimeError(f"Expected 6 sensitive nodes, enabled {enabled}")

    trusted={"gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
             "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA")}
    refs={}
    for typ,(wid,nodename) in trusted.items():
        src=api("GET","/workflows/"+wid)
        m=[n for n in src.get("nodes",[]) if n.get("name")==nodename]
        if len(m)!=1: raise RuntimeError("Trusted credential source missing")
        c=m[0].get("credentials",{}).get(typ,{})
        if typ=="gmailOAuth2" and c.get("name") not in ("hyder@exampleabc.com","ExampleABC Gmail"):
            raise RuntimeError("Unexpected Gmail credential")
        if typ=="googleSheetsOAuth2Api" and c.get("name")!="ExampleABC Google Sheets":
            raise RuntimeError("Unexpected Sheets credential")
        refs[typ]={"id":c["id"],"name":c["name"]}
    for n in w["nodes"]:
        for typ in list(n.get("credentials",{})):
            if typ not in refs: raise RuntimeError("Untrusted credential type "+typ)
            n["credentials"][typ]=refs[typ]

    old=trigger["name"]
    downstream=w["connections"].pop(old)
    trigger["name"]="Every minute until Nov06 recovery consumed"
    trigger["type"]="n8n-nodes-base.scheduleTrigger"
    trigger["typeVersion"]=1.2
    trigger["parameters"]={"rule":{"interval":[{"field":"cronExpression","expression":"* * * * *"}]}}
    guard_name="Require Nov06 2026 ET recovery"
    guard={"id":"nov06-recovery-date-guard","name":guard_name,"type":"n8n-nodes-base.code","typeVersion":2,
           "position":[300,300],"parameters":{"mode":"runOnceForAllItems","jsCode":
           "const p=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).filter(x=>x.type!=='literal').map(x=>[x.type,x.value])); if(p.year!=='2026'||p.month!=='11'||p.day!=='06') return []; return $input.all();"}}
    w["nodes"].append(guard)
    w["connections"][trigger["name"]]={"main":[[{"node":guard_name,"type":"main","index":0}]]}
    w["connections"][guard_name]=downstream
    w["name"]=NAME
    w.setdefault("settings",{})["timezone"]="America/New_York"

    payload={k:w[k] for k in ("name","nodes","connections","settings")}
    made=api("POST","/workflows",payload)
    wid=str(made["id"])
    api("POST","/workflows/"+wid+"/activate")
    print("RECOVERY READY:", "https://auto.exampleabc.com/workflow/"+wid)

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("RECOVERY DEPLOY STOPPED:",str(e),file=sys.stderr)
        raise
