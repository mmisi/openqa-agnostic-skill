# SUSE's openQA tests
#
# Copyright SUSE LLC
# SPDX-License-Identifier: FSFAP
#
# Summary: Run 'apparmor aa-disable' test
# Maintainer: QE Security <none@suse.de>

use Mojo::Base 'opensusebasetest';
use testapi;
use serial_terminal 'select_serial_terminal';
use security::agnosticTestRunner;

sub run {
    select_serial_terminal;
    my $test = security::agnosticTestRunner->new({
            language => 'python',
            name => 'aa_disable',
        }
    );

    $test->setup()->run_test()->parse_results()->cleanup();
}

1;
