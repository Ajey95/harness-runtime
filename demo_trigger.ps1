# Demo PowerShell script to trigger a task and verification
$body = @{ description = 'Demo pipeline: auto-remediation and verify' } | ConvertTo-Json
$r = Invoke-RestMethod -Uri http://127.0.0.1:8000/tasks -Method POST -Body $body -ContentType 'application/json'
Write-Host "Started task:" $r.task_id
Start-Sleep -Seconds 1
Invoke-RestMethod -Uri "http://127.0.0.1:8000/verify/$($r.task_id)" -Method POST
Write-Host "Verification started for" $r.task_id
