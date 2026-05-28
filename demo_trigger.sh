#!/bin/bash
# Demo script to trigger a task and verification
R=$(curl -s -X POST "http://127.0.0.1:8000/tasks" -H "Content-Type: application/json" -d '{"description":"Demo pipeline: auto-remediation and verify"}')
echo "Response: $R"
TASK_ID=$(echo $R | jq -r .task_id)
echo "Started task: $TASK_ID"
sleep 1
curl -s -X POST "http://127.0.0.1:8000/verify/$TASK_ID"
echo "Verification started for $TASK_ID"
