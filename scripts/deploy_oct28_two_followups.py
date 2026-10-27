#!/usr/bin/env python3
'''Deploy a fresh one-time Oct28 same-thread follow-up workflow for Kim and Jenn.'''
import json,sys
from pathlib import Path
from deploy_locked_n8n import api,pages,validate_locked

NAME="ExampleABC - Oct28 8:10AM ET - 2 Eligible Followups"
SOURCE="ExampleABC_Batch05_Followups_THREAD_REPLIES_LOCKED.json"
BATCH="OCT28-FOLLOWUP-20261028"
CONTROL="Oct28 Followup Control"
LOG="Oct28 Followup Log"
SEND="Send Explicit ExampleABC Same-Thread Reply - LOCKED"

KIM_BODY='''Hi Kim,

Just checking whether you had a chance to see my note about streamlining repair-status updates and front-desk follow-ups. If you're not the right person, would you be willing to point me toward whoever handles business operations? No worries if this isn't relevant.

Best regards,
Hyder Khan
ExampleABC Automation Solutions, LLC
hyder@exampleabc.com
https://exampleabc.com | (609) 310-1805

To opt out, just reply "unsubscribe."'''
JENN_BODY='''Hi Jenn,

Just following up on my earlier note about routing estimate inquiries and coordinating customer follow-ups at McCabe Electric. If that's already streamlined, great. If there is still manual work involved, would a brief 15-minute conversation be worthwhile?

No pressure if it isn't a priority.

Best regards,
Hyder Khan
ExampleABC Automation Solutions, LLC
hyder@exampleabc.com
https://exampleabc.com | (609) 310-1805

To opt out, just reply "unsubscribe."'''

def main():
    if any(x.get("name")==NAME for x in pages("/workflows")):
        print("Follow-up workflow already exists; refusing duplicate deployment."); return
    w=validate_locked(json.loads(Path(SOURCE).read_text(encoding="utf8")))
    if w.get("active") is not False: raise RuntimeError("Locked source unexpectedly active")
    nodes={n["name"]:n for n in w["nodes"]}

    # Fresh control/log tabs.
    for n in w["nodes"]:
        if n.get("type")=="n8n-nodes-base.googleSheets":
            sh=n.get("parameters",{}).get("sheetName",{}).get("value")
            if sh=="Batch05 Followup Control": n["parameters"]["sheetName"]["value"]=CONTROL
            elif sh=="Batch05 Followup Log": n["parameters"]["sheetName"]["value"]=LOG

    nodes["Require Followup Approval (HOLD now)"]["parameters"]["jsCode"] = (
        "const c=$input.all()[0]?.json||{};"
        "if(c['Batch ID']!=='"+BATCH+"'||String(c.Approval||'')!=='APPROVE FOLLOWUPS'||Number(c['Expected Count'])!==2)"
        "throw Error('Followup review HOLD. Do not send.');"
        "return [{json:{'Batch ID':'"+BATCH+"',Approval:'RUNNING','Last Run':new Date().toISOString()}}];"
    )

    queue_js = r'''
const L=$input.all().map(i=>i.json);
const t=v=>String(v??'').trim();
const wanted=new Map([
 [7,{to:'kim@jimcarlsautobody.com',body:%s}],
 [25,{to:'jenn@mccabeelectric.net',body:%s}]
]);
const queue=[],fail=[];
for(const [id,w] of wanted){
 const l=L.find(x=>Number(x['Prospect #'])===id); const issues=[];
 if(!l) issues.push('missing followup log');
 else {
  if(t(l['Batch ID'])!=='%s') issues.push('wrong batch id');
  if(t(l.Recipient).toLowerCase()!==w.to) issues.push('recipient mismatch');
  if(!/^[0-9a-f]{16,}$/.test(t(l['Original Gmail Message ID']))||!t(l['Original Thread ID'])) issues.push('missing original Gmail IDs');
  if(t(l['Review Status'])!=='READY'||t(l['Send Status'])!=='PENDING'||t(l['Follow-up Gmail ID'])) issues.push('not pending/ready');
 }
 if(issues.length) fail.push('#'+id+':'+issues.join(','));
 else queue.push({id,to:w.to,body:w.body,orig_message_id:l['Original Gmail Message ID'],orig_thread_id:l['Original Thread ID'],batch_id:'%s'});
}
if(fail.length||queue.length!==2) throw Error('Follow-up send ABORT '+fail.join('|')+' candidates='+queue.length);
return queue.map(x=>({json:x}));
''' % (json.dumps(KIM_BODY),json.dumps(JENN_BODY),BATCH,BATCH)
    nodes["Build Verified Thread Reply Queue"]["parameters"]["jsCode"]=queue_js

    req=nodes["Require Gmail Follow-up Message ID"]["parameters"]["jsCode"]
    req=req.replace("BATCH05-FOLLOWUP-20261026",BATCH)
    nodes["Require Gmail Follow-up Message ID"]["parameters"]["jsCode"]=req
    nodes["Require 15 Confirmed Followup Gmail IDs"]["parameters"]["jsCode"] = (
        "const expected=new Set([7,25]);"
        "const matched=$input.all().map(item=>item.json).filter(r=>r['Batch ID']==='"+BATCH+"');"
        "const unique=new Map();"
        "for(const row of matched){const id=Number(row['Prospect #']);"
        "if(!expected.has(id))throw Error('Unexpected prospect in followup ledger: '+id);"
        "if(row['Send Status']!=='SENT'||!String(row['Follow-up Gmail ID']||'').trim()||!String(row['Follow-up Sent ET']||'').trim())throw Error('Incomplete followup ledger #'+id);"
        "unique.set(id,row);}if(unique.size!==2)throw Error('Missing confirmed followup Gmail IDs; got '+unique.size+' of 2');"
        "return [{json:{'Batch ID':'"+BATCH+"',Approval:'COMPLETE','Last Run':new Date().toISOString()}}];"
    )

    # Enable only the locked outbound/write nodes.
    enabled=0
    for n in w["nodes"]:
        p=n.get("parameters",{})
        if n.get("type")=="n8n-nodes-base.httpRequest" and p.get("method")=="POST":
            if n["name"]!=SEND or p.get("url")!="https://gmail.googleapis.com/gmail/v1/users/me/messages/send":
                raise RuntimeError("Unexpected followup HTTP POST")
            n["disabled"]=False; enabled+=1
        elif n.get("type")=="n8n-nodes-base.googleSheets" and p.get("operation")=="update":
            if n.get("disabled") is not True: raise RuntimeError("Locked Sheet writer unexpectedly enabled")
            n["disabled"]=False; enabled+=1
    if enabled!=5: raise RuntimeError(f"Expected 5 sensitive nodes, enabled {enabled}")

    # Trusted credential references.
    trusted={"gmailOAuth2":("ymCruFvw0MQe-jfBKFGxt","Send QA To SELF Only"),
             "googleSheetsOAuth2Api":("MoW6SECTxE1mNYpxGy7Tc","Update ONLY Automation QA")}
    refs={}
    for typ,(wid,nodename) in trusted.items():
        src=api("GET","/workflows/"+wid)
        matches=[n for n in src.get("nodes",[]) if n.get("name")==nodename]
        if len(matches)!=1: raise RuntimeError("Trusted credential source missing")
        c=matches[0].get("credentials",{}).get(typ,{})
        if not c.get("id") or not c.get("name"): raise RuntimeError("Credential missing")
        refs[typ]={"id":c["id"],"name":c["name"]}
    for n in w["nodes"]:
        for typ in list(n.get("credentials",{})):
            if typ not in refs: raise RuntimeError("Untrusted credential type "+typ)
            n["credentials"][typ]=refs[typ]

    # Exact Oct28 schedule at 08:10 ET, after the 50-message initial batch has time to finish.
    trigger=nodes["Manual Review Trigger"]; old=trigger["name"]; downstream=w["connections"].pop(old)
    trigger["name"]="Scheduled Oct28 8:10AM ET - ONE TIME"
    trigger["type"]="n8n-nodes-base.scheduleTrigger"; trigger["typeVersion"]=1.2
    trigger["parameters"]={"rule":{"interval":[{"field":"cronExpression","expression":"10 8 28 10 *"}]}}
    guard_name="Require exact Oct28 2026 8AM ET"
    guard={"id":"oct28-followup-date-guard","name":guard_name,"type":"n8n-nodes-base.code","typeVersion":2,"position":[300,300],
           "parameters":{"mode":"runOnceForAllItems","jsCode":"const p=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).filter(x=>x.type!=='literal').map(x=>[x.type,x.value])); if(p.year!=='2026'||p.month!=='10'||p.day!=='28'||p.hour!=='08') return []; return $input.all();"}}
    w["nodes"].append(guard)
    w["connections"][trigger["name"]]={"main":[[{"node":guard_name,"type":"main","index":0}]]}
    w["connections"][guard_name]=downstream
    w["name"]=NAME; w.setdefault("settings",{})["timezone"]="America/New_York"
    made=api("POST","/workflows",{k:w[k] for k in ("name","nodes","connections","settings")})
    wid=str(made["id"]); api("POST","/workflows/"+wid+"/activate")
    if not api("GET","/workflows/"+wid).get("active"): raise RuntimeError("Follow-up workflow failed to activate")
    print("READY https://auto.exampleabc.com/workflow/"+wid)
    print("Scheduled Oct28 08:10 ET; 2 exact same-thread followups, each fails closed if thread changed.")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("OCT28 FOLLOWUP DEPLOY STOPPED:",str(e),file=sys.stderr); raise
