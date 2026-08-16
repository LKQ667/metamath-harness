---
name: grill-me
description: A relentless interview to sharpen a plan or design.
---

Run a `/grilling` session.

Do not modify code, files, configuration, or repository state during this mode; only question, analyze, and refine the user's plan or design.

Use Codex's `tool/requestUserInput` prompt UI for each grilling question: ask one clear, specific question with 3 meaningful preset options, including an `isOther` free-form option for user-defined responses.

If the user uses the custom/free-form option to ask a question, request clarification, or challenge a premise, answer briefly and accurately, then continue by presenting the next planned grilling question through the `tool/requestUserInput` prompt UI.

Do not treat custom/free-form responses as an interruption or as permission to exit the grilling flow. Remain in `/plan` mode until every planned question has been asked.
