#!/bin/bash

# --- functions ---

get_tag_line_number() {
    local tag="$1"
    local file="$2"
    local line_num=$(grep -n "^## .*$tag" "$file" | head -n 1 | cut -d: -f1)
    echo "${line_num:-0}"
}

find_header_in_range() {
    local start=2
    local end="$1"
    local file="$2"

    if [ "$end" -le "$start" ]; then
        echo "$end"
        return
    fi

    local relative_found=$(sed -n "${start},${end}p" "$file" | grep -n "^## " | head -n 1 | cut -d: -f1)

    if [ -n "$relative_found" ]; then
        echo "$((start + relative_found - 1))"
    else
        echo "0"
    fi
}

# export from line to end of file
export_from_line() {
    local start_line="$1"
    local src_file="$2"
    local dest_file="$3"
    tail -n +"$start_line" "$src_file" > "$dest_file"
}

# export specific line range
export_range() {
    local start="$1"
    local end="$2"
    local src_file="$3"
    local dest_file="$4"

    # sed -n 'X,Yp' prints lines X to Y
    sed -n "${start},${end}p" "$src_file" > "$dest_file"
}

reassemble_header() {
    local src_header="$1"
    local dest_file="$2"
    local new_tag="$3"
    local date="$4"
    local header_updated=false

    # clear/create destination file
    > "$dest_file"

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^##\  ]] && [ "$header_updated" = false ]; then
            # extract version from line (e.g., 'v0.4.0' from '## v0.4.0 - 2026...')
            local current_version=$(echo "$line" | cut -d' ' -f2)
            
            # use highest version
            local higher_version=$(echo -e "$current_version\n$new_tag" | sort -V | tail -n 1)

            echo "## $higher_version - $date" >> "$dest_file"
            header_updated=true
            
            if [ "$higher_version" != "$new_tag" ]; then
                echo "Kept existing higher version $higher_version instead of $new_tag"
            fi
        else
            echo "$line" >> "$dest_file"
        fi
    done < "$src_header"

    if [ "$header_updated" = false ]; then
        echo "# Changelog" > "$dest_file"
        echo "" >> "$dest_file"
        echo "## $new_tag - $date" >> "$dest_file"
    fi
}

inject_changes() {
    local dest_file="$1"
    local category="$2"
    local commit_msg="$3"
    local tmp_file="inject.tmp"

    # if category exists, insert after header
    if grep -q "^### $category" "$dest_file"; then
        local cat_line=$(grep -n "^### $category" "$dest_file" | cut -d: -f1)
        local insert_at=$((cat_line + 1)) 

        head -n "$insert_at" "$dest_file" > "$tmp_file"
        echo "- $commit_msg" >> "$tmp_file"
        tail -n +"$((insert_at + 1))" "$dest_file" >> "$tmp_file"
        mv "$tmp_file" "$dest_file"
        return
    fi

    # find target line (version header)
    local target_line=$(grep -n "^## " "$dest_file" | head -n 1 | cut -d: -f1)

    # handle category hierarchy
    local final_target=$target_line
    
    if [ "$category" == "Breaking" ]; then
        final_target=$target_line
    elif [ "$category" == "Enhancements" ]; then
        local break_line=$(grep -n "^### Breaking" "$dest_file" | cut -d: -f1)
        if [ -n "$break_line" ]; then
            # find last bullet in breaking section
            local rel_last=$(sed -n "${break_line},/^##/p" "$dest_file" | grep -n "^-" | tail -n 1 | cut -d: -f1)
            final_target=$((break_line + rel_last - 1))
        fi
    elif [ "$category" == "Fixes" ]; then
        local enh_line=$(grep -n "^### Enhancements" "$dest_file" | cut -d: -f1)
        local break_line=$(grep -n "^### Breaking" "$dest_file" | cut -d: -f1)
        if [ -n "$enh_line" ]; then
            local rel_last=$(sed -n "${enh_line},/^##/p" "$dest_file" | grep -n "^-" | tail -n 1 | cut -d: -f1)
            final_target=$((enh_line + rel_last - 1))
        elif [ -n "$break_line" ]; then
            local rel_last=$(sed -n "${break_line},/^##/p" "$dest_file" | grep -n "^-" | tail -n 1 | cut -d: -f1)
            final_target=$((break_line + rel_last - 1))
        fi
    elif [ "$category" == "Maintenance" ]; then
        [ -n "$(tail -n 1 "$dest_file")" ] && echo "" >> "$dest_file"
        echo -e "### Maintenance\n\n- $commit_msg" >> "$dest_file"
        return
    fi

    # reassemble using sandwich method
    head -n "$final_target" "$dest_file" > "$tmp_file"
    echo -e "\n### $category\n\n- $commit_msg" >> "$tmp_file"
    tail -n +"$((final_target + 1))" "$dest_file" >> "$tmp_file"
    mv "$tmp_file" "$dest_file"
}

# --- main script ---

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 <OLD_TAG> <NEW_TAG> <CATEGORY> <COMMIT_MSG>"
    exit 1
fi

OLD_TAG="$1"
NEW_TAG="$2"
CATEGORY="$3"
COMMIT_MSG="$4"
FILE="CHANGELOG.md"
DATE=$(date +%Y-%m-%d)

TEMP_HEADER="header.tmp"
TEMP_BODY="body.tmp"

# find old tag line number
OLD_LINE_NUM=$(get_tag_line_number "$OLD_TAG" "$FILE")

# split file into header and body
END_RANGE=$((OLD_LINE_NUM - 1))
export_range 1 "$END_RANGE" "$FILE" "$TEMP_HEADER"
export_from_line "$OLD_LINE_NUM" "$FILE" "$TEMP_BODY"

# reassemble header with new version
reassemble_header "$TEMP_HEADER" "$FILE" "$NEW_TAG" "$DATE"

# inject category and commit message
inject_changes "$FILE" "$CATEGORY" "$COMMIT_MSG"

# add spacing newline if needed
[ -n "$(tail -n 1 "$FILE")" ] && echo "" >> "$FILE"

# append old versions
cat "$TEMP_BODY" >> "$FILE"

# strip header for release body
sed -i '1,4d' "$TEMP_HEADER"

echo "Header processed. $FILE now contains the title and the new version header."