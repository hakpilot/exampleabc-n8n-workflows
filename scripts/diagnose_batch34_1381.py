#!/usr/bin/env python3
"""Read-only diagnosis of ExampleABC n8n batch34 completed execution, never sends."""
from deploy_locked_n8n import api
def main():
    run=api("GET","/executions/1381?includeData=true")
    result=run.get("data",{}).get("resultData",{})
    raw=result.get("error") or {}
    d={
      "id":run.get("id"),
      "status":run.get("status"),
      "lastNodeExecuted":result.get("lastNodeExecuted"),
      "errorType":raw.get("name") or raw.get("type"),
      "errorMessage":str(raw.get("message") or raw.get("description") or "")[:1200],
      "nodeRuns":{name:len(runs) for name,runs in result.get("runData",{}).items()}
    }
    node=result.get("runData",{}).get("Re-read Followup Log After Loop",[])
    if node:
        outputs=node[0].get("data",{}).get("main",[])
        items=outputs[0] if outputs else []
        print("Final ledger reread count:",len(items))
        print("Final ledger non-sensitive fields:",sorted(items[0].get("json",{}).keys()) if items else [])
        print("First/last ledger batch IDs:",[items[0].get("json",{}).get("Batch ID"),items[-1].get("json",{}).get("Batch ID")] if items else [])
        print("Ledger status counts:",{status:sum(x.get("json",{}).get("Send Status")==status for x in items) for status in ["SENT","PENDING"]})
    print("Read-only execution diagnosis (no email bodies, credentials or recipient addresses):")
    print(d)
if __name__=="__main__":main()
