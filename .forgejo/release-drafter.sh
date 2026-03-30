#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG=""
LABELS=""
CURRENT_TAG=""
PR_NUMBER=""
AUTHOR=""
DRY_RUN=true
RUN_TESTS=false
DEPTH=""

VERSION_FILE="app/deezer_engine/__version__.py"
CHANGELOG_FILE="CHANGELOG.md"
RAW_COMMIT_COUNT=0
IGNORED_RELEASE_DRAFT_COUNT=0
IGNORED_EXISTING_CHANGELOG_COUNT=0
FILTERED_COMMIT_MSG=""
TEST_TMP_DIR=""

usage() {
    cat <<'USAGE'
Usage:
  .forgejo/release-drafter.sh [options]

Options:
  -m <messages>              Commit message block (newline-delimited)
  -t <tag>                   Current tag (ex: v0.14.2)
  -a <author>                Author used in changelog lines
  -l <labels>                Labels text (optional)
  -p <pr_ref>                PR number (optional)
  --dry-run                  Preview only, do not modify files (default)
  --dry-run=true|false       Explicit dry-run toggle
  --no-dry-run               Apply changes to version + changelog
    --depth <n>                Use last n commits from HEAD/end-ref for message collection
    --depth=<n>                Same as above
  --test                     Run built-in hard-coded tests
  -h, --help                 Show this help

Notes:
  - If -m is omitted, commit messages are read from git range/history.
  - If -t is omitted, current tag is resolved by git describe.
  - If -a is omitted, author is read from git log.
USAGE
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -m)
                COMMIT_MSG="${2:-}"
                shift 2
                ;;
            -l)
                LABELS="${2:-}"
                shift 2
                ;;
            -t)
                CURRENT_TAG="${2:-}"
                shift 2
                ;;
            -p)
                PR_NUMBER="${2:-}"
                shift 2
                ;;
            -a)
                AUTHOR="${2:-}"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --no-dry-run)
                DRY_RUN=false
                shift
                ;;
            --dry-run=true)
                DRY_RUN=true
                shift
                ;;
            --dry-run=false)
                DRY_RUN=false
                shift
                ;;
            --test)
                RUN_TESTS=true
                shift
                ;;
            --depth)
                DEPTH="${2:-}"
                shift 2
                ;;
            --depth=*)
                DEPTH="${1#*=}"
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                echo "ERROR: Unknown argument '$1'"
                usage
                ;;
        esac
    done
}

version_to_int() {
    echo "$1" | sed 's/v//' | awk -F. '{ printf("%03d%03d%03d\n", $1,$2,$3); }'
}

increment_version() {
    local version="$1"
    local bump="$2"
    local clean_version="${version#v}"
    local major minor patch

    IFS='.' read -r major minor patch <<< "$clean_version"
    case "$bump" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
    esac
    echo "v$major.$minor.$patch"
}

current_version_from_file() {
    grep "__version__ =" "$VERSION_FILE" | cut -d '"' -f 2
}

is_in_changelog() {
    local line="$1"
    [[ -f "$CHANGELOG_FILE" ]] || return 1
    grep -Fq -- "- $line" "$CHANGELOG_FILE"
}

collect_commit_messages_from_git() {
    local range=""
    local end_ref="${TARGET_SHA:-${GITHUB_SHA:-HEAD}}"

    if [[ -n "$DEPTH" ]]; then
        if ! [[ "$DEPTH" =~ ^[0-9]+$ ]] || [[ "$DEPTH" == "0" ]]; then
            echo "ERROR: --depth must be a positive integer" >&2
            exit 1
        fi
        git log --format=%s -n "$DEPTH" "$end_ref"
        return
    fi

    if [[ -n "${GIT_RANGE:-}" ]]; then
        range="$GIT_RANGE"
    elif [[ -n "${BEFORE_SHA:-}" ]] && [[ "$BEFORE_SHA" != "0000000000000000000000000000000000000000" ]]; then
        if git rev-parse -q --verify "$BEFORE_SHA^{commit}" >/dev/null 2>&1 && git rev-parse -q --verify "$end_ref^{commit}" >/dev/null 2>&1; then
            range="$BEFORE_SHA..$end_ref"
        fi
    fi

    if [[ -z "$range" ]] && [[ -n "$CURRENT_TAG" ]]; then
        if git rev-parse -q --verify "$CURRENT_TAG^{commit}" >/dev/null 2>&1; then
            range="$CURRENT_TAG..HEAD"
        fi
    fi

    if [[ -n "$range" ]]; then
        git log --format=%s "$range"
    else
        git log --format=%s -n 20
    fi
}

filter_commit_messages() {
    local input="$1"
    FILTERED_COMMIT_MSG=""

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" ]] && continue
        RAW_COMMIT_COUNT=$((RAW_COMMIT_COUNT + 1))

        if [[ "${line,,}" == *"[release-draft]"* ]]; then
            IGNORED_RELEASE_DRAFT_COUNT=$((IGNORED_RELEASE_DRAFT_COUNT + 1))
            continue
        fi

        if is_in_changelog "$line"; then
            IGNORED_EXISTING_CHANGELOG_COUNT=$((IGNORED_EXISTING_CHANGELOG_COUNT + 1))
            continue
        fi

        if [[ -z "$FILTERED_COMMIT_MSG" ]]; then
            FILTERED_COMMIT_MSG="$line"
        else
            FILTERED_COMMIT_MSG="$FILTERED_COMMIT_MSG"$'\n'"$line"
        fi
    done <<< "$input"
}

build_formatted_lines() {
    local formatted=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" ]] && continue
        local rendered="$line"
        if [[ "$PR_NUMBER" =~ ^[0-9]+$ ]] && [[ "$PR_NUMBER" != "0" ]]; then
            rendered="$rendered #$PR_NUMBER"
        fi
        if [[ -n "$AUTHOR" && "$AUTHOR" != "***" ]]; then
            rendered="$rendered (@$AUTHOR)"
        fi
        if [[ -z "$formatted" ]]; then
            formatted="$rendered"
        else
            formatted="$formatted"$'\n'"$rendered"
        fi
    done <<< "$COMMIT_MSG"
    echo "$formatted"
}

get_priority() {
    local input
    input=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    local prefix=""
    [[ "$input" == *":"* ]] && prefix="${input%%:*}"

    if [[ "$prefix" =~ ^major$ || "$input" =~ major || "$input" =~ breaking || "$input" =~ ! ]]; then
        echo 3
    elif [[ "$prefix" =~ ^(minor|feat) || "$input" =~ feature || "$input" =~ feat || "$input" =~ enhancement || "$input" =~ enhance ]] || \
         [[ -z "$prefix" && "$input" =~ minor ]]; then
        echo 2
    elif [[ "$prefix" =~ ^(patch|fix) || "$input" =~ bug || "$input" =~ patch ]]; then
        echo 1
    elif [[ "$input" =~ skip || "$input" =~ ignore-release ]]; then
        echo -1
    else
        echo 0
    fi
}

calculate_logic() {
    local msg_pri=0
    local msg_has_skip=false

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" ]] && continue
        local line_pri
        line_pri=$(get_priority "$line")
        if (( line_pri > msg_pri )); then
            msg_pri=$line_pri
        fi
        [[ "$line_pri" -eq -1 ]] && msg_has_skip=true
    done <<< "$COMMIT_MSG"

    local lbl_pri
    lbl_pri=$(get_priority "$LABELS")
    local max_pri=$msg_pri
    (( lbl_pri > max_pri )) && max_pri=$lbl_pri

    local has_skip=false
    [[ "$msg_has_skip" == true || "$lbl_pri" -eq -1 ]] && has_skip=true

    local current_major
    current_major=$(echo "${CURRENT_TAG#v}" | cut -d'.' -f1)

    if (( max_pri >= 1 )); then
        case "$max_pri" in
            3)
                if [[ "$current_major" == "0" ]]; then
                    echo "minor|Breaking"
                else
                    echo "major|Breaking"
                fi
                ;;
            2) echo "minor|Enhancements" ;;
            1) echo "patch|Fixes" ;;
        esac
    elif [[ "$has_skip" == true ]]; then
        echo "skip|SKIPPED"
    else
        echo "patch|Maintenance"
    fi
}

apply_release_logic() {
    if [[ -z "$CURRENT_TAG" ]]; then
        CURRENT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    fi

    if [[ -z "$COMMIT_MSG" ]]; then
        COMMIT_MSG=$(collect_commit_messages_from_git)
    fi

    if [[ "$AUTHOR" == "***" || -z "$AUTHOR" || "$AUTHOR" == "null" || "$AUTHOR" == " " ]]; then
        AUTHOR=$(git log -1 --pretty=%an)
    fi

    filter_commit_messages "$COMMIT_MSG"
    COMMIT_MSG="$FILTERED_COMMIT_MSG"

    local commit_title
    commit_title=$(echo "$COMMIT_MSG" | sed '/^$/d' | head -n 1)

    if [[ -z "$commit_title" ]]; then
        echo "------------------------------------------"
        echo "Release logic: SKIPPED"
        echo "Reason      : No eligible commits after filtering"
        echo "Raw commits : $RAW_COMMIT_COUNT"
        echo "Ignored     : [release-draft]=$IGNORED_RELEASE_DRAFT_COUNT, in_changelog=$IGNORED_EXISTING_CHANGELOG_COUNT"
        echo "Dry Run     : $DRY_RUN"
        echo "------------------------------------------"
        return 0
    fi

    local result bump_type category formatted_lines
    result=$(calculate_logic)
    bump_type=$(echo "$result" | cut -d'|' -f1)
    category=$(echo "$result" | cut -d'|' -f2)
    formatted_lines=$(build_formatted_lines)

    if [[ "$bump_type" == "skip" ]]; then
        echo "------------------------------------------"
        echo "Release logic: SKIPPED"
        echo "Dry Run     : $DRY_RUN"
        echo "------------------------------------------"
        return 0
    fi

    local calculated_tag file_tag final_tag update_action
    calculated_tag=$(increment_version "$CURRENT_TAG" "$bump_type")
    file_tag=$(current_version_from_file)

    local calc_int file_int
    calc_int=$(version_to_int "$calculated_tag")
    file_int=$(version_to_int "$file_tag")

    if (( file_int > calc_int )); then
        final_tag="$file_tag"
        update_action="Kept existing higher version $file_tag instead of $calculated_tag"
    elif (( file_int == calc_int )); then
        final_tag="$file_tag"
        update_action="File already up to date ($file_tag)"
    else
        final_tag="$calculated_tag"
        if [[ "$DRY_RUN" == true ]]; then
            update_action="Would update version to $final_tag (dry-run)"
        else
            update_action="Updated version to $final_tag"
            sed -i "s/^__version__ = .*/__version__ = \"$final_tag\"/" "$VERSION_FILE"
        fi
    fi

    echo "------------------------------------------"
    echo "Release Draft Detection:"
    echo "Commit Msg :"
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" ]] && continue
        echo "  - $line"
    done <<< "$COMMIT_MSG"
    echo "Commit Raw : $RAW_COMMIT_COUNT"
    echo "Commit Cnt : $(echo "$COMMIT_MSG" | sed '/^$/d' | wc -l)"
    echo "Ignored    : [release-draft]=$IGNORED_RELEASE_DRAFT_COUNT, in_changelog=$IGNORED_EXISTING_CHANGELOG_COUNT"
    echo "Labels     : ${LABELS:-[None]}"
    echo "Formatted  : $(echo "$formatted_lines" | head -n 1)"
    echo "Category   : $category"
    echo "Version    : $CURRENT_TAG -> $final_tag ($bump_type)"
    echo "Action     : $update_action"
    echo "Dry Run    : $DRY_RUN"
    echo "------------------------------------------"

    if [[ "$DRY_RUN" == false ]]; then
        bash .forgejo/update-changelog.sh "$CURRENT_TAG" "$final_tag" "$category" "$formatted_lines"
    fi
}

assert_eq() {
    local got="$1"
    local expected="$2"
    local message="$3"
    if [[ "$got" != "$expected" ]]; then
        echo "FAIL: $message"
        echo "  expected: $expected"
        echo "  got:      $got"
        exit 1
    fi
}

assert_contains() {
    local file="$1"
    local needle="$2"
    local message="$3"
    if ! grep -Fq -- "$needle" "$file"; then
        echo "FAIL: $message"
        echo "  missing: $needle"
        exit 1
    fi
}

run_hardcoded_tests() {
    local self="$0"
    local test_author="host-test"
    local run_id
    run_id="$(date +%s)"

    print_commit_list() {
        local message_block="$1"
        local idx=1
        echo "Commits:"
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ -z "$line" ]] && continue
            echo "  $idx. $line"
            idx=$((idx + 1))
        done <<< "$message_block"
    }

    print_case_summary() {
        local base_tag="$1"
        local expected_tag="$2"
        local new_tag="$3"
        echo "Version plan: $base_tag -> $expected_tag"
        echo "Version run : $base_tag -> $new_tag"
        echo "Drafter log (key lines):"
        grep -E "^(Release Draft Detection:|Commit Msg|Commit Raw|Commit Cnt|Ignored|Category|Version|Action|Dry Run)" "$TEST_TMP_DIR/last-run.log" || true
    }

    TEST_TMP_DIR="$(mktemp -d)"
    cp "$VERSION_FILE" "$TEST_TMP_DIR/version.bak"
    cp "$CHANGELOG_FILE" "$TEST_TMP_DIR/changelog.bak"

    cleanup_test() {
        if [[ -n "$TEST_TMP_DIR" && -f "$TEST_TMP_DIR/version.bak" && -f "$TEST_TMP_DIR/changelog.bak" ]]; then
            cp "$TEST_TMP_DIR/version.bak" "$VERSION_FILE"
            cp "$TEST_TMP_DIR/changelog.bak" "$CHANGELOG_FILE"
            rm -f header.tmp body.tmp inject.tmp
            rm -rf "$TEST_TMP_DIR"
        fi
    }

    trap cleanup_test EXIT

    reset_state() {
        cp "$TEST_TMP_DIR/version.bak" "$VERSION_FILE"
        cp "$TEST_TMP_DIR/changelog.bak" "$CHANGELOG_FILE"
        rm -f header.tmp body.tmp inject.tmp
    }

    run_apply() {
        local msg="$1"
        local tag="$2"
        BEFORE_SHA="" TARGET_SHA="" GIT_RANGE="" \
            bash "$self" -m "$msg" -t "$tag" -a "$test_author" --no-dry-run > "$TEST_TMP_DIR/last-run.log"
    }

    echo "=== release-drafter hard-coded tests ==="

    echo "Case 1: multiline highest bump picks minor"
    reset_state
    local base_tag expected_tag new_tag msg_fix msg_feat multi_msgs
    base_tag=$(current_version_from_file)
    msg_fix="fix: ci-test-${run_id}-fix"
    msg_feat="feat: ci-test-${run_id}-feat"
    multi_msgs="${msg_fix}"$'\n'"${msg_feat}"
    expected_tag=$(increment_version "$base_tag" minor)

    echo "Base version: $base_tag"
    echo "Expected bump: minor"
    print_commit_list "$multi_msgs"

    run_apply "$multi_msgs" "$base_tag"
    new_tag=$(current_version_from_file)
    print_case_summary "$base_tag" "$expected_tag" "$new_tag"
    assert_eq "$new_tag" "$expected_tag" "multiline commits should pick minor bump"
    assert_contains "$CHANGELOG_FILE" "- ${msg_fix} (@${test_author})" "fix message should be written as bullet"
    assert_contains "$CHANGELOG_FILE" "- ${msg_feat} (@${test_author})" "feat message should be written as bullet"
    echo "PASS: multiline bump + changelog bullets"
    echo

    echo "Case 2: pre-1.0 breaking is capped to minor"
    reset_state
    base_tag=$(current_version_from_file)
    local major_part msg_break
    major_part="${base_tag#v}"
    major_part="${major_part%%.*}"
    msg_break="breaking: ci-test-${run_id}-breaking!"

    echo "Base version: $base_tag"
    echo "Expected bump: minor (for v0.x.x only)"
    print_commit_list "$msg_break"

    if [[ "$major_part" != "0" ]]; then
        echo "SKIP: base version is $base_tag (not v0.x.x)"
    else
        expected_tag=$(increment_version "$base_tag" minor)
        run_apply "$msg_break" "$base_tag"
        new_tag=$(current_version_from_file)
        print_case_summary "$base_tag" "$expected_tag" "$new_tag"
        assert_eq "$new_tag" "$expected_tag" "breaking should not produce major bump for v0.x.x"
        assert_contains "$CHANGELOG_FILE" "- ${msg_break} (@${test_author})" "breaking message should be added"
        echo "PASS: pre-1.0 breaking cap"
    fi
    echo

    echo "Case 3: patch-only block remains patch"
    reset_state
    base_tag=$(current_version_from_file)
    local msg_fix2 msg_patch multi_patch
    msg_fix2="fix: ci-test-${run_id}-patch-a"
    msg_patch="patch: ci-test-${run_id}-patch-b"
    multi_patch="${msg_fix2}"$'\n'"${msg_patch}"
    expected_tag=$(increment_version "$base_tag" patch)

    echo "Base version: $base_tag"
    echo "Expected bump: patch"
    print_commit_list "$multi_patch"

    run_apply "$multi_patch" "$base_tag"
    new_tag=$(current_version_from_file)
    print_case_summary "$base_tag" "$expected_tag" "$new_tag"
    assert_eq "$new_tag" "$expected_tag" "patch-only block should remain patch"
    assert_contains "$CHANGELOG_FILE" "- ${msg_fix2} (@${test_author})" "first patch should be included"
    assert_contains "$CHANGELOG_FILE" "- ${msg_patch} (@${test_author})" "second patch should be included"
    echo "PASS: patch-only multiline bump"
    echo

    echo "All hard-coded tests passed."
}

main() {
    parse_args "$@"

    if [[ "$RUN_TESTS" == true ]]; then
        run_hardcoded_tests
        return 0
    fi

    apply_release_logic
}

main "$@"
