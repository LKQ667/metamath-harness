# Issue Tracker: Local Markdown

Issues and specifications in this repository are stored as Markdown files under `.scratch/`.

## Conventions

- Use one directory per feature: `.scratch/<feature-slug>/`
- The specification file is `.scratch/<feature-slug>/spec.md`
- Use an individual file for each implementation task: `.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- Number tasks starting from `01`; do not use a single combined task file
- Append comments and discussion history under the `## Comments` section at the bottom of the file

## When a Skill Requires "Post to Issue Tracker"

Create a new file under `.scratch/<feature-slug>/`; create the directory if it does not exist.

## When a Skill Requires "Fetch Relevant Task"

Read the file pointed to by the referenced path. Users will typically provide the file path or task number directly.

## Wayfinding Operations

For use with `/wayfinder`. A map file corresponds to multiple task subfiles.

- **Map**: `.scratch/<effort>/map.md`, containing Notes, Decisions-so-far, and Fog
- **Subtask**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered starting from `01`, with the body recording the problem
- `Type:` line records task type: `research`, `prototype`, `grilling`, or `task`
- `Status:` line records status: `claimed` or `resolved`
- **Dependencies**: Use `Blocked by: NN, NN` near the top of the file
- **Workable Frontier**: Scan `.scratch/<effort>/issues/`, select tasks that are unresolved, unblocked, and unclaimed, prioritizing the lowest number
- **Claim**: Update status to `Status: claimed` and save before starting work
- **Resolve**: Append the answer under the `## Answer` header, update status to `Status: resolved`, and append the summary and link to Decisions-so-far in `map.md`
