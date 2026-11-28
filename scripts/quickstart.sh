#!/usr/bin/env bash
# Disposable synthetic archive: import, search, verify, clean up. No network.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
workdir=$(mktemp -d "${TMPDIR:-/tmp}/hb-continuum-quickstart.XXXXXX")
cleanup() { rm -rf "$workdir"; }
trap cleanup EXIT

archive="$workdir/archive"
fixture="$workdir/sample.eml"

cat > "$fixture" <<'EML'
From: Ada Example <ada@example.invalid>
To: Grace Example <grace@example.invalid>
Subject: Fictional invoice for March
Date: Tue, 14 Mar 2023 09:15:00 +0000
Message-ID: <quickstart-0001@example.invalid>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

This message is entirely fictional and exists only for the quickstart.

The invoice number is QS-1042 and it is attached to a project that never
existed. Ada Example signed it on a made-up planet.
EML

cd "$repo_root"

echo "1. Import a synthetic EML file"
imported=$(python3 dispatch.py --archive "$archive" import "$fixture" 2>&1)
echo "$imported"
hash_id=$(printf '%s\n' "$imported" | tail -n 1)
echo
echo "2. Import the same file again (deduplication, no new record)"
again=$(python3 dispatch.py --archive "$archive" import "$fixture" 2>&1)
echo "$again"
case "$again" in
  *existing*) ;;
  *) echo "quickstart: FAILED (duplicate was not detected)"; exit 1 ;;
esac
echo
echo "3. Search the archive"
results=$(python3 dispatch.py --archive "$archive" search invoice)
echo "$results"
case "$results" in
  *"$hash_id"*) ;;
  *) echo "quickstart: FAILED (search did not return the imported record)"; exit 1 ;;
esac
echo
echo "4. Verify stored bytes against their hashes"
verification=$(python3 dispatch.py --archive "$archive" verify)
echo "$verification"
[ "$verification" = "[]" ] || { echo "quickstart: FAILED (verification reported mismatches)"; exit 1; }
echo
echo "quickstart: OK (temporary archive removed)"
