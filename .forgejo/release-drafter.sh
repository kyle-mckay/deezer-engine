#!/usr/bin/env bash

COMMIT_MSG=""
LABELS=""
CURRENT_TAG=""
PR_NUMBER=""
AUTHOR=""
VERSION_FILE="__version__.py"



usage() {
    echo "Usage: $0 -m '<message>' -t '<tag>' -p '<pr_ref>' -a '<author>' [-l '<labels>']"
    exit 1
}

# parse arguments
while getopts "m:l:t:p:a:" opt; do
  case $opt in
    m) COMMIT_MSG="$OPTARG" ;;
    l) LABELS="$OPTARG" ;;
    t) CURRENT_TAG="$OPTARG" ;;
    p) PR_NUMBER="$OPTARG" ;;
    a) AUTHOR="$OPTARG" ;;
    *) usage ;;
  esac
done

# ensure required fields are present
if [[ -z "$COMMIT_MSG" || -z "$CURRENT_TAG" || -z "$PR_NUMBER" || -z "$AUTHOR" ]]; then
    usage
fi

# extract first line of message
COMMIT_TITLE=$(echo "$COMMIT_MSG" | head -n 1)

# format release line: feat: docker docs #19 (@kylemmkay)
FORMATTED_LINE="$COMMIT_TITLE #$PR_NUMBER (@$AUTHOR)"

# --- functions ---

# converts v1.2.3 to 001002003 for integer comparison
version_to_int() {
    echo "$1" | sed 's/v//' | awk -F. '{ printf("%03d%03d%03d\n", $1,$2,$3); }'
}

increment_version() {
    local version=$1
    local bump=$2
    # remove 'v' prefix
    local clean_version="${version#v}"
    IFS='.' read -r major minor patch <<< "$clean_version"
    case "$bump" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
    esac
    echo "v$major.$minor.$patch"
}

get_priority() {
    local input=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    local prefix=""
    # extract prefix before colon (e.g., 'feat' from 'feat: description')
    [[ "$input" == *":"* ]] && prefix="${input%%:*}"

    if [[ "$prefix" =~ ^major$ || "$input" =~ "major" || "$input" =~ "breaking" || "$input" =~ "!" ]]; then
        echo 3
    elif [[ "$prefix" =~ ^(minor|feat) || "$input" =~ "feature" || "$input" =~ "enhancement" ]] || \
         [[ "$prefix" == "" && "$input" =~ "minor" ]]; then
        echo 2
    elif [[ "$prefix" =~ ^(patch|fix) || "$input" =~ "bug" || "$input" =~ "patch" ]]; then
        echo 1
    elif [[ "$input" =~ "skip" || "$input" =~ "ignore-release" ]]; then
        echo -1
    else
        echo 0
    fi
}

calculate_logic() {
    local msg_pri=$(get_priority "$COMMIT_TITLE")
    local lbl_pri=$(get_priority "$LABELS")
    local max_pri=$msg_pri
    # use highest priority
    (( lbl_pri > max_pri )) && max_pri=$lbl_pri
    local has_skip=false
    [[ "$msg_pri" -eq -1 || "$lbl_pri" -eq -1 ]] && has_skip=true

    if (( max_pri >= 1 )); then
        case $max_pri in
            3) echo "major|Breaking" ;;
            2) echo "minor|Enhancements" ;;
            1) echo "patch|Fixes" ;;
        esac
    elif [[ "$has_skip" == true ]]; then
        echo "skip|SKIPPED"
    else
        echo "patch|Maintenance"
    fi
}

# --- execution ---

RESULT=$(calculate_logic)
BUMP_TYPE=$(echo "$RESULT" | cut -d'|' -f1)
CATEGORY=$(echo "$RESULT" | cut -d'|' -f2)

if [[ "$BUMP_TYPE" == "skip" ]]; then
    echo "------------------------------------------"
    echo "Release logic: SKIPPED"
    echo "------------------------------------------"
    exit 0
fi

# calculate next version from current tag
CALCULATED_TAG=$(increment_version "$CURRENT_TAG" "$BUMP_TYPE")

# extract current draft version
FILE_TAG=$(grep "__version__ =" "$VERSION_FILE" | grep -oE "['\"][^'\"]+['\"]" | sed "s/['\"]//g")

CALC_INT=$(version_to_int "$CALCULATED_TAG")
FILE_INT=$(version_to_int "$FILE_TAG")

# compare versions
if [ "$FILE_INT" -gt "$CALC_INT" ]; then
    # Scenario: Draft is v0.4.0, calculated is v0.3.1. We keep v0.4.0.
    FINAL_TAG="$FILE_TAG"
    UPDATE_ACTION="Kept existing higher version $FILE_TAG instead of $CALCULATED_TAG"
elif [ "$FILE_INT" -eq "$CALC_INT" ]; then
    # Scenario: Draft is v0.3.1, calculated is v0.3.1. No change.
    FINAL_TAG="$FILE_TAG"
    UPDATE_ACTION="File already up to date ($FILE_TAG)"
else
    # Scenario: Draft is v0.3.0, calculated is v0.3.1. BUMP.
    FINAL_TAG="$CALCULATED_TAG"
    UPDATE_ACTION="Updated version to $FINAL_TAG"
    sed -i "s/^__version__ = .*/__version__ = \"$FINAL_TAG\"/" "$VERSION_FILE"
fi

echo "------------------------------------------"
echo "Release Draft Detection:"
echo "Commit Msg : $COMMIT_TITLE"
echo "Labels     : ${LABELS:-[None]}"
echo "Formatted  : $FORMATTED_LINE"
echo "Category   : $CATEGORY"
echo "Version    : $CURRENT_TAG -> $FINAL_TAG ($BUMP_TYPE)"
echo "Action     : $UPDATE_ACTION"
echo "------------------------------------------"

# update changelog
bash .forgejo/update-changelog.sh "$CURRENT_TAG" "$NEW_TAG" "$CATEGORY" "$FORMATTED_LINE"