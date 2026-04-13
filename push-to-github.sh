#!/bin/bash
# Plexus Coffee Dashboard — GitHub Setup Script
# Run this ONCE from Terminal to create the repo and go live.
# After it succeeds, you can delete this file.

set -e

TOKEN="ghp_Bo01e0IFD3tMqVpvbG6oj9A4HlK9MV3R5BuC"
USERNAME="chanybar"
REPO="plexus-coffee-dashboard"

echo ""
echo "☕ Plexus Coffee Dashboard — Pushing to GitHub..."
echo ""

# 1. Create the repo on GitHub
echo "→ Creating repo $USERNAME/$REPO..."
HTTP=$(curl -s -o /tmp/gh_response.json -w "%{http_code}" \
  -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO\",\"description\":\"Plexus Technology Coffee Route Outreach Dashboard\",\"private\":false,\"auto_init\":false}")

if [ "$HTTP" = "201" ]; then
  echo "  ✓ Repo created!"
elif [ "$HTTP" = "422" ]; then
  echo "  ✓ Repo already exists, continuing..."
else
  echo "  ✗ Failed to create repo (HTTP $HTTP)"
  cat /tmp/gh_response.json
  exit 1
fi

# 2. Set remote and push
cd "$(dirname "$0")"
git remote remove origin 2>/dev/null || true
git remote add origin https://$TOKEN@github.com/$USERNAME/$REPO.git
echo "→ Pushing to GitHub..."
git push -u origin main --force
echo "  ✓ Pushed!"

# 3. Enable GitHub Pages (deploy from main branch root)
echo "→ Enabling GitHub Pages..."
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$USERNAME/$REPO/pages \
  -d '{"source":{"branch":"main","path":"/"}}' > /dev/null

echo "  ✓ GitHub Pages enabled!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎉 DONE! Your dashboard will be live at:"
echo "  https://$USERNAME.github.io/$REPO"
echo ""
echo "  (GitHub Pages takes ~60 seconds to go live)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Delete this file after running — it contains your token."
echo ""
