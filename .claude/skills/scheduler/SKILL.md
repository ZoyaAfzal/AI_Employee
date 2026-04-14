---
name: scheduler
description: |
  Sets up and manages scheduled tasks using cron (Linux/Mac) or Task Scheduler (Windows).
  Schedules recurring AI Employee tasks like daily briefings, weekly audits, and watcher
  startup. Use when a task needs to run automatically at a set time or interval.
---

# Scheduler - AI Employee Skill

Automate recurring AI Employee tasks using cron (Linux/WSL/Mac) or Windows Task Scheduler.

## Platform Detection

```bash
# Detect platform
uname -a  # Linux/Mac/WSL
# If WSL: use cron (Linux) OR Windows Task Scheduler via PowerShell
```

This project runs in WSL2 on Windows. Use **cron** for Linux-side scheduling and
**Windows Task Scheduler** (via PowerShell) for Windows-side startup tasks.

## Workflow: Add a Cron Job (Linux/WSL)

### Step 1: View Existing Cron Jobs

```bash
crontab -l
```

### Step 2: Add New Cron Job

```bash
# Open crontab editor
crontab -e
```

**Cron format:**
```
# ┌───── minute (0-59)
# │ ┌───── hour (0-23)
# │ │ ┌───── day of month (1-31)
# │ │ │ ┌───── month (1-12)
# │ │ │ │ ┌───── day of week (0=Sun, 6=Sat)
# │ │ │ │ │
# * * * * * <command>
```

### Step 3: Standard AI Employee Cron Jobs

Add these to crontab for Silver Tier automation:

```cron
# ── AI Employee Scheduled Tasks ──────────────────────────────────

# Daily briefing: every day at 8:00 AM
0 8 * * * cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee" && claude --print "Use the vault-manager skill to generate today's briefing and update Dashboard.md" >> logs/cron.log 2>&1

# Weekly CEO briefing: every Monday at 7:00 AM
0 7 * * 1 cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee" && claude --print "Generate the Monday Morning CEO Briefing using vault contents from the past 7 days. Save to AI_Employee_Vault/Briefings/" >> logs/cron.log 2>&1

# Process Needs_Action: every 30 minutes during business hours (8am-8pm)
*/30 8-20 * * * cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee" && claude --print "Use vault-manager skill to check and process any files in AI_Employee_Vault/Needs_Action/" >> logs/cron.log 2>&1

# Check pending approvals: every 15 minutes
*/15 * * * * cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee" && claude --print "Use approval-workflow skill to check /Approved and /Rejected folders and process any decisions" >> logs/cron.log 2>&1

# LinkedIn post: every Tuesday and Thursday at 9:00 AM
0 9 * * 2,4 cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee" && claude --print "Use linkedin-poster skill to check if there is a pre-approved LinkedIn post in /Approved/ and post it" >> logs/cron.log 2>&1

# Start watchers on boot (if not already running)
@reboot cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee/watchers" && python3 main.py >> logs/watchers.log 2>&1
```

### Step 4: Verify Cron is Running

```bash
# Check cron service status (WSL)
service cron status

# Start cron if not running
sudo service cron start

# Verify your crontab was saved
crontab -l
```

### Step 5: Test a Cron Job

```bash
# Run the command manually to test
cd "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee"
claude --print "Use vault-manager skill to update Dashboard.md with current stats"
```

## Workflow: Windows Task Scheduler (PowerShell)

For tasks that need to run on the Windows side or survive WSL restarts:

### Create a Scheduled Task via PowerShell

```powershell
# Run in Windows PowerShell (not WSL)
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-e bash -c 'cd /mnt/c/Users/Admin/OneDrive/Desktop/AI_Employee && python3 watchers/main.py'"
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "AIEmployee_Watchers" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
```

### Start Watchers on Windows Login

```powershell
# Create startup task for watchers
$action = New-ScheduledTaskAction `
  -Execute "wsl.exe" `
  -Argument "-e bash -c 'cd /mnt/c/Users/Admin/OneDrive/Desktop/AI_Employee/watchers && python3 main.py >> logs/watchers.log 2>&1'"

$trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME

Register-ScheduledTask `
  -TaskName "AIEmployee_StartWatchers" `
  -Action $action `
  -Trigger $trigger `
  -Description "Start AI Employee watchers on login" `
  -Force
```

### List Existing Tasks

```powershell
Get-ScheduledTask | Where-Object {$_.TaskName -like "AIEmployee*"} | Select-Object TaskName, State
```

### Remove a Task

```powershell
Unregister-ScheduledTask -TaskName "AIEmployee_StartWatchers" -Confirm:$false
```

## Standard Schedule Reference

| Task | Frequency | Time | Skill Used |
|------|-----------|------|-----------|
| Process Needs_Action | Every 30 min (8am-8pm) | Business hours | vault-manager |
| Check Approvals | Every 15 min | Always | approval-workflow |
| Daily Briefing | Daily | 8:00 AM | vault-manager |
| LinkedIn Post | Tue & Thu | 9:00 AM | linkedin-poster |
| Weekly CEO Briefing | Every Monday | 7:00 AM | vault-manager |
| Start Watchers | On boot/login | — | watchers/main.py |
| Log Rotation | Daily | 11:59 PM | vault-manager |

## Workflow: Schedule a One-Time Task

For tasks that should run once at a specific time:

```bash
# Run at specific time using 'at' command
echo 'cd "/mnt/c/Users/Admin'"'"'/OneDrive/Desktop/AI_Employee" && claude --print "Generate monthly invoice summary"' | at 09:00 tomorrow

# List pending at jobs
atq

# Remove an at job
atrm <JOB_ID>
```

## Log Management

All cron output goes to `logs/cron.log`. Rotate weekly:

```bash
# Add to crontab for log rotation
0 0 * * 0 mv "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee/logs/cron.log" \
  "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee/logs/cron_$(date +%Y-%m-%d).log"
```

## Workflow: Audit Current Schedule

When asked to review what's scheduled:

```bash
# Show all cron jobs
crontab -l

# Show recent cron execution log
tail -50 "/mnt/c/Users/Admin'/OneDrive/Desktop/AI_Employee/logs/cron.log"
```

Summarize in Dashboard.md under `## Scheduled Tasks`.

## Enabling Cron in WSL (first-time setup)

```bash
# Install cron if not present
sudo apt-get install cron -y

# Enable cron service
sudo service cron start

# Make it auto-start (add to /etc/wsl.conf)
echo -e "[boot]\ncommand = service cron start" | sudo tee -a /etc/wsl.conf
```

## Rules

- ALWAYS log scheduled task output to `logs/cron.log` or `logs/<task_name>.log`
- NEVER schedule tasks that send money or emails without approval gates
- ALWAYS update Dashboard.md with the current schedule summary
- When removing a task: log the removal and reason
- Test new cron jobs manually before scheduling
- Use full absolute paths in cron commands (cron has minimal PATH)
