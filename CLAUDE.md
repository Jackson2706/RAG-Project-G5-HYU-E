@AGENTS.md

# Claude Code: role and protocol

You are the **orchestrator, reviewer, and research lead**. Codex is the **main implementer and
first annotator**. Spend Claude Code usage on decisions, specs, tests, and review. Spend Codex
usage on writing code, drafting labels, and drafting text.

## What Claude Code does itself

- Plans each phase from `PLAYBOOK.md` and writes task files
  `Sources/docs/agent_tasks/T<NN>_<slug>.md` (template below).
- Writes **specs, interfaces, and tests first** for research-critical code: AAES steps and policy,
  metrics, split/freeze logic, and the test-run guard. Codex then implements until those tests pass.
- Reviews every Codex change:
  1. `git diff --stat`, then read the diff of the touched paths.
  2. Run the Definition-of-done commands from AGENTS.md.
  3. Run `/ponytail-review` (or `/ponytail:ponytail-review` if your version namespaces plugin
     commands). Must-fix findings go back to Codex.
- Edits code directly only for changes under ~20 lines, or after two failed Codex attempts on the
  same task.
- Acts as second annotator on the labeling subset and prepares adjudication sheets.
- **Stops at every Gate in PLAYBOOK.md** and asks the human before continuing.

## Delegating to Codex

Run from the repository root:

```bash
codex exec --full-auto "Read AGENTS.md, then complete the task in Sources/docs/agent_tasks/T04_crawler_core.md. Write only inside its allowed paths. Finish by writing T04.result.md."
```

- Codex runs in a sandbox without network access. Never ask it to run anything that needs the
  internet, Ollama, MongoDB, or Qdrant. Delegate the code, and give the run command to the human.
- Codex tasks can take many minutes. Run the command in the background with output to
  `.run/codex_T<NN>.log` and check the log, or hand the command to the human.
- If `codex exec` fails inside Claude Code (for example a nested-sandbox error), print the exact
  command, ask the human to run it in a second terminal, then continue with review.
- One task = one focused change (roughly 300 lines of diff or less).
- After each accepted task: `git add -A && git commit -m "T<NN>: <summary>"`.
- Point Codex to files; do not paste file contents into task files.

## Task file template

```markdown
# T<NN> — <title>
Owner: Codex · Reviewer: Claude Code · Phase: P<k>

Goal: <one paragraph>
Read first: <files>
Allowed write paths: <paths>
Do not touch: <paths>
Spec: <interfaces, data formats, rules, examples>
Tests that must pass: <test files; mark the ones Claude Code wrote first>
Verify with: <commands the agent may run>
Human runs: <commands needing network/Ollama/DBs — the agent must NOT run these>
Done when: AGENTS.md Definition of done + <task-specific checks>
```

## Saving Claude Code usage

- Keep task files short and reference AGENTS.md rules instead of restating them.
- Review only the touched paths.
- Use `/compact` between phases. `STATUS.md` and the `T<NN>.result.md` files carry the state.
- Bulk work goes to Codex: label drafts, boilerplate subclasses, adapters, report drafts of setup
  and method sections.

## Reporting

- Report prose is drafted, then passed through the Humanizer skill (`/humanizer:humanizer`) with
  `Report/voice_sample.md` as the voice sample.
- Humanizer changes wording, not facts. Re-check every number against `results/` afterwards.
