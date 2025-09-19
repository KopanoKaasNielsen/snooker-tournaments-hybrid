#!/bin/bash

echo "🚀 Fetching latest remote info..."
git fetch

echo -e "\n🔍 Current branch and tracking info:"
git branch -vv

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo -e "\n📌 Local commits not pushed to remote ($CURRENT_BRANCH):"
git log origin/$CURRENT_BRANCH..HEAD --oneline

echo -e "\n📥 Remote commits not pulled to local ($CURRENT_BRANCH):"
git log HEAD..origin/$CURRENT_BRANCH --oneline

echo -e "\n📊 Diff between local and remote ($CURRENT_BRANCH):"
git diff origin/$CURRENT_BRANCH --stat

echo -e "\n✅ Status:"
git status

echo -e "\n🌐 Remote repositories:"
git remote -v
