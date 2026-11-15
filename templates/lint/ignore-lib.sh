# .stylelintignore (repo root) is the single exclusion list for every linter; stylelint reads it natively.
# Accepted lines: blank, "#" comments, and plain paths/globs of [A-Za-z0-9_./*-]. A negation ("!") or anything else fails loudly.
IGNORE_FILE=".stylelintignore"

# Prints one validated pattern per line; returns 1, naming every offending line, when any line is unsupported.
read_ignores() {
    local line n=0 bad=0
    [[ -f "$IGNORE_FILE" ]] || return 0
    while IFS= read -r line || [[ -n "$line" ]]; do
        n=$((n + 1))
        line="${line%$'\r'}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        if [[ -z "$line" || "$line" == \#* ]]; then
            continue
        fi
        if [[ "$line" =~ ^[A-Za-z0-9_./*-]+$ ]]; then
            printf '%s\n' "$line"
        else
            echo "${IGNORE_FILE}:${n}: unsupported pattern '${line}' (only plain paths and * / ** globs; no negation)" >&2
            bad=1
        fi
    done < "$IGNORE_FILE"
    return "$bad"
}

# php_ignore_patterns <phpcs|phpmd>: the entries as that tool's comma-separated pattern list ("" when there are none).
# Every entry is matched anywhere in the path; phpcs also gets an end-anchored form so "src/Foo" never hides "src/FooBar".
php_ignore_patterns() {
    local tool="$1" entries entry last csv=""
    entries="$(read_ignores)" || return 1
    while IFS= read -r entry; do
        entry="${entry#./}"
        entry="${entry#/}"
        entry="$(printf '%s' "$entry" | sed -E 's#(/+\*{0,2})+$##; s#\*+#*#g')"
        [[ -z "$entry" ]] && continue
        [[ "$entry" == \*/* ]] || entry="*/${entry}"
        csv+="${csv:+,}${entry}/*"
        last="${entry##*/}"
        if [[ "$tool" == phpcs ]]; then
            csv+=",${entry}\$"
        elif [[ "$last" == *.* ]]; then
            csv+=",${entry}"
        fi
    done <<<"$entries"
    printf '%s' "$csv"
}
