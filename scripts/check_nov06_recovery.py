#!/usr/bin/env python3
from deploy_locked_n8n import api
WORKFLOW="JzlUHhKNhyzFkvle"
def main():
    runs=api("GET",f"/executions?workflowId={WORKFLOW}&limit=5&includeData=true")
    data=runs.get("data",[])
    for run in data:
        rid=run.get("id")
        full=api("GET",f"/executions/{rid}?includeData=true")
        result=full.get("data",{}).get("resultData",{})
        err=result.get("error") or {}
        print({"id":rid,"status":full.get("status"),"lastNodeExecuted":result.get("lastNodeExecuted"),
               "errorMessage":str(err.get("message") or err.get("description") or "")[:2000],
               "nodeRuns":{k:len(v) for k,v in result.get("runData",{}).items()}})
if __name__=="__main__": main()
