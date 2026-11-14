#!/usr/bin/env bash
# --- file: helpers/wlw-sync.sh ---
# ==============================================================================
# WLW deploy mirror (on the Pi) - lives in the WanOS tree (P2)
#
# Copies the be90 git clone onto the live tree. Excludes come from the same
# helpers/wanos-sync.config.txt used by wanos-sync.ps1 (main / lcd / wlw).
# Compare by checksum, not modification time (a checkout stamps new times).
#   rsync -a --checksum --no-times --delete
# Default output: copy / delete / unchanged counts. No path list.
# -v lists copy, delete, and unchanged paths under separate headings.
# No SSH, no log pull, no SQLite pull, no bootstrap.
#
# Modes:
#   test   Dry run (rsync -n). Counts only. Writes nothing.
#   run    Mirror clone --> live.
#   info   Show the clone, and the git commands to pull or check out a branch.
#          Does not fetch, pull, or check out.
#
# After main WanOS sync has deployed helpers + config:
#   bash ~/wanos/helpers/wlw-sync.sh test
#   bash ~/wanos/helpers/wlw-sync.sh test -v
#   bash ~/wanos/helpers/wlw-sync.sh run
#   bash ~/wanos/helpers/wlw-sync.sh run -v
#   bash ~/wanos/helpers/wlw-sync.sh info
#
# Excluded paths are not copied and are not deleted on the live tree.
# helpers/bootstrap/ is included (no bare "bootstrap" exclude).
# ==============================================================================

set -euo pipefail

# Locked paths (docs/wlw-sync.md RemoteRoot + the Pi clone).
SOURCE="/home/wannes/git/be90webserver"
DEST="/home/wannes/be90webserver"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/wanos-sync.config.txt"

EXCLUDE_DIRS=()
EXCLUDE_FILES=()

usage() {
    echo "Usage: bash $0 test|run|info [-v]" >&2
    echo "  test   Dry-run mirror (rsync -n). Counts copies, deletes, unchanged." >&2
    echo "  run    Mirror ${SOURCE}/ --> ${DEST}/" >&2
    echo "  info   Clone state, and git commands to pull or check out a branch." >&2
    echo "  -v     With test or run: list copy, delete, and unchanged paths." >&2
    echo "  Config: ${CONFIG_FILE}" >&2
}

# Load [MirrorExcludeDirs] / [MirrorExcludeFiles] from wanos-sync.config.txt (SSoT).
load_excludes_from_config() {
    local section="" line
    EXCLUDE_DIRS=()
    EXCLUDE_FILES=()
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Config not found: $CONFIG_FILE" >&2
        echo "Deploy WanOS helpers first (wanos-sync run) so config lands on the Pi." >&2
        exit 1
    fi
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ''|\#*) continue ;;
            \[MirrorExcludeDirs\])
                section="dirs"
                continue
                ;;
            \[MirrorExcludeFiles\])
                section="files"
                continue
                ;;
            \[*\])
                section=""
                continue
                ;;
        esac
        case "$section" in
            dirs) EXCLUDE_DIRS+=("$line") ;;
            files) EXCLUDE_FILES+=("$line") ;;
        esac
    done <"$CONFIG_FILE"
    if [ "${#EXCLUDE_DIRS[@]}" -eq 0 ] && [ "${#EXCLUDE_FILES[@]}" -eq 0 ]; then
        echo "No MirrorExclude dirs/files loaded from $CONFIG_FILE" >&2
        exit 1
    fi
}

# Refuse a mirror that could delete the clone or copy a tree onto itself.
assert_distinct_trees() {
    local src="$1"
    local dst="$2"
    if [ "$src" = "$dst" ]; then
        echo "Refusing: source and dest are the same path ($src)." >&2
        exit 1
    fi
    case "$dst/" in
        "$src/"*)
            echo "Refusing: dest is inside source ($dst)." >&2
            exit 1
            ;;
    esac
    case "$src/" in
        "$dst/"*)
            echo "Refusing: source is inside dest ($src)." >&2
            exit 1
            ;;
    esac
}

require_source() {
    if [ ! -d "$SOURCE" ]; then
        echo "Clone not found: $SOURCE" >&2
        exit 1
    fi
    if [ ! -d "$SOURCE/.git" ]; then
        echo "Not a git clone: $SOURCE" >&2
        exit 1
    fi
}

require_dest() {
    if [ ! -d "$DEST" ]; then
        echo "Live tree not found: $DEST" >&2
        exit 1
    fi
}

require_rsync() {
    if ! command -v rsync >/dev/null 2>&1; then
        echo "rsync is not installed." >&2
        exit 1
    fi
}

# Same --exclude shape as wanos-sync ConvertTo-RsyncExcludeArgs.
rsync_excludes() {
    local d f
    for d in "${EXCLUDE_DIRS[@]}"; do
        case "$d" in
            *[\*\?\[]*) printf '%s\0' "--exclude=${d}" ;;
            *) printf '%s\0' "--exclude=${d}/" ;;
        esac
    done
    for f in "${EXCLUDE_FILES[@]}"; do
        printf '%s\0' "--exclude=${f}"
    done
}

# "1 file" or "N files".
files_word() {
    if [ "$1" = "1" ]; then
        echo "1 file"
    else
        echo "$1 files"
    fi
}

# True when a relative path matches mirror excludes (same rules as rsync / PS).
path_is_excluded() {
    local rel="$1"
    local base segment d f
    local -a parts
    base="${rel##*/}"
    for f in "${EXCLUDE_FILES[@]}"; do
        # shellcheck disable=SC2254
        case "$base" in
            $f) return 0 ;;
        esac
    done
    IFS='/' read -r -a parts <<< "$rel"
    for segment in "${parts[@]}"; do
        [ -z "$segment" ] && continue
        for d in "${EXCLUDE_DIRS[@]}"; do
            # shellcheck disable=SC2254
            case "$segment" in
                $d) return 0 ;;
            esac
        done
    done
    return 1
}

# Sorted relative paths of regular files under src after excludes.
list_source_files() {
    local src="$1"
    local out="$2"
    local f rel
    : >"$out"
    while IFS= read -r -d '' f; do
        rel="${f#"$src"/}"
        if path_is_excluded "$rel"; then
            continue
        fi
        printf '%s\n' "$rel"
    done < <(find "$src" -type f -print0) | LC_ALL=C sort -u >"$out"
}

# Itemize + --stats from rsync. Count content copies, deletes, unchanged.
# With verbose=1, list copy / delete / unchanged under separate headings.
print_mirror_summary() {
    local dry="$1"
    local itemize="$2"
    local verbose="$3"
    local source_list="$4"
    local copies deletes source_regs unchanged
    local copy_list delete_list unchanged_list
    copies=$(grep -cE '^[<>]f' "$itemize" || true)
    deletes=$(grep -cE '^\*deleting' "$itemize" || true)
    copies=${copies:-0}
    deletes=${deletes:-0}
    # Source regular files after excludes (rsync --stats).
    source_regs=$(sed -n 's/^Number of files: .* (reg: \([0-9][0-9]*\).*/\1/p' "$itemize" | head -n 1)
    source_regs=${source_regs:-0}
    unchanged=$((source_regs - copies))
    if [ "$unchanged" -lt 0 ]; then
        unchanged=0
    fi

    if [ "$verbose" = "1" ]; then
        copy_list=$(mktemp)
        delete_list=$(mktemp)
        unchanged_list=$(mktemp)
        sed -n 's/^[<>]f[^ ]* //p' "$itemize" | LC_ALL=C sort -u >"$copy_list"
        sed -n 's/^\*deleting  *//p' "$itemize" | LC_ALL=C sort -u >"$delete_list"
        # Unchanged = source files not in the copy list.
        if [ -s "$source_list" ]; then
            LC_ALL=C sort -u -o "$source_list" "$source_list"
            LC_ALL=C sort -u -o "$copy_list" "$copy_list"
            LC_ALL=C comm -23 "$source_list" "$copy_list" >"$unchanged_list"
        else
            : >"$unchanged_list"
        fi

        echo "--- copy ---"
        if [ -s "$copy_list" ]; then
            cat "$copy_list"
        else
            echo "(none)"
        fi
        echo "--- delete ---"
        if [ -s "$delete_list" ]; then
            cat "$delete_list"
        else
            echo "(none)"
        fi
        echo "--- unchanged ---"
        if [ -s "$unchanged_list" ]; then
            cat "$unchanged_list"
        else
            echo "(none)"
        fi
        echo ""
        rm -f "$copy_list" "$delete_list" "$unchanged_list"
    fi

    if [ "$copies" = "0" ] && [ "$deletes" = "0" ]; then
        echo "Nothing to copy or delete. Unchanged $(files_word "$unchanged")."
        return
    fi
    if [ "$dry" = "1" ]; then
        echo "Would copy $(files_word "$copies"). Would delete $(files_word "$deletes"). Unchanged $(files_word "$unchanged")."
    else
        echo "Copied $(files_word "$copies"). Deleted $(files_word "$deletes"). Unchanged $(files_word "$unchanged")."
    fi
}

mirror() {
    local dry="$1"
    local verbose="$2"
    local src dst
    load_excludes_from_config
    require_rsync
    require_source
    require_dest
    src="$(realpath -e "$SOURCE")"
    dst="$(realpath -e "$DEST")"
    assert_distinct_trees "$src" "$dst"

    local -a args excludes
    # --checksum: size+mtime is not a change. --no-times: do not stamp the
    # live tree just because the clone was checked out later.
    # --stats: source regular-file count for the unchanged total.
    args=(-a --checksum --no-times --delete -i --stats)
    if [ "$dry" = "1" ]; then
        args+=(-n)
        echo "=== MIRROR DRY RUN (clone --> live) ==="
    else
        echo "=== MIRROR (clone --> live) ==="
    fi
    echo "Source: ${src}/"
    echo "Dest:   ${dst}/"
    echo "Config: ${CONFIG_FILE}"
    echo ""

    excludes=()
    while IFS= read -r -d '' ex; do
        excludes+=("$ex")
    done < <(rsync_excludes)

    local itemize source_list
    itemize=$(mktemp)
    source_list=$(mktemp)
    if [ "$verbose" = "1" ]; then
        list_source_files "$src" "$source_list"
    else
        : >"$source_list"
    fi
    if ! rsync "${args[@]}" "${excludes[@]}" "${src}/" "${dst}/" >"$itemize"; then
        rm -f "$itemize" "$source_list"
        exit 1
    fi
    print_mirror_summary "$dry" "$itemize" "$verbose" "$source_list"
    rm -f "$itemize" "$source_list"
}

show_info() {
    load_excludes_from_config
    require_source
    local src
    src="$(realpath -e "$SOURCE")"

    echo "=== WLW sync info ==="
    echo "Tool:               ${SCRIPT_DIR}/wlw-sync.sh"
    echo "Config:             ${CONFIG_FILE}"
    echo "Source (git clone): ${src}/"
    echo "Dest (live tree):   ${DEST}/"
    if [ -d "$DEST" ]; then
        echo "Live tree:          present"
    else
        echo "Live tree:          missing"
    fi
    echo ""
    echo "--- clone ---"
    git -C "$src" status -sb
    echo ""
    git -C "$src" log -1 --decorate --oneline
    echo ""
    git -C "$src" branch -vv
    echo ""
    echo "The mirror copies this working tree as it sits, including uncommitted"
    echo "files. test and run compare contents (not timestamps). Default output"
    echo "is counts (copy / delete / unchanged); -v lists those paths under"
    echo "separate headings. They do not fetch, pull, or check out."
    echo ""
    echo "--- update the current branch from GitHub ---"
    echo "git -C ${src} pull"
    echo ""
    echo "--- list branches ---"
    echo "git -C ${src} fetch"
    echo "git -C ${src} branch -vv"
    echo "git -C ${src} branch -a"
    echo ""
    echo "--- check out another branch, then mirror ---"
    echo "git -C ${src} checkout <branch>"
    echo "bash ${SCRIPT_DIR}/wlw-sync.sh test"
    echo "bash ${SCRIPT_DIR}/wlw-sync.sh test -v"
    echo "bash ${SCRIPT_DIR}/wlw-sync.sh run"
    echo ""
    echo "--- excludes (from wanos-sync.config.txt; not copied, not deleted) ---"
    echo "dirs:  ${EXCLUDE_DIRS[*]}"
    echo "files: ${EXCLUDE_FILES[*]}"
    echo "helpers/bootstrap/ is included (no bare bootstrap exclude)."
    echo ""
    echo "Not this tool: log pull, SQLite pull, bootstrap, PHP-FPM reload."
}

if [ "$(id -u)" -eq 0 ]; then
    echo "Run as wannes, not root." >&2
    exit 1
fi

mode=""
verbose=0
for arg in "$@"; do
    case "$arg" in
        -v|--verbose)
            verbose=1
            ;;
        test|run|info)
            if [ -n "$mode" ]; then
                usage
                exit 2
            fi
            mode=$arg
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

if [ -z "$mode" ]; then
    usage
    exit 2
fi

case "$mode" in
    test) mirror 1 "$verbose" ;;
    run)  mirror 0 "$verbose" ;;
    info) show_info ;;
esac
