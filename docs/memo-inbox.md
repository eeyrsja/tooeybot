# Memo

## Asynchronous User–Agent Communication via Internal Messaging (Email-Like System)

### Purpose of this Memo

This memo defines the **requirements and design intent** for adding an **asynchronous communication channel** between the agent and the user, to replace the assumption that the user is present at a console.

The agent must be able to:

* Ask the user questions
* Receive clarifications or instructions
* Continue work after a delay

The user must be able to:

* Interact with the agent without being logged into a terminal
* Review agent messages and respond at their convenience

This capability is essential to support **long-running, autonomous agent operation**.

---

## 1. Core Problem Statement

The current agent design assumes synchronous interaction:

* The agent asks a question
* The user is present to answer immediately

This assumption does **not** hold for realistic usage.

The agent must be able to **pause**, **communicate asynchronously**, and **resume** when the user replies.

---

## 2. Design Goals

### 2.1 Asynchronous by Default

User–agent communication must:

* Not require the user to be present at execution time
* Not block the system indefinitely
* Allow hours or days between messages

The agent must be comfortable operating unattended.

---

### 2.2 Message-Based, Not Interactive

Communication is **message-based**, not conversational in real time.

Messages:

* Are discrete
* Are persisted
* Have clear sender/recipient semantics
* Can be inspected and audited

This aligns with the agent’s stateful, task-driven nature.

---

### 2.3 Decoupled from Execution Loop

The agent’s reasoning loop must not depend on:

* Live user input
* Terminal I/O
* Interactive prompts

Instead:

* The agent transitions into a waiting state
* The loop resumes only when a message is received

---

## 3. Conceptual Model

The system introduces an **internal messaging channel**, conceptually similar to email.

Key characteristics:

* Asynchronous
* Persistent
* Addressable
* Auditable

This is **not** a human email product; it is an internal messaging mechanism with email-like semantics.

---

## 4. Agent Behaviour Requirements

### 4.1 Asking the User a Question

When the agent requires user input, it must:

* Generate a clear, concrete message
* Specify what decision or information is needed
* Provide sufficient context for the user to answer without prior state

At this point, the agent must:

* Record the question in its state
* Transition to a `waiting_user` status
* Suspend autonomous execution

---

### 4.2 Waiting State Semantics

While in `waiting_user`:

* The agent performs no further actions
* No new tasks are executed
* Budgets do not advance
* State remains stable and inspectable

This is a **deliberate pause**, not a failure.

---

### 4.3 Receiving User Messages

When a user message is received:

* The message is persisted
* The agent state is updated
* The message is treated as new authoritative input

The agent must:

* Resume execution
* Interpret the message in the context of the paused question
* Decide how it affects existing tasks, plans, or assumptions

---

## 5. Message Semantics

### 5.1 Message Types

Messages exchanged between user and agent must be typed, for example:

* Question
* Answer
* Clarification
* Instruction
* Status update
* Completion summary

Typing is required for:

* Correct interpretation
* Auditing
* Future automation

---

### 5.2 Message Content Requirements

All messages from the agent must:

* Be self-contained
* Reference the relevant task or decision
* Avoid assumptions that the user remembers prior context
* Be written for delayed reading

This avoids confusion when replies arrive much later.

---

## 6. Persistence and Auditability

All messages must be:

* Persisted to durable storage
* Linked to the agent run/session
* Timestamped
* Immutable once sent

This ensures:

* Full traceability of decisions
* Debuggability
* Compliance with the agent’s transparency goals

---

## 7. Relationship to the Agent Loop

The messaging system integrates with the agent loop as follows:

* **Outgoing message** → agent enters `waiting_user`
* **Incoming message** → agent resumes loop
* **Message content** → treated as new user input

From the agent’s perspective:

* Messaging is just another way of receiving user input
* It does not change planning, reflection, or curiosity mechanisms

---

## 8. Interaction with Tasks and Curiosity

### 8.1 User Replies as Task Modifiers

User messages may:

* Resolve a blocked task
* Change task priority
* Add new constraints
* Introduce new goals

The agent must reflect on user input in the same structured way it reflects on tool outputs.

---

### 8.2 Curiosity While Waiting

While in `waiting_user`:

* The agent must not generate new tasks
* The agent must not continue exploration

Curiosity resumes only after user input is processed.

This prevents runaway behaviour during long waits.

---

## 9. Failure and Timeout Considerations

The system must allow for:

* No reply
* Delayed reply
* Ambiguous reply

Policies must exist for:

* Escalation after prolonged silence
* Re-asking or rephrasing questions
* Graceful termination if user never responds

These policies should be explicit, not implicit.

---

## 10. Security and Scope Boundaries

The messaging system must:

* Clearly separate agent-originated messages from user-originated messages
* Prevent message spoofing
* Ensure messages cannot directly mutate state without agent mediation

All user input is interpreted, never blindly executed.

---

## 11. Non-Goals (Explicit)

This phase does **not** require:

* Real-time chat
* User presence during execution
* Integration with external email providers

The goal is **reliable asynchronous communication**, not user experience polish.

---

## 12. Why an Email-Like Model Is the Right Abstraction

An email-style model:

* Matches asynchronous human behaviour
* Encourages clear, complete questions
* Creates a durable decision trail
* Avoids false assumptions of immediacy

It aligns with the broader agent philosophy:

> deliberate, inspectable, and autonomous — but never opaque.

---

## 13. Success Criteria

This capability is successful if:

* The agent can pause indefinitely awaiting user input
* Users can respond without accessing a terminal
* The agent resumes correctly after delays
* All communication is visible, persistent, and attributable
* No part of the agent loop assumes synchronous interaction

---

## Closing Statement

Adding asynchronous messaging is **not an accessory feature**.

It is a **structural requirement** for any agent intended to:

* Run unattended
* Perform non-trivial work
* Collaborate meaningfully with humans

This memo establishes the conceptual and behavioural requirements for that capability, without constraining implementation choices.