#!/bin/sh
# usage: seed.sh SRC DST
# Copy the sample seed into the cache directory without overwriting anything already there.
# An explicit loop, because `cp -n` exits non-zero on a skipped file in newer coreutils.
set -eu
mkdir -p "$2"
cd "$1"
find . -type f | while IFS= read -r f; do
  [ -e "$2/$f" ] || { mkdir -p "$2/$(dirname "$f")"; cp "$f" "$2/$f"; }
done
