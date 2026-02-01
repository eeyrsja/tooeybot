# Memo

## Phase 2 Agent Design: Conversational, Curious, Self-Directed TUI Bot

### Purpose of this Memo

This memo defines the **design goals, guiding principles, and functional requirements** for the next phase of the TUI agent system.

Phase 1 established a functional, single-shot agent.
Phase 2 must evolve this into a **stateful, conversational, curiosity-driven agent** that can reason over time, generate and manage its own tasks, and remain bounded, inspectable, and safe.

This document specifies **what the system must do and why**, not how it is implemented.

---

## 1. Core Intent

The agent is not a chat assistant.

It is a **goal-driven autonomous system** that:

* Works iteratively over multiple reasoning cycles
* Maintains internal state across turns
* Reflects on its own actions
* Expands its workload through structured curiosity
* Decides when to continue, pause, or stop

Conversation emerges from **iteration and reflection**, not free-form dialogue.

---

## 2. Fundamental Design Principles

### 2.1 Iterative, Not One-Shot

The agent must operate as a loop, not a single request/response interaction.

Each cycle must:

* Decide what to do next
* Take exactly one action
* Observe the result
* Reflect on progress
* Decide whether to continue, expand, pause, or finish

### 2.2 State Is Explicit and Persistent

All reasoning happens against an explicit, inspectable state.

The agent:

* Does not rely on implicit memory
* Does not “remember” outside of recorded state
* Can be stopped, restarted, and resumed without losing intent

This is essential for:

* Debugging
* Safety
* Trust
* Long-running tasks

---

## 3. The Agent Loop (Conceptual)

The agent operates continuously through the following conceptual phases:

```
INITIALISE → PLAN → ACT → OBSERVE → REFLECT → (EXPAND?) → DECIDE → …
```

This loop continues until:

* The goal is satisfied
* The agent requires user input
* A safety or budget constraint is reached

Reflection is the **control point** of the system.

---

## 4. Task-Centric Operation

### 4.1 Everything Is a Task

All work performed by the agent is represented as a task, including:

* User-requested work
* Planned subtasks
* Curiosity-driven exploration
* Error recovery and verification

There are no “hidden” activities.

### 4.2 Task Origins Matter

Each task must record its origin:

* User
* Plan
* Curiosity
* Recovery

This allows:

* Analysis of agent behaviour
* Control of curiosity
* Future prioritisation and pruning
* Debugging task explosion

---

## 5. Conversational Behaviour Through Reflection

The agent’s “conversation” is internal and structured.

After every action, the agent must explicitly reflect on:

* Whether progress was made
* What new information was learned
* Whether the plan is still valid
* Whether additional work is justified

This reflection step is mandatory and central to correctness.

---

## 6. Curiosity as a First-Class Capability

### 6.1 What “Curious” Means

A curious agent:

* Actively looks for gaps, risks, improvements, or missing information
* Proposes additional tasks that increase correctness, robustness, or understanding
* Treats curiosity as *work*, not speculation

Curiosity is **productive**, not wandering.

### 6.2 Curiosity Is Structured and Bounded

The agent:

* May propose new tasks during reflection
* Must justify why each new task is valuable
* Must operate within explicit limits to prevent runaway behaviour

Curiosity is encouraged, but **never unbounded**.

---

## 7. Separation of Responsibilities

The system conceptually separates:

* **Planning and ideation** (including curiosity)
* **Execution of actions**
* **Critical reflection and validation**

This separation ensures:

* Actions remain deliberate
* Creativity does not directly trigger execution
* The agent cannot “do everything at once”

---

## 8. Single-Action Discipline

At each step, the agent must choose **exactly one next action**, such as:

* Perform a tool operation
* Ask the user for clarification
* Perform internal reasoning
* Declare completion

This rule exists to:

* Prevent ambiguity
* Enable replay and debugging
* Keep the loop deterministic

---

## 9. Budgeting and Safety Constraints

The agent must operate under explicit limits, including:

* Maximum reasoning iterations
* Maximum number of tasks it may create
* Maximum number of active tasks
* Limits on repeated failures or lack of progress

These are **hard constraints**, not suggestions.

The purpose is to:

* Prevent infinite loops
* Prevent exponential task growth
* Force graceful stopping or user intervention

---

## 10. Non-Progress and Recovery Awareness

The agent must be able to recognise when it is stuck.

Indicators include:

* Repeating the same task without progress
* Repeating the same error
* Making no measurable progress over multiple cycles

When detected, the agent must:

* Stop autonomous operation
* Ask the user for guidance
* Or create explicit recovery work

Silent failure or infinite retrying is unacceptable.

---

## 11. Error Visibility and Recovery

Errors are first-class events.

The agent must:

* Record errors explicitly
* Reason about why they occurred
* Decide whether to retry, recover, or escalate
* Create recovery tasks where appropriate

Errors are never ignored or hidden.

---

## 12. Context and Scale Awareness

The agent must be designed with the assumption that:

* State grows over time
* Tool outputs may be large
* Context windows are finite

Therefore:

* Not all history is always active
* Older information may be summarised
* Detailed data must remain retrievable when needed

This ensures long-running sessions remain viable.

---

## 13. Explicit Capabilities Awareness

The agent must have an explicit understanding of:

* What it can do
* What it cannot do
* What environment it is operating in

When uncertain, the agent should:

* Check its stated capabilities
* Experiment cautiously
* Record what it learns

This supports autonomy without hallucination.

---

## 14. Transparency and Inspectability

At all times, it must be possible to inspect:

* The current goal
* The plan
* The task list
* Recent actions and reflections
* Why new tasks were created

This transparency is essential for trust, debugging, and future governance.

---

## 15. Out of Scope (For This Phase)

This phase explicitly does **not** aim to:

* Optimise task prioritisation beyond simple rules
* Learn long-term preferences or styles
* Self-modify its own architecture
* Operate without clear bounds or budgets

Those may be future phases.

---

## 16. Success Criteria

Phase 2 is successful if the agent:

* Operates over multiple reasoning cycles without user intervention
* Can expand its own workload responsibly
* Stops when appropriate
* Recovers from errors
* Remains inspectable and bounded
* Feels *purposeful*, not chatty

---

## Closing Statement

This phase transforms the system from:

> “A tool that answers once”

into:

> **“An agent that works.”**

The defining characteristics are:

* Reflection over time
* Explicit state
* Structured curiosity
* Hard limits
* Clear intent

If these requirements are met, the system becomes a solid foundation for later prioritisation, learning, and autonomy—without sacrificing control.