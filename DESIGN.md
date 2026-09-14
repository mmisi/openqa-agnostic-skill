# Original design plan

This is the plan approved before writing the first version of `SKILL.md`.
The skill has since evolved past it (multi-machine disqualification moved
from static grep to full semantic reasoning, a bootstrap/propaedeutic
exclusion tier was added, a mandatory self-verify pass was added for every
verdict, and Workflow/parallel-agent use was explicitly forbidden for
Discovery on cost grounds) — kept here as the historical rationale for why
the skill exists and what it was originally meant to cover.

---

## Skill: convert openQA security tests to openqa-agnostic tests

### Context

QE Security is building a library of "openqa-agnostic" tests: standalone
test artifacts (bash/python/go/java) that assert security behavior directly
on a SUT, runnable both inside openQA (via a thin `.pm` wrapper) and outside
it (any machine with the runtime installed). Six examples already exist
under `data/security/openqa_agnostic/` (testPolkit, testPostQuantumCrypto,
testApacheSSLPQC, goPostQuantum, java_hashing, yama) with matching wrappers
in `tests/security/oqa_agnostic/`, all driven by the shared
`lib/security/agnosticTestRunner.pm`.

Converting an existing openQA test module into this shape is mechanical but
easy to get wrong in the details (METADATA block fields, `runtest` argument
contract, result format per language, helper.sh sourcing path). We want a
SKILL.md that walks Claude through the conversion so future ports follow the
established pattern instead of reinventing it.

Scope is limited to the "# Security" block of `.github/CODEOWNERS`:
`data/security/`, `lib/security/`, `lib/main_security.pm`,
`lib/eal4_test.pm`, `lib/selinuxtest.pm`, `schedule/security/`,
`test_data/security/`, `tests/security/`, `tests/fips/`.

### Deliverable

`.claude/skills/openqa-agnostic/SKILL.md` (project skill, committed to the
repo) with frontmatter:

```yaml
name: openqa-agnostic
description: >
  Convert an existing openQA security test module (tests/security/**/*.pm)
  into a standalone "openqa-agnostic" test that also runs outside openQA,
  or scaffold a brand-new one. Scope: the "# Security" paths in
  .github/CODEOWNERS only. Use when asked to "make this test agnostic",
  "port this to openqa-agnostic", "convert this security test to run
  standalone", or to add a new security test that should be agnostic-first.
```

### Content outline for SKILL.md

**1. Perimeter check (first, always)**
Before touching anything, confirm the target module's path falls under the
Security CODEOWNERS entries. Read `.github/CODEOWNERS`, extract the paths
listed under the `# Security` comment block (don't hardcode the list —
CODEOWNERS is the source of truth and may grow). If the requested file is
outside that perimeter, stop and tell the user this skill doesn't apply.

**2. Explain the architecture** (so the model reasons correctly about where
each piece goes), grounded in the real files:
- `lib/security/agnosticTestRunner.pm` — generic OO helper:
  `new({language, name})->setup->run_test->parse_results->cleanup`.
  `language` must be exactly `go`, `python`, or `java` (the constructor
  dies otherwise). `setup` zypper-installs the right runtime
  (`go gotestsum` / `python3-pytest` / latest `java-*-openjdk-devel`),
  downloads `security/openqa_agnostic/<name>/` from `data_url`, plus the
  shared `lib/helper.sh` one level up. `run_test` executes `./runtest`,
  captures `results.xml` (XUnit, go/python) or `results.tap` (TAP, java),
  and calls `parse_extra_log`. `cleanup` just `rm -rf`s the test dir on the
  SUT — it does NOT restore application state, so state teardown belongs in
  the test itself.
- `data/security/openqa_agnostic/<TestName>/` — the portable artifact:
  language source file(s) + a `runtest` script. Show the exact `runtest`
  contract (use `data/security/openqa_agnostic/testPolkit/runtest` and
  `yama/runtest` as the canonical templates):
  - shebang, then a `# METADATA_START` / `# METADATA_END` YAML block with
    fields `test`, `desc`, `steps`, `author`, `maintainer`
    (`QE Security <none@suse.de>`), `expected`, `platform`, `tags`.
  - `source ../lib/helper.sh`, `TEST_FILES=(...)` listing every file the
    runner must download besides `runtest` itself, `handle_args "$0" "$@"`
    (implements `-h/--help`, `-m/--metadata` dump, `-f/--files` list — the
    runner's `setup()` calls `-f` to know what to fetch).
  - the actual invocation: `pytest <file> --junitxml=results.xml` (python),
    `gotestsum --format=standard-verbose --junitfile results.xml` after
    `go clean -testcache` (go), or `javac x.java && java x > results.tap`
    with hand-rolled TAP output (java — no JUnit runner available on the
    SUT, see `java_hashing/FipsJcaProviderTest.java`'s `ok()`/`fail()`).
  - note the yama pattern of relaxing `set -e` around the pytest call so a
    test *failure* (non-zero pytest exit) doesn't stop `results.xml` from
    being produced/uploaded — only a missing results file is a hard error.
- `data/security/openqa_agnostic/lib/helper.sh` — shared `handle_args`,
  `ensure_root`, `ensure_command_available`. Never duplicate this logic
  into a new `runtest`; source it.
- `tests/security/oqa_agnostic/<name>.pm` — thin wrapper:
  `select_serial_terminal`, any openQA-only pre-steps that can't be
  expressed as portable shell (package install via `zypper_call`/
  `install_package`, reboots via `power_action`/`wait_boot`, version-gate
  skip logic via `is_sle`/`is_tumbleweed` with `record_info`), then
  `security::agnosticTestRunner->new({language => ..., name => ...})
  ->setup()->run_test()->parse_results()->cleanup();`. Note the one
  exception in the codebase (`go_post_quantum.pm`) that bypasses the runner
  entirely for a simple stdout-substring check with no XUnit/TAP — call
  this out as legacy, not the pattern to copy.
- Scheduling: the module is referenced by its openQA path
  (`security/oqa_agnostic/<name>`) from a `schedule/security/*.yaml` file,
  e.g. `schedule/security/yama.yaml`.

**3. Conversion workflow**
1. Perimeter check (step 1).
2. Read the source `.pm` fully. Classify every action:
   - **Portable** (`assert_script_run`, `script_run`, `script_output`,
     `validate_script_output`) — these map 1:1 onto shell/python/go
     statements: run a command, check exit code, regex-match output. Use
     `tests/security/usbguard/usbguard.pm` as a worked example of a module
     that is *entirely* portable (no needles/screen matching) — a good
     conversion candidate.
   - **openQA-only** (`select_console`/`select_serial_terminal`,
     `zypper_call`, `install_package`, `power_action`+`wait_boot`,
     `record_info`/`record_soft_failure`, `is_sle`/`is_tumbleweed` gating,
     needle/screen assertions) — these stay in the `.pm` wrapper, or if
     trivial (e.g. `command -v foo`), get re-expressed as a portable
     runtime check/skip inside the agnostic test.
   - **Not portable** — needle matching, VNC/GUI interaction, multi-machine
     orchestration, physical TPM presence, etc. If the module leans on
     these for its core assertions, it is NOT a good conversion candidate;
     say so and stop rather than forcing a bad port.
3. Pick the language: bash for plain CLI-driven checks with no data
   structures worth modeling; python+pytest for parametrized/fixture-heavy
   cases; go when native crypto/TLS/networking primitives are needed
   (reuse `testPolkit/utils.go`'s `RunCommandTimeout` helper rather than
   reinventing subprocess handling); java only for JVM/JCA-specific
   testing.
4. Scaffold `data/security/openqa_agnostic/<TestName>/` with the source
   file(s) and a `runtest` following the template in step 2, including a
   complete METADATA block (ask the user for `author` if not inferable
   from `git config user.email` / recent commits).
5. Write `tests/security/oqa_agnostic/<name>.pm` per the wrapper template,
   porting over any openQA-only pre-steps found in step 2 verbatim where
   possible, preserving the original `test_flags` (`always_rollback`)
   unless there's a reason to change it — flag if unsure.
6. Wire scheduling: add/update the `security/oqa_agnostic/<name>` entry in
   the schedule YAML that referenced the old module.
7. Flag the old `.pm` module (and any now-unused schedule entry) for
   removal — ask for explicit confirmation before deleting, since other
   YAML files or job groups may still reference it.
8. Validate what can be validated locally without a full SUT: `./runtest
   -h`, `./runtest -m`, `./runtest -f` should all work standalone (they
   only depend on `helper.sh`, not the SUT). Say explicitly that the actual
   test steps still needs a real SUT run (or the ssh/scp loop already used
   in this repo's `.claude/settings.local.json` against a local VM) —
   never claim the ported test passes without having run it.

**4. Hard constraints to state explicitly in the skill**
- `language` in `agnosticTestRunner->new()` is only `go|python|java` —
  never invent another value.
- `result_format`/`result_file` are derived automatically from `language`;
  don't override them.
- `name` passed to `new()` must match the `data/security/openqa_agnostic/<name>`
  directory name exactly (it drives both `data_url_path` and `test_dir`).
- `helper.sh` is sourced as `../lib/helper.sh` — this only works because
  `setup()` downloads it to a sibling `lib/` dir one level above
  `test_dir`; don't change that layout.
- Never touch files outside the Security CODEOWNERS perimeter as part of
  this skill.

### Verification

- `cat .claude/skills/openqa-agnostic/SKILL.md` renders with valid
  frontmatter (name + description) mirroring the format used by
  `~/.claude/plugins/marketplaces/improve/skills/improve/SKILL.md`.
- Dry-run the skill mentally against `tests/security/usbguard/usbguard.pm`
  (a fully-portable, non-agnostic module) and confirm the workflow it
  prescribes produces the same shape as the six existing examples.
- No source/test files are modified — this task only adds the one new
  SKILL.md file.
