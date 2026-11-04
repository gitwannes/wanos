#!/usr/bin/env bash
# --- file: helpers/ops8-php2shell/ops8_php2shell.sh ---
# Ops8 PHP2Shell bridge (Bullseye php7.4 path B2: pristine orig + official patch).
# Debian quilt cannot take the upstream 7.4 backport on top of debian/patches.
# Usage:
#   sudo ./ops8_php2shell.sh status|mitigate|rebuild|hold|restart|all
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
  reset     Wipe previous build trees under OPS8_BUILD_ROOT (keeps good tarball)
  rebuild   reset + pristine 7.4.33 + official patch + replace CLI/FPM binaries
  hold      apt-mark hold php7.4* (stop apt from overwriting binaries)
  restart   systemctl restart php7.4-fpm
  all       mitigate + rebuild + hold + restart

Env:
  OPS8_BUILD_ROOT         Build tree (default /home/wannes/ops8-php-build)
  OPS8_BUILD_PARALLEL     Force -jN (default: 1 if RAM < 3GiB, else min(2,nproc))
  OPS8_SWAP_TARGET_MB     Grow dphys-swapfile to this MiB if swap too small (default 2048)
  OPS8_MIN_ROOT_AVAIL_MB  Abort rebuild if / avail below this MiB (default 5120)
  OPS8_RESUME=1           Skip reset/extract/patch; reconfigure+make+install only
  OPS8_FPM_USER/GROUP     FPM --with-fpm-user/group (default www-data)
EOF
}

# Clear leftover extract/build debris from failed/prior attempts.
# Keeps php-7.4.33.tar.xz only when SHA256 matches. Does not touch marker/bin-bak.
ops8_reset_build() {
    local tarball have_hash kept=0
    tarball="${OPS8_BUILD_ROOT}/php-7.4.33.tar.xz"

    echo "Reset: clearing previous attempt trees under ${OPS8_BUILD_ROOT}..."
    mkdir -p "${OPS8_BUILD_ROOT}"

    if [ -f "${tarball}" ]; then
        have_hash="$(sha256sum "${tarball}" | awk '{print $1}')"
        if [ "${have_hash}" != "${OPS8_PHP_TARBALL_SHA256}" ]; then
            echo "WARN: removing cached tarball (SHA256 mismatch)."
            rm -f "${tarball}"
        else
            kept=1
        fi
    fi

    # Wipe everything in the build root except a verified tarball.
    if [ -d "${OPS8_BUILD_ROOT}" ]; then
        find "${OPS8_BUILD_ROOT}" -mindepth 1 -maxdepth 1 \
            ! -name 'php-7.4.33.tar.xz' \
            -exec rm -rf {} +
    fi

    mkdir -p "${OPS8_BUILD_ROOT}"
    chown wannes:wannes "${OPS8_BUILD_ROOT}" 2>/dev/null || true

    if [ "${kept}" -eq 1 ] && [ -f "${tarball}" ]; then
        echo "OK: reset complete (kept verified tarball)."
    else
        echo "OK: reset complete (no usable tarball cache)."
    fi
}

ops8_ensure_disk_space() {
    local avail
    avail="$(df -PBM / | awk 'NR==2 { gsub(/M/,"",$4); print $4 }')"
    if [ -z "${avail}" ]; then
        echo "WARN: could not parse df avail for / - continuing." >&2
        return 0
    fi
    echo "Root filesystem avail: ${avail} MiB (minimum ${OPS8_MIN_ROOT_AVAIL_MB} MiB)."
    if [ "${avail}" -lt "${OPS8_MIN_ROOT_AVAIL_MB}" ]; then
        echo "ERROR: not enough free space on / (need >= ${OPS8_MIN_ROOT_AVAIL_MB} MiB)." >&2
        exit 1
    fi
}

# Uncomment deb-src; backups go under /var/lib/wanos-ops8/apt-bak (not sources.list.d).
ops8_ensure_deb_src() {
    local f changed=0 base
    mkdir -p "${OPS8_APT_BAK_DIR}"
    # Remove leftover invalid backups that confuse apt
    rm -f /etc/apt/sources.list.d/*.bak.ops8 /etc/apt/sources.list.bak.ops8 2>/dev/null || true

    if apt-cache showsrc php7.4 >/dev/null 2>&1; then
        echo "OK: deb-src already usable (apt-cache showsrc php7.4)."
        return 0
    fi
    echo "WARN: no usable deb-src for php7.4 - enabling commented deb-src lines..."
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do
        [ -f "${f}" ] || continue
        if grep -qE '^[[:space:]]*#[[:space:]]*deb-src' "${f}"; then
            base="$(basename "${f}")"
            if [ ! -f "${OPS8_APT_BAK_DIR}/${base}" ]; then
                cp -a "${f}" "${OPS8_APT_BAK_DIR}/${base}"
            fi
            sed -i -E 's/^[[:space:]]*#[[:space:]]*(deb-src[[:space:]].*)$/\1/' "${f}"
            changed=1
            echo "OK: uncommented deb-src in ${f}"
        fi
    done
    if [ "${changed}" -eq 0 ]; then
        echo "ERROR: no commented deb-src lines found; add deb-src for bullseye and re-run." >&2
        exit 1
    fi
    apt-get update -y
    if ! apt-cache showsrc php7.4 >/dev/null 2>&1; then
        echo "ERROR: deb-src enabled but apt-cache showsrc php7.4 still fails." >&2
        exit 1
    fi
    echo "OK: deb-src ready for php7.4."
}

ops8_ensure_build_swap() {
    local swap_mb want
    swap_mb="$(ops8_swap_total_mb)"
    want="${OPS8_SWAP_TARGET_MB}"
    echo "Memory: $(ops8_mem_total_mb) MiB RAM, ${swap_mb} MiB swap (target >= ${want} MiB for build)."
    if [ "${swap_mb}" -ge "${want}" ]; then
        echo "OK: swap already sufficient."
        return 0
    fi
    if [ ! -f "${OPS8_DPHYS_SWAPFILE}" ]; then
        echo "WARN: swap is ${swap_mb} MiB and ${OPS8_DPHYS_SWAPFILE} missing - build may OOM." >&2
        return 0
    fi
    mkdir -p "${OPS8_STATE_DIR}"
    if [ ! -f "${OPS8_STATE_DIR}/dphys-swapfile.bak" ]; then
        cp -a "${OPS8_DPHYS_SWAPFILE}" "${OPS8_STATE_DIR}/dphys-swapfile.bak"
    fi
    echo "Growing dphys-swapfile to ${want} MiB (was ${swap_mb} MiB)..."
    if grep -qE '^CONF_SWAPSIZE=' "${OPS8_DPHYS_SWAPFILE}"; then
        sed -i -E "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=${want}/" "${OPS8_DPHYS_SWAPFILE}"
    else
        echo "CONF_SWAPSIZE=${want}" >> "${OPS8_DPHYS_SWAPFILE}"
    fi
    if grep -qE '^#?CONF_MAXSWAP=' "${OPS8_DPHYS_SWAPFILE}"; then
        sed -i -E "s/^#?CONF_MAXSWAP=.*/CONF_MAXSWAP=${OPS8_SWAP_MAX_MB}/" "${OPS8_DPHYS_SWAPFILE}"
    else
        echo "CONF_MAXSWAP=${OPS8_SWAP_MAX_MB}" >> "${OPS8_DPHYS_SWAPFILE}"
    fi
    dphys-swapfile swapoff || true
    dphys-swapfile setup
    dphys-swapfile swapon
    swap_mb="$(ops8_swap_total_mb)"
    echo "OK: swap now ${swap_mb} MiB (backup ${OPS8_STATE_DIR}/dphys-swapfile.bak)."
}

ops8_prepare_unified_patch() {
    local dest="$1"
    awk '
        BEGIN { keep=0 }
        /^diff --git / { keep=1 }
        keep { print }
    ' "${OPS8_PATCH_FILE}" > "${dest}"
    if [ ! -s "${dest}" ]; then
        echo "ERROR: failed to prepare patch from ${OPS8_PATCH_FILE}" >&2
        exit 1
    fi
}

ops8_status_human() {
    echo "=== Ops8 PHP2Shell status ==="
    echo "CLI: $(php -v 2>/dev/null | head -n1 || echo 'php missing')"
    if [ -x "${OPS8_FPM_BIN}" ]; then
        echo "FPM: $("${OPS8_FPM_BIN}" -v 2>/dev/null | head -n1)"
    else
        echo "FPM: ${OPS8_FPM_BIN} missing"
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
; CVE-2026-109619 confirmed path; does not fully cover CVE-2026-109618 alone.
; Must live in FPM conf (not ini_set / not .user.ini). Restart FPM after change.
session.upload_progress.enabled = Off
EOF
    chmod 644 "${OPS8_FPM_INI}"
    echo "OK: wrote ${OPS8_FPM_INI}"
    ops8_restart_fpm
}

# Resolve php-config binary (Debian: php-config7.4 from php7.4-dev).
ops8_resolve_php_config() {
    local c
    for c in "${OPS8_PHP_CONFIG}" php-config7.4 php-config /usr/bin/php-config7.4; do
        if command -v "${c}" >/dev/null 2>&1; then
            OPS8_PHP_CONFIG="$(command -v "${c}")"
            echo "OK: using php-config at ${OPS8_PHP_CONFIG}"
            return 0
        fi
        if [ -x "${c}" ]; then
            OPS8_PHP_CONFIG="${c}"
            echo "OK: using php-config at ${OPS8_PHP_CONFIG}"
            return 0
        fi
    done
    return 1
}

# Run ./configure using php-config --configure-options.
# That string often embeds CFLAGS=-g -O2 (unquoted) and/or ${prefix} leftovers.
# Do not eval it under set -u (expands $prefix -> "unbound variable").
# shlex-split, substitute prefix, keep only --* tokens.
# php-config7.4 is CLI-shaped (--enable-cli, no FPM). Force --enable-fpm so
# both sapi/cli/php and sapi/fpm/php-fpm are produced (Debian matches via env
# PHP_INI_SCAN_DIR for FPM; config-file-path may stay on the CLI paths).
# Also force --with-fpm-systemd: Debian unit is Type=notify; without sd_notify
# the bridged FPM start hangs until systemd TimeoutStartSec.
ops8_configure_from_php_config() {
    local srcdir="$1"
    local raw token
    local -a args=()
    local -a filtered=()
    local has_enable_cli=0 has_enable_fpm=0 has_fpm_user=0 has_fpm_group=0
    local has_fpm_systemd=0

    raw="$("${OPS8_PHP_CONFIG}" --configure-options)"
    echo "configure options from ${OPS8_PHP_CONFIG} (truncated):"
    echo "${raw}" | fold -s -w 100 | head -n 5
    echo "..."

    while IFS= read -r token; do
        [ -n "${token}" ] || continue
        case "${token}" in
            --*)
                args+=("${token}")
                ;;
            CFLAGS=* | CPPFLAGS=* | CXXFLAGS=* | LDFLAGS=* | EXTRA_CFLAGS=* | EXTRA_LDFLAGS=*)
                echo "OK: dropping build-flag token from php-config: ${token%%=*}=..."
                ;;
            *)
                echo "OK: dropping non-configure token from php-config: ${token}"
                ;;
        esac
    done < <(
        printf '%s\n' "${raw}" | python3 -c '
import shlex
import sys

raw = sys.stdin.read()
tokens = shlex.split(raw)
prefix = "/usr"
for t in tokens:
    if t.startswith("--prefix="):
        prefix = t.split("=", 1)[1]
        break
for t in tokens:
    t = t.replace("${prefix}", prefix).replace("$prefix", prefix)
    sys.stdout.write(t + "\n")
'
    )

    if [ "${#args[@]}" -eq 0 ]; then
        echo "ERROR: no --* configure options left after filtering php-config output." >&2
        exit 1
    fi

    for token in "${args[@]}"; do
        case "${token}" in
            --disable-fpm)
                echo "OK: dropping --disable-fpm (need FPM binary for bridge)."
                continue
                ;;
            --enable-cli) has_enable_cli=1 ;;
            --enable-fpm) has_enable_fpm=1 ;;
            --with-fpm-user=*) has_fpm_user=1 ;;
            --with-fpm-group=*) has_fpm_group=1 ;;
            --with-fpm-systemd) has_fpm_systemd=1 ;;
        esac
        filtered+=("${token}")
    done
    args=("${filtered[@]}")

    if [ "${has_enable_cli}" -eq 0 ]; then
        args+=(--enable-cli)
        echo "OK: forcing --enable-cli"
    fi
    if [ "${has_enable_fpm}" -eq 0 ]; then
        args+=(--enable-fpm)
        echo "OK: forcing --enable-fpm (php-config is CLI-only)."
    fi
    if [ "${has_fpm_user}" -eq 0 ]; then
        args+=(--with-fpm-user="${OPS8_FPM_USER}")
        echo "OK: forcing --with-fpm-user=${OPS8_FPM_USER}"
    fi
    if [ "${has_fpm_group}" -eq 0 ]; then
        args+=(--with-fpm-group="${OPS8_FPM_GROUP}")
        echo "OK: forcing --with-fpm-group=${OPS8_FPM_GROUP}"
    fi
    if [ "${has_fpm_systemd}" -eq 0 ]; then
        args+=(--with-fpm-systemd)
        echo "OK: forcing --with-fpm-systemd (Debian Type=notify)."
    fi

    echo "Configuring with ${#args[@]} options (long)..."
    (
        cd "${srcdir}"
        ./configure "${args[@]}"
    )
}

# B2: pristine upstream 7.4.33 + official patch; replace CLI/FPM binaries only.
ops8_rebuild() {
    ops8_need_root
    if [ ! -f "${OPS8_PATCH_FILE}" ]; then
        echo "ERROR: missing patch ${OPS8_PATCH_FILE}" >&2
        exit 1
    fi

    local resume=0
    case "${OPS8_RESUME}" in
        1|yes|YES|true|TRUE) resume=1 ;;
    esac

    export DEBIAN_FRONTEND=noninteractive
    local jobs
    jobs="$(ops8_pick_parallel)"
    echo "Build parallel jobs: ${jobs}"
    echo "Method: B2 pristine orig + official patch (not Debian quilt)."

    local upstream srcdir
    upstream="${OPS8_BUILD_ROOT}/upstream"
    srcdir="${upstream}/${OPS8_PHP_SRC_DIRNAME}"

    if [ "${resume}" -eq 1 ]; then
        echo "OPS8_RESUME=1: skip reset/extract/patch; reconfigure+make+install only."
        if [ ! -f "${srcdir}/configure" ]; then
            echo "ERROR: OPS8_RESUME=1 but missing ${srcdir}/configure - run full rebuild." >&2
            exit 1
        fi
        ops8_ensure_disk_space
        mkdir -p "${OPS8_BUILD_ROOT}"
        cd "${OPS8_BUILD_ROOT}"
        apt-get install -y --no-install-recommends libsystemd-dev >/dev/null || \
            apt-get install -y --no-install-recommends libsystemd-dev
        if ! ops8_resolve_php_config; then
            apt-get install -y --no-install-recommends php7.4-dev
            if ! ops8_resolve_php_config; then
                echo "ERROR: php-config7.4 / php-config still missing." >&2
                exit 1
            fi
        fi
    else
        # First action: wipe prior attempt debris (half-patched trees, .rej, debian leftovers).
        ops8_reset_build

        ops8_ensure_disk_space
        ops8_ensure_deb_src
        ops8_ensure_build_swap

        cd "${OPS8_BUILD_ROOT}"

        echo "Installing build dependencies (including php7.4-dev for php-config)..."
        apt-get update -y
        apt-get install -y --no-install-recommends \
            build-essential patch pkg-config \
            dpkg-dev \
            libsystemd-dev \
            php7.4-dev
        apt-get build-dep -y php7.4

        if ! ops8_resolve_php_config; then
            echo "ERROR: php-config7.4 / php-config still missing after php7.4-dev install." >&2
            exit 1
        fi

        # apt-get source is NOT used for the tree anymore (Debian .orig + quilt mismatch /
        # .asc confusion). We still need build-dep libs from the packages above.
        # Fetch pristine php.net 7.4.33 and verify SHA256.
        echo "Fetching pristine ${OPS8_PHP_SRC_DIRNAME} from php.net..."
        local tarball="${OPS8_BUILD_ROOT}/php-7.4.33.tar.xz"
        if [ -f "${tarball}" ]; then
            local have_hash
            have_hash="$(sha256sum "${tarball}" | awk '{print $1}')"
            if [ "${have_hash}" != "${OPS8_PHP_TARBALL_SHA256}" ]; then
                echo "WARN: removing tarball with wrong SHA256 (${have_hash})"
                rm -f "${tarball}"
            else
                echo "OK: reusing cached tarball (SHA256 match)."
            fi
        fi
        if [ ! -f "${tarball}" ]; then
            apt-get install -y --no-install-recommends curl ca-certificates
            if ! curl -fsSL -o "${tarball}" "${OPS8_PHP_TARBALL_URL}"; then
                echo "ERROR: download failed: ${OPS8_PHP_TARBALL_URL}" >&2
                exit 1
            fi
        fi
        local got_hash
        got_hash="$(sha256sum "${tarball}" | awk '{print $1}')"
        if [ "${got_hash}" != "${OPS8_PHP_TARBALL_SHA256}" ]; then
            echo "ERROR: SHA256 mismatch for php-7.4.33.tar.xz" >&2
            echo "  expected ${OPS8_PHP_TARBALL_SHA256}" >&2
            echo "  got      ${got_hash}" >&2
            exit 1
        fi
        echo "OK: tarball ${tarball} ($(wc -c < "${tarball}") bytes, SHA256 OK)"

        rm -rf "${upstream}"
        mkdir -p "${upstream}"
        if ! tar -xJf "${tarball}" -C "${upstream}"; then
            echo "ERROR: tar extract failed for ${tarball}" >&2
            exit 1
        fi

        if [ ! -f "${srcdir}/configure" ]; then
            echo "ERROR: missing ${srcdir}/configure after extract." >&2
            find "${upstream}" -maxdepth 2 -print || true
            exit 1
        fi
        echo "Pristine source: ${srcdir}"

        local patch_clean="${OPS8_BUILD_ROOT}/ops8-php2shell.unified.patch"
        ops8_prepare_unified_patch "${patch_clean}"
        echo "Dry-run official PHP2Shell backport (${OPS8_PATCH_COMMIT})..."
        if ! (
            cd "${srcdir}"
            patch -p1 --dry-run --forward --batch < "${patch_clean}"
        ); then
            echo "ERROR: patch dry-run failed on pristine php.net tree - aborting." >&2
            exit 1
        fi
        echo "Applying official PHP2Shell backport..."
        (
            cd "${srcdir}"
            patch -p1 --forward --batch --no-backup-if-mismatch < "${patch_clean}"
        )
    fi

    ops8_configure_from_php_config "${srcdir}"

    echo "Compiling (long on Pi; parallel=${jobs})..."
    (
        cd "${srcdir}"
        make -j"${jobs}"
    )

    local built_cli built_fpm
    built_cli="${srcdir}/sapi/cli/php"
    built_fpm="${srcdir}/sapi/fpm/php-fpm"
    if [ ! -x "${built_cli}" ] || [ ! -x "${built_fpm}" ]; then
        echo "ERROR: build did not produce sapi/cli/php and sapi/fpm/php-fpm" >&2
        echo "  cli: ${built_cli}  exists=$( [ -e "${built_cli}" ] && echo yes || echo no )" >&2
        echo "  fpm: ${built_fpm}  exists=$( [ -e "${built_fpm}" ] && echo yes || echo no )" >&2
        exit 1
    fi

    mkdir -p "${OPS8_BIN_BAK_DIR}"
    if [ -x "${OPS8_CLI_BIN}" ] && [ ! -f "${OPS8_BIN_BAK_DIR}/php7.4" ]; then
        cp -a "${OPS8_CLI_BIN}" "${OPS8_BIN_BAK_DIR}/php7.4"
    fi
    if [ -x "${OPS8_FPM_BIN}" ] && [ ! -f "${OPS8_BIN_BAK_DIR}/php-fpm7.4" ]; then
        cp -a "${OPS8_FPM_BIN}" "${OPS8_BIN_BAK_DIR}/php-fpm7.4"
    fi

    echo "Installing bridged binaries over ${OPS8_CLI_BIN} and ${OPS8_FPM_BIN}..."
    install -m 755 "${built_cli}" "${OPS8_CLI_BIN}"
    install -m 755 "${built_fpm}" "${OPS8_FPM_BIN}"

    # Quick smoke: binaries run
    "${OPS8_CLI_BIN}" -v | head -n1
    "${OPS8_FPM_BIN}" -v | head -n1

    ops8_write_marker "pristine-orig"
    echo "OK: B2 rebuild complete. Stock dpkg version unchanged; binaries replaced + marker set."
    echo "    Originals (if first run): ${OPS8_BIN_BAK_DIR}/"
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
    ops8_hold
    ops8_restart_fpm
    ops8_status_human
    echo "DONE: Ops8 bridge applied (temporary until Ops7)."
}

cmd="${1:-}"
case "${cmd}" in
    status) ops8_status_human ;;
    mitigate) ops8_mitigate ;;
    reset) ops8_need_root; ops8_reset_build ;;
    rebuild) ops8_rebuild ;;
    hold) ops8_hold ;;
    restart) ops8_need_root; ops8_restart_fpm ;;
    all) ops8_all ;;
    install)
        echo "ERROR: 'install' removed. B2 rebuild replaces binaries itself. Use: rebuild | all" >&2
        exit 1
        ;;
    -h|--help|help|"") ops8_usage; exit 0 ;;
    *) echo "ERROR: unknown command: ${cmd}" >&2; ops8_usage; exit 1 ;;
esac
