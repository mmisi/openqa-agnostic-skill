# Worked example: `tests/security/apparmor/aa_disable.pm`

A full run of the skill's Phase B (Conversion) against one real module, kept
here for reference. **These files are examples only** — applying this
conversion for real means creating them at their real repo paths (shown
below), not inside `.claude/skills/`. This example was trialed live once,
then moved here without wiring it in (schedule untouched, original module
untouched) — see "What's left" at the bottom.

## The original module

`tests/security/apparmor/aa_disable.pm` (18 lines):

```perl
use Mojo::Base 'apparmortest';
use testapi;
use utils;

sub run {
    my ($self) = @_;

    $self->test_profile_content_is_special("aa-disable", "Disabling.*");
}

1;
```

All the real logic is delegated to `apparmortest::test_profile_content_is_special`
in `lib/apparmortest.pm` — reading the wrapper alone tells you almost
nothing, you have to follow the delegation (§2's "Delegated logic?"
question in SKILL.md).

## Disqualification check (§3.1)

Read `lib/apparmortest.pm::test_profile_content_is_special` in full:

- **Multi-machine?** No `mutex_*`/`barrier_*`/`parallel_*` calls anywhere,
  `schedule/security/apparmor.yaml` has no `PARALLEL_WITH` — single
  machine, linear schedule alongside 8 sibling `aa_*` checks.
- **GUI/needle?** Zero `assert_screen`/`check_screen` calls in the helper.
  `apparmortest` extends `consoletest`, whose only `select_console` call is
  in `post_fail_hook` (failure-path log collection) — not part of the
  passing-path logic.
- **Reboot-path needle dependency?** No `power_action`/`wait_boot`/
  `process_reboot` calls anywhere in this module or the helper.
- **Bootstrap?** No — it ends with real assertions (see below), it's not
  setup for a sibling.

Clean single-host candidate. What the helper actually does for
`("aa-disable", "Disabling.*")`:

1. Create an empty local-include file at `/etc/apparmor.d/local/usr.sbin.cupsd`.
2. Create a test profile at `/etc/apparmor.d/usr.sbin.test_profile` whose
   `#include` line sits *after* the closing `}` — reproduces
   [LP#1848227](https://bugs.launchpad.net/apparmor/+bug/1848227).
3. Run `aa-disable /etc/apparmor.d/usr.sbin.test_profile`.
4. Since `cmd eq "aa-disable"`: also check `aa-status | grep test_profile`
   returns non-zero (profile no longer listed).
5. Clean up both files.

**Bug found while reading the helper**: line 722,
`script_run($cmd1, sub { m/$msg/ })` — `script_run` doesn't accept a
regex-match callback as its second argument (that's `validate_script_output`'s
signature). Grepping the whole repo for `script_run(.*sub {` turns up
exactly this one instance — dead code, almost certainly a copy-paste
artifact, not an intentionally working check. The `$msg` parameter
(`"Disabling.*"`) is passed everywhere but never actually verified in the
original. **The conversion below implements the check for real** (asserts
the regex, since that's clearly the intent) rather than reproducing the
bug — call this out if you convert a sibling module and land on the same
helper, and consider a separate fix for the original Perl.

## Language choice (§3.3 step 2)

Plain CLI-driven check, no data structures worth modeling → python+pytest
(bash isn't a valid `language` for `agnosticTestRunner` — see SKILL.md's
hard constraints).

## The conversion

- `data/security/openqa_agnostic/aa_disable/test_aa_disable.py` — pytest
  port of the five steps above, as an `autouse` fixture (setup/teardown) +
  one test function.
- `data/security/openqa_agnostic/aa_disable/runtest` — standard template:
  METADATA block, `source ../lib/helper.sh`, `TEST_FILES=(test_aa_disable.py)`,
  `handle_args`, then `pytest test_aa_disable.py --junitxml=results.xml`.
- `tests/security/oqa_agnostic/aa_disable.pm` — thin wrapper:
  `select_serial_terminal` then `agnosticTestRunner->new({language =>
  'python', name => 'aa_disable'})->setup()->run_test()->parse_results()->cleanup()`.
  No `test_flags` override, matching the original (none of the `aa_*`
  siblings set one either, except `aa_prepare.pm`'s bootstrap `milestone`).

## Validation performed (no SUT available)

```
$ ./runtest -h    # usage text — OK
$ ./runtest -m    # dumps the METADATA block — OK
$ ./runtest -f    # prints "test_aa_disable.py" — OK
$ perl -Ilib -c tests/security/oqa_agnostic/aa_disable.pm
# fails with "Base class package basetest is empty" — IDENTICAL failure on
# the already-merged java_hashing.pm wrapper checked the same way, i.e. a
# pre-existing missing-os-autoinst-engine limitation of this dev environment,
# not a defect in the new file.
$ python3 -m pytest test_aa_disable.py --collect-only -q
# 1 test collected — OK
```

Never run against a real SUT — the actual `aa-disable`/`aa-status`
behavior is unverified. Don't claim this passes without running it for
real.

## What's left (not done, by design — this is an example, not a live change)

- `schedule/security/apparmor.yaml` still points at
  `security/apparmor/aa_disable`, not `security/oqa_agnostic/aa_disable`.
- The original `tests/security/apparmor/aa_disable.pm` still exists and is
  still scheduled — nothing was removed.
- If you want to actually land this conversion: copy the two files under
  `data/`/`tests/` above to their real repo paths, then follow SKILL.md
  §3.3 steps 5-7 (wire scheduling, ask before deleting the original, run it
  against a real SUT).
