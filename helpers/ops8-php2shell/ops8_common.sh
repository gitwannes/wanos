#!/usr/bin/env bash
# --- file: helpers/ops8-php2shell/ops8_common.sh ---
# Shared constants / helpers for Ops8 PHP2Shell bridge (sourced by ops8_php2shell.sh).
# ASCII-only console messages.

OPS8_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS8_PATCH_FILE="${OPS8_SELF_DIR}/php-7.4-CVE-2026-109618-109619.patch"
OPS8_PATCH_COMMIT="712e60f9edfd03f0960fc4fc3c2c375f42b90aa2"
OPS8_CVE_A="CVE-2026-109618"
OPS8_CVE_B="CVE-2026-109619"
OPS8_STATE_DIR="/var/lib/wanos-ops8"
OPS8_MARKER="${OPS8_STATE_DIR}/bridge"
OPS8_APT_BAK_DIR="${OPS8_STATE_DIR}/apt-bak"
OPS8_BIN_BAK_DIR="${OPS8_STATE_DIR}/bin-bak"
OPS8_FPM_INI="/etc/php/7.4/fpm/conf.d/99-ops8-php2shell.ini"
OPS8_BUILD_ROOT="${OPS8_BUILD_ROOT:-/home/wannes/ops8-php-build}"
OPS8_FPM_SERVICE="php7.4-fpm"
OPS8_PHP_CONFIG="${OPS8_PHP_CONFIG:-php-config7.4}"
OPS8_CLI_BIN="/usr/bin/php7.4"
OPS8_FPM_BIN="/usr/sbin/php-fpm7.4"
# Override build jobs: OPS8_BUILD_PARALLEL=1 sudo ./ops8_php2shell.sh all
OPS8_BUILD_PARALLEL="${OPS8_BUILD_PARALLEL:-}"
OPS8_SWAP_TARGET_MB="${OPS8_SWAP_TARGET_MB:-2048}"
OPS8_SWAP_MAX_MB="${OPS8_SWAP_MAX_MB:-4096}"
OPS8_DPHYS_SWAPFILE="/etc/dphys-swapfile"
OPS8_MIN_ROOT_AVAIL_MB="${OPS8_MIN_ROOT_AVAIL_MB:-5120}"
# Set OPS8_RESUME=1 to skip reset/extract/patch and only reconfigure+make+install
# (use when the patched tree is still present, e.g. after CLI-only configure miss).
OPS8_RESUME="${OPS8_RESUME:-0}"
OPS8_FPM_USER="${OPS8_FPM_USER:-www-data}"
OPS8_FPM_GROUP="${OPS8_FPM_GROUP:-www-data}"
# Official php.net 7.4.33 (xz) — use this, not Debian .orig (may differ / .asc confusion)
OPS8_PHP_TARBALL_URL="${OPS8_PHP_TARBALL_URL:-https://www.php.net/distributions/php-7.4.33.tar.xz}"
OPS8_PHP_TARBALL_SHA256="${OPS8_PHP_TARBALL_SHA256:-924846abf93bc613815c55dd3f5809377813ac62a9ec4eb3778675b82a27b927}"
OPS8_PHP_SRC_DIRNAME="php-7.4.33"

ops8_need_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "ERROR: run as root (sudo)." >&2
        exit 1
    fi
}

ops8_mem_total_mb() {
    awk '/^MemTotal:/ { printf "%d", $2/1024; exit }' /proc/meminfo
}

ops8_swap_total_mb() {
    awk 'NR>1 { s+=$3 } END { printf "%d", s/1024 }' /proc/swaps 2>/dev/null || echo 0
}

ops8_pick_parallel() {
    local n mem
    if [ -n "${OPS8_BUILD_PARALLEL}" ]; then
        echo "${OPS8_BUILD_PARALLEL}"
        return 0
    fi
    mem="$(ops8_mem_total_mb)"
    n="$(nproc 2>/dev/null || echo 2)"
    if [ "${mem}" -lt 3000 ]; then
        echo 1
    elif [ "${n}" -gt 2 ]; then
        echo 2
    else
        echo "${n}"
    fi
}

ops8_php_pkg_version() {
    dpkg-query -W -f='${Version}\n' php7.4-fpm 2>/dev/null || true
}

ops8_is_bridged() {
    if [ -f "${OPS8_MARKER}" ] && grep -q '^bridged=1' "${OPS8_MARKER}"; then
        return 0
    fi
    return 1
}

ops8_restart_fpm() {
    if systemctl list-unit-files "${OPS8_FPM_SERVICE}.service" >/dev/null 2>&1; then
        systemctl restart "${OPS8_FPM_SERVICE}"
        systemctl is-active --quiet "${OPS8_FPM_SERVICE}"
        echo "OK: restarted ${OPS8_FPM_SERVICE}"
    else
        echo "ERROR: ${OPS8_FPM_SERVICE}.service not found." >&2
        return 1
    fi
}

ops8_write_marker() {
    local method="$1"
    mkdir -p "${OPS8_STATE_DIR}"
    {
        echo "bridged=1"
        echo "method=${method}"
        echo "commit=${OPS8_PATCH_COMMIT}"
        echo "cve=${OPS8_CVE_A},${OPS8_CVE_B}"
        echo "pkg_version=$(ops8_php_pkg_version)"
        echo "cli_bin=${OPS8_CLI_BIN}"
        echo "fpm_bin=${OPS8_FPM_BIN}"
        echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${OPS8_MARKER}"
    chmod 644 "${OPS8_MARKER}"
    echo "OK: wrote marker ${OPS8_MARKER}"
}
