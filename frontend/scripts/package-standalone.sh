#!/usr/bin/env bash
# Build the site and package it as a self-contained bundle (web.tgz) that only needs Node.
# Run it on the server with: PORT=3100 node web/server.js (plus the LiveKit env vars).
set -euo pipefail
cd "$(dirname "$0")/.."

pnpm build

out="$(mktemp -d)"
cp -RL .next/standalone "$out/web"
cp -R .next/static "$out/web/.next/static"
cp -R public "$out/web/public"

# pnpm keeps dependencies in node_modules/.pnpm behind symlinks, which don't survive
# copying to another OS. Hoist every package to the top level instead.
(
  cd "$out/web/node_modules"
  for dir in .pnpm/*/node_modules/*; do
    name="$(basename "$dir")"
    if [[ "$name" == @* ]]; then
      for pkg in "$dir"/*; do
        target="$name/$(basename "$pkg")"
        [[ -e "$target" ]] || { mkdir -p "$name"; cp -R "$pkg" "$target"; }
      done
    else
      [[ -e "$name" ]] || cp -R "$dir" "$name"
    fi
  done
  rm -rf .pnpm @img/sharp-darwin-* @img/sharp-libvips-darwin-*
)

tar -czf web.tgz -C "$out" web
rm -rf "$out"
echo "Wrote $(pwd)/web.tgz"
