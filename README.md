# openqa-agnostic skill

Helps convert openQA security test modules into standalone
"openqa-agnostic" tests (see `data/security/openqa_agnostic/` for the
resulting artifacts). This file is for humans; `SKILL.md` is the actual
instructions the agent follows, `DESIGN.md` is the original design
rationale.

## Installation

Clone this repo to to `~/.claude/skills/`. If you plan to contribute then
fork this repo and then clone the fork to `~/.claude/skills/`.
Restart Claude after cloning and it will auto-discover the skill.
You can check it with `/skills` command.

## Prerequisites

- [Claude Code](https://docs.claude.com/en/docs/claude-code) new enough to
  support **project skills** (auto-discovered from `.claude/skills/`).
  If `/help` or your Claude Code docs don't mention "skills", update first.
- A checkout of this repo with the branch that contains this file (or, once
  merged, any checkout of `master`).
- No other setup. Claude Code scans `.claude/skills/*/SKILL.md` for every
  project it opens — there's no registration step, no config flag, no
  plugin marketplace involved. Start Claude Code with this repo as the
  working directory and the skill is already active.

## How to use it

Just ask, in your own words, from within a Claude Code session in this
repo. Two shapes:

- **"What's convertible?"** — e.g. *"what security tests can we convert to
  openqa-agnostic?"*, *"list openqa-agnostic candidates"*, *"what's
  convertible under tests/security/selinux/?"*. Runs Discovery: reads
  candidate modules and returns a prioritized list with reasoning per
  verdict. This is genuinely slow on a full-repo sweep (by design — see
  "Why serial, not parallel" below) — expect it to take a while for 200+
  files, fast for a scoped subdirectory.
- **"Convert this one"** — e.g. *"convert tests/security/apparmor/
  aa_disable.pm to openqa-agnostic"*, *"make this test agnostic"*. Runs
  Phase B directly: reads the target module, disqualifies it if it can't
  be converted (multi-machine, GUI/needle-dependent), otherwise scaffolds
  the new artifact under `data/security/openqa_agnostic/<name>/` and the
  thin wrapper under `tests/security/oqa_agnostic/<name>.pm`.

You can also invoke it explicitly with `/openqa-agnostic` if you want to be
sure it's this skill answering rather than a generic response.

The skill will always stop and ask before deleting the original `.pm`
module or touching `schedule/security/*.yaml` — those are shared,
production-affecting changes, not something it does silently.

## Scope

Only applies inside the "# Security" block of `.github/CODEOWNERS`
(`data/security/`, `lib/security/`, `schedule/security/`, `tests/security/`,
`tests/fips/`, etc.). Ask it to convert anything else and it will decline.

## Why serial, not parallel

An earlier iteration ran Discovery as a 400+ subagent parallel sweep via
Claude Code's Workflow tool. It worked, but cost ~22M tokens and ~19
minutes for one run. The skill was deliberately changed to process
candidates one at a time instead — slower, but with bounded, predictable
cost for routine use. See `git log -- .claude/skills/openqa-agnostic/` for
the full history if you're curious.

## Reference conversions

Six modules were already converted by hand before this skill existed —
they're the ground truth the skill points back to:

```
data/security/openqa_agnostic/{testPolkit,testPostQuantumCrypto,testApacheSSLPQC,goPostQuantum,java_hashing,yama}/
tests/security/oqa_agnostic/{polkit_rules,openssl_pqc,apachessl_pqc,go_post_quantum,java_hashing,yama}.pm
```

## Worked example

`examples/aa_disable/WALKTHROUGH.md` is a full trial run of Phase B against
a real module (`tests/security/apparmor/aa_disable.pm`), including the
disqualification reasoning, a real bug found while reading the delegated
helper, and the resulting files — kept as documentation, not applied live
(the original module and `schedule/security/apparmor.yaml` are untouched).
Read it if you want to see the abstract SKILL.md steps play out concretely
before running the skill for real.
