#!/usr/bin/env bash
# Reproduce the security-review vectors from SECURITY_REVIEW_CHECKLIST.md.
# Uses a disposable archive under a temp directory. No network access.
# Override the interpreter with PYTHON=/path/to/python3.
set -uo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-python3}
PASSPHRASE='security-review-vector-passphrase'
fixture="$repo_root/tests/fixtures/security_review/fictional-2023-03-14.eml"
expected_sha='653eef314e3ce4374eff51724ecd6d75a4c82370262a409030329f3fe78919f2'

workdir=$(mktemp -d "${TMPDIR:-/tmp}/hb-security-vectors.XXXXXX")
cleanup() { rm -rf "$workdir"; }
trap cleanup EXIT

passed=0; failed=0; skipped=0
ok()   { passed=$((passed+1)); printf 'PASS  %s\n' "$1"; }
bad()  { failed=$((failed+1)); printf 'FAIL  %s\n' "$1"; }
skip() { skipped=$((skipped+1)); printf 'SKIP  %s\n' "$1"; }

cd "$repo_root" || exit 1

# 1. Fixture integrity
if command -v shasum >/dev/null 2>&1; then actual_sha=$(shasum -a 256 "$fixture" | cut -d' ' -f1)
else actual_sha=$(sha256sum "$fixture" | cut -d' ' -f1); fi
if [ "$actual_sha" = "$expected_sha" ]; then ok "fixture hash $expected_sha"
else bad "fixture hash changed: $actual_sha"; fi

# 2. Plaintext archive: import, search, verify
plain="$workdir/plain"
plain_import=$("$PYTHON" dispatch.py --archive "$plain" import "$fixture" 2>&1)
if printf '%s' "$plain_import" | grep -q "$expected_sha"; then ok "plaintext import records the original hash"
else bad "plaintext import did not report $expected_sha"; fi

plain_search=$("$PYTHON" dispatch.py --archive "$plain" search invoice 2>&1)
if printf '%s' "$plain_search" | grep -q "$expected_sha"; then ok "plaintext search finds the fixture"
else bad "plaintext search did not find the fixture"; fi

plain_verify=$("$PYTHON" dispatch.py --archive "$plain" verify 2>&1)
if [ "$plain_verify" = "[]" ]; then ok "plaintext verification reports no mismatches"
else bad "plaintext verification output: $plain_verify"; fi

# 3. Encrypted archive: creation requires the optional SQLCipher binding
if ! "$PYTHON" -c "import sqlcipher3" >/dev/null 2>&1; then
  skip "encrypted vectors: sqlcipher3 is not installed for $PYTHON"
  for name in "encrypted creation" "encrypted import" "encrypted search" \
              "ordinary sqlite3 refuses the database" "non-SQLite header" \
              "incorrect password rejected" "encrypted backup" "backup verification" \
              "restore into a new location" "restored archive search"; do
    skip "$name"
  done
else
  enc="$workdir/encrypted"
  created=$(printf '%s\n%s\n' "$PASSPHRASE" "$PASSPHRASE" | \
            "$PYTHON" dispatch.py --archive "$enc" init-encrypted 2>&1)
  if [ -f "$enc/.hb-encryption.json" ]; then ok "encrypted creation writes the descriptor"
  else bad "encrypted creation failed: $created"; fi

  enc_import=$(printf '%s\n' "$PASSPHRASE" | \
               "$PYTHON" dispatch.py --archive "$enc" import "$fixture" 2>&1)
  if printf '%s' "$enc_import" | grep -q "$expected_sha"; then ok "encrypted import records the original hash"
  else bad "encrypted import failed: $enc_import"; fi

  enc_search=$(printf '%s\n' "$PASSPHRASE" | \
               "$PYTHON" dispatch.py --archive "$enc" search invoice 2>&1)
  if printf '%s' "$enc_search" | grep -q "$expected_sha"; then ok "encrypted search finds the fixture"
  else bad "encrypted search failed: $enc_search"; fi

  if "$PYTHON" - "$enc/archive.sqlite3" <<'PY' >/dev/null 2>&1
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
try:
    connection.execute('SELECT count(*) FROM sqlite_master').fetchone()
except sqlite3.DatabaseError:
    raise SystemExit(0)
raise SystemExit(1)
PY
  then ok "ordinary sqlite3 refuses the encrypted database"
  else bad "ordinary sqlite3 opened the encrypted database"; fi

  header=$(head -c 16 "$enc/archive.sqlite3" 2>/dev/null)
  if [ "$header" != "SQLite format 3" ]; then ok "encrypted database header is not a plaintext SQLite header"
  else bad "encrypted database starts with the plaintext SQLite header"; fi

  wrong=$(printf '%s\n' 'definitely-not-the-passphrase' | \
          "$PYTHON" dispatch.py --archive "$enc" search invoice 2>&1)
  wrong_status=$?
  if [ "$wrong_status" -ne 0 ] && ! printf '%s' "$wrong" | grep -q "$expected_sha"; then
    ok "incorrect password is rejected without returning records"
  else bad "incorrect password did not fail closed (status $wrong_status)"; fi

  snapshot="$workdir/snapshot"
  backup_out=$(printf '%s\n' "$PASSPHRASE" | \
               "$PYTHON" dispatch.py --archive "$enc" backup "$snapshot" 2>&1)
  if [ -f "$snapshot/.hb-encryption.json" ]; then ok "encrypted backup keeps the descriptor"
  else bad "encrypted backup failed: $backup_out"; fi

  backup_check=$(printf '%s\n' "$PASSPHRASE" | \
                 "$PYTHON" dispatch.py --archive "$enc" verify-backup "$snapshot" 2>&1)
  if printf '%s' "$backup_check" | grep -qi 'ok\|true\|valid'; then ok "backup verification succeeds with the passphrase"
  else bad "backup verification output: $backup_check"; fi

  restored="$workdir/restored"
  restore_out=$(printf '%s\n' "$PASSPHRASE" | \
                "$PYTHON" dispatch.py --archive "$restored" restore "$snapshot" 2>&1)
  if [ -f "$restored/.hb-encryption.json" ]; then ok "restore writes a new encrypted archive"
  else bad "restore failed: $restore_out"; fi

  restored_search=$(printf '%s\n' "$PASSPHRASE" | \
                    "$PYTHON" dispatch.py --archive "$restored" search invoice 2>&1)
  if printf '%s' "$restored_search" | grep -q "$expected_sha"; then ok "restored archive answers the same search"
  else bad "restored search failed: $restored_search"; fi
fi

printf '\n%d passed, %d failed, %d skipped\n' "$passed" "$failed" "$skipped"
[ "$failed" -eq 0 ] || exit 1
