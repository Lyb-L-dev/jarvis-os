# Issue tracker: GitHub

Issues and specs for this repository live in GitHub Issues:

- Repository: `Lyb-L-dev/jarvis-os`
- CLI: `gh`

Run commands inside this repository so `gh` can infer the remote automatically.

## Conventions

- Create an issue:
  `gh issue create --title "..." --body-file <path>`
- Read an issue:
  `gh issue view <number> --comments`
- List issues:
  `gh issue list --state open --json number,title,body,labels,comments`
- Comment:
  `gh issue comment <number> --body "..."`
- Apply or remove labels:
  `gh issue edit <number> --add-label "..."`
  `gh issue edit <number> --remove-label "..."`
- Close:
  `gh issue close <number> --comment "..."`

Use a temporary Markdown file with `--body-file` for multiline issue bodies.

## Pull requests as a triage surface

**PRs as a request surface: no.**

Pull requests are not included in the issue triage queue unless this setting is changed manually.

GitHub shares one number sequence across issues and pull requests. When a bare reference such as `#42` is ambiguous, try `gh pr view 42` and then fall back to `gh issue view 42`.

## Skill terminology

When a skill says "publish to the issue tracker", create a GitHub issue.

When a skill says "fetch the relevant ticket", run:

`gh issue view <number> --comments`

## Wayfinding operations

The `wayfinder` skill represents a large initiative as one map issue with linked child issues.

- Map: one issue labelled `wayfinder:map`, containing Notes, Decisions-so-far and Fog.
- Child ticket: a GitHub sub-issue linked to the map. If sub-issues are unavailable, use a task list in the map and place `Part of #<map>` at the beginning of each child.
- Child labels: `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling` or `wayfinder:task`.
- Blocking: use native GitHub issue dependencies when available. Otherwise add `Blocked by: #<number>` to the child issue.
- Frontier: choose the first open child in map order that has no open blockers and no assignee.
- Claim: assign the selected issue to the current user with `gh issue edit <number> --add-assignee @me`.
- Resolve: comment with the result, close the child issue, and add a concise decision pointer to the map's Decisions-so-far section.
