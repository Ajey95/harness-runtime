# Harness Runtime — Engineering Build Guidelines

## Project Mission

You are building:

# “Harness Runtime”

A supervisory runtime for autonomous AI engineering agents like Codex.

This is NOT:

* a chatbot
* a coding assistant
* an IDE replacement
* a generic AI wrapper

This IS:

* an operational control plane for AI engineers
* a verification-first AI execution runtime
* an observability and governance system for autonomous coding agents

The MVP demonstrates:

> how humans can safely supervise autonomous AI engineering workflows in production-style environments.

---

# Core Product Philosophy

The product should feel like:

* Datadog for AI engineers
* PagerDuty for autonomous coding agents
* Kubernetes-style orchestration for AI execution workflows
* an operational runtime for AI systems

The runtime supervises:

* execution
* remediation
* verification
* approvals
* observability
* recovery workflows

Codex is treated as:

# a supervised operational worker.

---

# MOST IMPORTANT RULE

Do NOT overbuild.

The system only needs ONE perfect workflow.

Everything should optimize for:

* clarity
* reliability
* observability
* demo quality
* operational realism

NOT feature breadth.

---

# MVP GOLDEN WORKFLOW

This is the ONLY workflow that must work flawlessly.

```text id="jq4r5d"
Docker service failure
        ↓
Harness Runtime detects issue
        ↓
Codex task triggered automatically
        ↓
Codex analyzes logs/config/repository
        ↓
Runtime captures traces + tool calls
        ↓
Risk middleware evaluates action
        ↓
Human approval requested
        ↓
Codex proposes remediation
        ↓
Fix/patch applied
        ↓
Verification tests executed
        ↓
Recovery validated
        ↓
Dashboard visualizes execution lifecycle
        ↓
Incident report generated
```

If this workflow works beautifully:

# the MVP succeeds.

---

# PRODUCT POSITIONING

The system should emphasize:

## 1. Supervision

Humans supervise AI engineers.

---

## 2. Observability

Every AI action is traceable.

---

## 3. Verification

Generated fixes must be validated.

---

## 4. Governance

Risky actions require approval.

---

## 5. Operational Intelligence

The runtime manages AI workflows like infrastructure systems.

---

# WHAT TO BUILD

# REQUIRED MVP COMPONENTS

---

# 1. Harness Runtime Backend

## Responsibilities

* orchestration
* workflow management
* execution lifecycle
* middleware coordination
* trace management

## Tech

* FastAPI
* async architecture

## Requirements

* modular structure
* typed APIs
* clean service separation

---

# 2. Codex Execution Layer

## Responsibilities

* trigger Codex CLI
* execute tasks
* capture stdout/stderr
* monitor execution status
* collect tool usage

## Requirements

* subprocess isolation
* timeout handling
* retry handling
* structured logs

## Important

Codex is the worker.
The runtime is the supervisor.

---

# 3. Failure Simulation Environment

## Responsibilities

Provide deterministic demo scenarios.

## Recommended Setup

Docker Compose environment with:

* nginx
* failing API
* broken config
* unhealthy service

## Goal

Create realistic operational incidents.

---

# 4. Monitoring Layer

## Responsibilities

* container health monitoring
* service status tracking
* log collection
* metric collection

## Minimal Requirements

* Docker SDK
* health checks
* logs API

## Avoid

Overengineering Prometheus stacks unless time permits.

---

# 5. Middleware Governance Layer

This is VERY important.

## Responsibilities

* classify risk
* gate execution
* require approval
* log middleware decisions

## Middleware Types

### Approval Middleware

Requests human confirmation.

---

### Risk Middleware

Classifies:

* safe
* medium-risk
* dangerous actions

---

### Execution Policy Middleware

Restricts:

* shell commands
* filesystem access
* dangerous operations

---

# 6. Verification Layer

This is the MOST important differentiator.

The system should NOT stop after:

> “Fix generated.”

It must continue until:

* tests pass
* service recovers
* health checks succeed
* endpoint stabilizes

## Verification Requirements

* health endpoint checks
* container status checks
* test execution
* rollback-safe logic

## Verification Output Example

```json
{
  "verification_status": "passed",
  "health_check": "200 OK",
  "service_status": "healthy",
  "tests_passed": true
}
```

---

# 7. Observability System

This is what makes the project memorable.

## Capture

* traces
* spans
* tool calls
* execution latency
* middleware lifecycle
* approvals
* remediation actions

## Trace Lifecycle Example

```text id="95krjz"
Incident Detected
    ↓
Diagnosis Started
    ↓
Codex Execution
    ↓
Tool Calls
    ↓
Risk Evaluation
    ↓
Approval Granted
    ↓
Patch Applied
    ↓
Verification Started
    ↓
Recovery Successful
```

---

# 8. Dashboard

The dashboard should feel:

* operational
* production-like
* real-time
* infrastructure-grade

## Recommended Stack

* Next.js
* Tailwind
* React Flow

---

# Dashboard Sections

## Incident Timeline

Chronological execution events.

---

## Trace Graph

Visual node graph of:

* reasoning
* actions
* middleware decisions
* verification lifecycle

---

## Tool Calls Panel

Show:

* executed tools
* commands
* duration
* outputs

---

## Approval Panel

Show:

* pending approvals
* risk classification
* action status

---

## Verification Panel

Show:

* recovery status
* test results
* health checks

---

# IMPORTANT ARCHITECTURAL RULES

# 1. Keep Architecture Flat

DO NOT:

* build microservices
* distribute components
* add unnecessary queues
* add distributed orchestration

Use:

* one backend service
* clean modules
* async workers only where needed

---

# 2. Focus On Operational Realism

Everything should feel:

* like real infrastructure
* like production workflows
* like incident management systems

Avoid:

* toy chatbot UX
* casual AI assistant design
* “chat-first” interactions

---

# 3. Make Observability First-Class

Every major event should generate:

* traces
* spans
* logs
* timestamps
* execution metadata

---

# 4. Prioritize Demo Reliability

The system must:

* fail predictably
* recover consistently
* demonstrate the same workflow repeatedly

Avoid:

* nondeterministic AI flows
* unstable infra
* excessive autonomy

---

# DESIGN PRINCIPLES

# Principle 1 — Runtime Over Chatbot

This is an operational runtime.
Not a chat UI.

---

# Principle 2 — Verification Over Generation

Generated output alone is insufficient.
Verification is mandatory.

---

# Principle 3 — Governance Over Autonomy

AI agents are supervised workers.
Not unrestricted actors.

---

# Principle 4 — Observability Over Magic

Users should see:

* how the agent reasons
* what actions it took
* why decisions were made
* how failures were resolved

---

# UI/UX GUIDELINES

# Visual Direction

The dashboard should resemble:

* Datadog
* Grafana
* LangSmith
* Temporal
* Kubernetes dashboards

NOT:

* ChatGPT
* Discord bots
* IDE copilots

---

# Color & Layout Direction

Focus on:

* operational clarity
* trace readability
* timeline visibility
* system-state awareness

Use:

* cards
* timelines
* graph views
* incident panels
* metrics displays

---

# ENGINEERING PRIORITIES

# P0 — MUST WORK

## Critical Flow

* failure detection
* Codex execution
* remediation
* verification
* dashboard traces

---

# P1 — IMPORTANT

## Strong UX

* live updates
* graph animations
* clean traces
* structured logs

---

# P2 — OPTIONAL

Only if time permits:

* persistent history
* advanced graph layouts
* websocket streaming
* replay system

---

# WHAT NOT TO BUILD

DO NOT BUILD:

* Kubernetes integration
* multi-agent systems
* memory systems
* RL optimization
* vector databases
* cloud orchestration
* enterprise auth
* distributed runtimes

These are explicitly deferred.

---

# DEMO GOAL

At the end of the hackathon, the demo should clearly communicate:

> “Autonomous AI engineers require supervision, verification, observability, and operational governance to safely operate in production environments.”

That is the core thesis of Harness Runtime.

---

# SUCCESS CONDITION

The MVP succeeds if the audience can clearly see:

* a real operational incident
* Codex autonomously attempting remediation
* the runtime supervising execution
* middleware enforcing safety
* verification validating recovery
* traces visualizing the entire lifecycle

That alone is enough for a strong hackathon submission.
