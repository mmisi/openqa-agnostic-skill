# SUSE's openQA tests
#
# Copyright SUSE LLC
# SPDX-License-Identifier: FSFAP

import re
import subprocess

import pytest

TEST_PROFILE = "/etc/apparmor.d/usr.sbin.test_profile"
LOCAL_PROFILE = "/etc/apparmor.d/local/usr.sbin.cupsd"


def _run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def apparmor_test_profile():
    # Refer to https://bugs.launchpad.net/apparmor/+bug/1848227 : a profile
    # with a local include placed after the closing '}' must still be
    # handled correctly by the aa-* tools.
    _run(f"rm -rf {LOCAL_PROFILE}")
    _run(f"touch {LOCAL_PROFILE}")
    _run(f"echo '/usr/sbin/cupsd {{' > {TEST_PROFILE}")
    _run(f"echo '}}' >> {TEST_PROFILE}")
    _run(f"echo '#include <local/usr.sbin.cupsd>' >> {TEST_PROFILE}")
    yield
    _run(f"rm -rf {TEST_PROFILE}")
    _run(f"rm -rf {LOCAL_PROFILE}")


def test_aa_disable():
    """aa-disable on the test profile must succeed and print a 'Disabling...'
    message, and the profile must then no longer be listed by aa-status."""
    result = _run(f"aa-disable {TEST_PROFILE}")
    assert result.returncode == 0, (
        f"aa-disable failed (rc={result.returncode}): {result.stdout}{result.stderr}"
    )
    assert re.search(r"Disabling.*", result.stdout + result.stderr), (
        f"Expected 'Disabling...' in aa-disable output, got: {result.stdout}{result.stderr}"
    )

    status = _run("aa-status | grep test_profile")
    assert status.returncode != 0, "Profile still listed by aa-status after aa-disable"


if __name__ == "__main__":
    pytest.main([__file__])
