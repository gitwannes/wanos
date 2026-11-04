#!/usr/bin/env bash
# --- file: helpers/ops8-php2shell/ops8_php2shell.sh ---
# Ops8 PHP2Shell bridge orchestrator (Bullseye php7.4 path B).
# Usage:
#   sudo ./ops8_php2shell.sh status|mitigate|rebuild|install|hold|restart|all
# ASCII-only console output.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ops8_common.sh
source "${SELF_DIR}/ops8_common.sh"

ops8_usage() {
    cat <<'EOF'
Usage: sudo ./ops8_php2shell.sh <command>

  status    Print inventory (also: python3 ops8_status.py)
  mitigate  Write FPM conf.d mitigation + restart FPM
  rebuild   apt source + official patch + dpkg-buildpackage (long)
  install   dpkg -i built debs from OPS8_BUILD_ROOT
  hold      apt-mark hold php7.4*
  restart   systemctl restart php7.4-fpm
  all       mitigate + rebuild + install + hold + restart

Env:
  OPS8_BUILD_ROOT  Build tree (default /home/wannes/ops8-php-build)
EOF
}

ops8_status_human() {
    echo "=== Ops8 PHP2Shell status ==="
    echo "CLI: $(php -v 2>/dev/null | head -n1 || echo 'php missing')"
    if command -v php-fpm7.4 >/dev/null 2>&1; then
        echo "FPM: $(php-fpm7.4 -v 2>/dev/null | head -n1)"
    else
        echo "FPM: php-fpm7.4 missing"
    fi
    echo "pkg php7.4-fpm: $(ops8_php_pkg_version)"
    if [ -f "${OPS8_FPM_INI}" ]; then
        echo "mitigation file: present (${OPS8_FPM_INI})"
    else
        echo "mitigation file: absent"
    fi
    if [ -f "${OPS8_MARKER}" ]; then
        echo "bridge marker: present"
        cat "${OPS8_MARKER}"
    else
        echo "bridge marker: absent"
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 "${SELF_DIR}/ops8_status.py" || true
    fi
}

ops8_mitigate() {
    ops8_need_root
    mkdir -p "$(dirname "${OPS8_FPM_INI}")"
    cat > "${OPS8_FPM_INI}" <<'EOF'
; --- Ops8 PHP2Shell mitigation (wanos) ---
; CVE-2026-109619 confirmed path; does not fully cover CVE-2026-109618.
; Must live in FPM conf (not ini_set / not .user.ini). Restart FPM after change.
session.upload_progress.enabled = Off
EOF
    chmod 644 "${OPS8_FPM_INI}"
    echo "OK: wrote ${OPS8_FPM_INI}"
    ops8_restart_fpm
}

ops8_prepare_quilt_patch() {
    local dest="$1"
    # Strip git mailbox headers; keep unified diffs for quilt -p1.
    awk '
        BEGIN { keep=0 }
        /^diff --git / { keep=1 }
        keep { print }
    ' "${OPS8_PATCH_FILE}" > "${dest}"
    if [ ! -s "${dest}" ]; then
        echo "ERROR: failed to prepare quilt patch from ${OPS8_PATCH_FILE}" >&2
        exit 1
    fi
}

ops8_rebuild() {
    ops8_need_root
    if [ ! -f "${OPS8_PATCH_FILE}" ]; then
        echo "ERROR: missing patch ${OPS8_PATCH_FILE}" >&2
        exit 1
    fi

    export DEBIAN_FRONTEND=noninteractive
    mkdir -p "${OPS8_BUILD_ROOT}"
    chown wannes:wannes "${OPS8_BUILD_ROOT}" 2>/dev/null || true
    cd "${OPS8_BUILD_ROOT}"

    echo "Installing build dependencies (php7.4)..."
    apt-get update -y
    apt-get install -y --no-install-recommends \
        build-essential fakeroot debhelper devscripts quilt patch \
        dpkg-dev
    apt-get build-dep -y php7.4

    echo "Fetching php7.4 source into ${OPS8_BUILD_ROOT}..."
    # Drop stale trees from failed runs
    rm -rf php7.4-* 2>/dev/null || true
    apt-get source php7.4

    local srcdir
    srcdir="$(find "${OPS8_BUILD_ROOT}" -maxdepth 1 -type d -name 'php7.4-*' | head -n1)"
    if [ -z "${srcdir}" ] || [ ! -d "${srcdir}/debian" ]; then
        echo "ERROR: php7.4 source tree not found under ${OPS8_BUILD_ROOT}" >&2
        exit 1
    fi
    echo "Source tree: ${srcdir}"

    local quilt_patch="${srcdir}/debian/patches/wanos-ops8-php2shell-bailout.patch"
    ops8_prepare_quilt_patch "${quilt_patch}"
    if ! grep -qxF 'wanos-ops8-php2shell-bailout.patch' "${srcdir}/debian/patches/series"; then
        echo 'wanos-ops8-php2shell-bailout.patch' >> "${srcdir}/debian/patches/series"
    fi

    # Bump local revision so dpkg can distinguish bridged packages.
    local old_ver new_ver
    old_ver="$(dpkg-parsechangelog -l "${srcdir}/debian/changelog" -S Version)"
    case "${old_ver}" in
        *wanosops8*) new_ver="${old_ver}" ;;
        *) new_ver="${old_ver}${OPS8_LOCAL_SUFFIX}" ;;
    esac
    if [ "${new_ver}" != "${old_ver}" ]; then
        (
            cd "${srcdir}"
            DEBFULLNAME="WanOS Ops8" DEBEMAIL="ops8@wanos.local" \
                dch -v "${new_ver}" -D unstable --force-distribution \
                "Ops8 PHP2Shell bridge: apply official 7.4 backport ${OPS8_PATCH_COMMIT} (${OPS8_CVE_A} / ${OPS8_CVE_B})."
        )
    fi
    echo "Package version for build: ${new_ver}"

    echo "Verifying Ops8 patch applies (quilt), then pop so dpkg-buildpackage applies cleanly..."
    (
        cd "${srcdir}"
        export QUILT_PATCHES=debian/patches
        quilt push -a
        quilt pop -a
    )

    echo "Building packages (this takes a long time on Pi)..."
    (
        cd "${srcdir}"
        # -us -uc: no signing; parallel via DEB_BUILD_OPTIONS
        DEB_BUILD_OPTIONS="parallel=$(nproc 2>/dev/null || echo 2)" \
            dpkg-buildpackage -b -us -uc
    )

    mkdir -p "${OPS8_BUILD_ROOT}/debs"
    find "${OPS8_BUILD_ROOT}" -maxdepth 1 -type f -name 'php7.4_*.deb' -exec cp -a {} "${OPS8_BUILD_ROOT}/debs/" \;
    find "${OPS8_BUILD_ROOT}" -maxdepth 1 -type f -name 'php7.4-*.deb' -exec cp -a {} "${OPS8_BUILD_ROOT}/debs/" \;
    echo "OK: built debs listed in ${OPS8_BUILD_ROOT}/debs"
    ls -la "${OPS8_BUILD_ROOT}/debs"
}

ops8_backup_installed_debs() {
    local bak="${OPS8_BUILD_ROOT}/debs-backup"
    mkdir -p "${bak}"
    echo "Saving currently installed php7.4 package list to ${bak}/installed.txt"
    dpkg-query -W -f='${Package}\t${Version}\n' 'php7.4*' > "${bak}/installed.txt" || true
}

ops8_install_debs() {
    ops8_need_root
    local debdir="${OPS8_BUILD_ROOT}/debs"
    if [ ! -d "${debdir}" ] || [ -z "$(ls -A "${debdir}"/*.deb 2>/dev/null || true)" ]; then
        echo "ERROR: no debs in ${debdir} - run rebuild first." >&2
        exit 1
    fi
    ops8_backup_installed_debs
    # Install only packages we already have installed (avoid pulling unused SAPIs).
    local to_install=()
    local deb base pkg
    for deb in "${debdir}"/*.deb; do
        base="$(basename "${deb}")"
        pkg="$(dpkg-deb -f "${deb}" Package)"
        if dpkg-query -W -f='${Status}' "${pkg}" 2>/dev/null | grep -q 'install ok installed'; then
            to_install+=("${deb}")
            echo "Will install: ${pkg} (${base})"
        else
            echo "Skip (not installed): ${pkg}"
        fi
    done
    if [ "${#to_install[@]}" -eq 0 ]; then
        echo "ERROR: no matching installed packages to upgrade from built debs." >&2
        exit 1
    fi
    dpkg -i "${to_install[@]}"
    apt-get install -f -y
    mkdir -p "${OPS8_STATE_DIR}"
    {
        echo "bridged=1"
        echo "commit=${OPS8_PATCH_COMMIT}"
        echo "cve=${OPS8_CVE_A},${OPS8_CVE_B}"
        echo "pkg_version=$(ops8_php_pkg_version)"
        echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${OPS8_MARKER}"
    chmod 644 "${OPS8_MARKER}"
    echo "OK: installed bridged packages; marker ${OPS8_MARKER}"
}

ops8_hold() {
    ops8_need_root
    local pkgs
    pkgs="$(dpkg-query -W -f='${Package}\n' 'php7.4*' 2>/dev/null || true)"
    if [ -z "${pkgs}" ]; then
        echo "ERROR: no php7.4* packages installed." >&2
        exit 1
    fi
    # shellcheck disable=SC2086
    apt-mark hold ${pkgs}
    echo "OK: held:"
    apt-mark showhold | grep '^php7\.4' || true
}

ops8_all() {
    ops8_mitigate
    ops8_rebuild
    ops8_install_debs
    ops8_hold
    ops8_restart_fpm
    ops8_status_human
    echo "DONE: Ops8 bridge applied (temporary until Ops7)."
}

cmd="${1:-}"
case "${cmd}" in
    status) ops8_status_human ;;
    mitigate) ops8_mitigate ;;
    rebuild) ops8_rebuild ;;
    install) ops8_install_debs ;;
    hold) ops8_hold ;;
    restart) ops8_need_root; ops8_restart_fpm ;;
    all) ops8_all ;;
    -h|--help|help|"") ops8_usage; exit 0 ;;
    *) echo "ERROR: unknown command: ${cmd}" >&2; ops8_usage; exit 1 ;;
esac
