#!/usr/bin/env bash
# --- file: helpers/ops8-php2shell/ops8_common.sh ---
# Shared constants / helpers for Ops8 PHP2Shell bridge (sourced by ops8_php2shell.sh).
# ASCII-only console messages.

OPS8_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS8_PATCH_FILE="${OPS8_SELF_DIR}/php-7.4-CVE-2026-109618-109619.patch"
OPS8_PATCH_COMMIT="712e60f9edfd03f0960fc4fc3c2c375f42b90aa2"
OPS8_CVE_A="CVE-2026-109618"
OPS8_CVE_B="CVE-2026-109619"
OPS8_LOCAL_SUFFIX="+wanosops8.1"
OPS8_STATE_DIR="/var/lib/wanos-ops8"
OPS8_MARKER="${OPS8_STATE_DIR}/bridge"
OPS8_FPM_INI="/etc/php/7.4/fpm/conf.d/99-ops8-php2shell.ini"
OPS8_BUILD_ROOT="${OPS8_BUILD_ROOT:-/home/wannes/ops8-php-build}"
OPS8_FPM_SERVICE="php7.4-fpm"

ops8_need_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "ERROR: run as root (sudo)." >&2
        exit 1
    fi
}

ops8_php_pkg_version() {
    dpkg-query -W -f='${Version}\n' php7.4-fpm 2>/dev/null || true
}

ops8_is_bridged_version() {
    local ver
    ver="$(ops8_php_pkg_version)"
    case "${ver}" in
        *wanosops8*) return 0 ;;
        *) return 1 ;;
    esac
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
