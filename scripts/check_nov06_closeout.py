#!/usr/bin/env python3
from deploy_locked_n8n import api
WORKFLOW="OZ7YirujEI8BfUlh"
def main():
    runs=api("GET",f"/executions?workflowId={WORKFLOW}&limit=5&includeData=true")
    data=runs.get("data",runs if isinstance(runs,list) else [])
    if isinstance(data,dict): data=data.get("results") or data.get("data") or []
    print("RUNS",len(data))
    for run in data:
        rid=run.get("id")
        full=api("GET",f"/executions/{rid}?includeData=true") if rid else run
        result=full.get("data",{}).get("resultData",{})
        err=result.get("error") or {}
        print({
          "id":rid,
          "status":full.get("status"),
          "lastNodeExecuted":result.get("lastNodeExecuted"),
          "errorType":err.get("name") or err.get("type"),
          "errorMessage":str(err.get("message") or err.get("description") or "")[:1500],
          "nodeRuns":{k:len(v) for k,v in result.get("runData",{}).items()}
        })
if __name__=="__main__": main()
