#!/bin/sh
# --- file: helpers/wanos-syslog-truncate.sh ---
# rsyslog $outchannel runs this when /var/log/syslog exceeds 20 MiB.
# Truncate in place. omfile uses append, so the next write starts at offset 0.
# Do not rotate/compress — WanOS does not keep rsyslog archives.
set -eu

if [ -f /var/log/syslog ]; then
    /usr/bin/truncate -s 0 /var/log/syslog
fi
