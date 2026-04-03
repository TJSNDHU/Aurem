# 🔐 GitHub Security Cleanup Guide

## ⚠️ CRITICAL: Two-Step Nuclear Security Lockdown

This guide ensures the old `admin123` password is **permanently erased** from existence.

---

## 🔴 STEP 1: BFG Scrub (Erase Git History)

### Why This Matters
Deleting code only removes it from the *current* version. The password still exists in Git's "memory" (commit history). Hackers can browse old commits and find it.

### Prerequisites
```bash
# On Mac
brew install bfg

# On Linux/Windows - Download JAR
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
```

### Execution Steps

```bash
# 1. Clone a fresh mirror (REQUIRED for BFG)
git clone --mirror git@github.com:YOUR_USERNAME/reroots-ca.git
cd reroots-ca.git

# 2. Create file with secrets to remove
cat > passwords.txt << 'EOF'
admin123
new_password_123
EOF

# 3. Run BFG to scrub secrets
java -jar bfg-1.14.0.jar --replace-text passwords.txt .
# Or if installed via brew: bfg --replace-text passwords.txt .

# 4. Clean up and force push
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force

# 5. Verify the password is gone
git log -p --all -S 'admin123' | head -50
# Should return NOTHING
```

### After BFG
- ⚠️ **All team members must re-clone the repo**
- The old repo on their machines will have conflicts

---

## 🔴 STEP 2: JWT Secret Rotation (Invalidate All Sessions)

### Why This Matters
If a hacker obtained a login token before the cleanup, they could still access the admin panel. Rotating the JWT_SECRET makes ALL existing tokens instantly worthless.

### What Will Happen
- ✅ All users (including you) will be logged out
- ✅ Any stolen tokens become useless
- ✅ You simply log back in with Google SSO

### Execution Steps

**On your production server:**

```bash
# 1. Generate a new secure secret
NEW_SECRET=$(openssl rand -base64 32)
echo "New JWT_SECRET: $NEW_SECRET"

# 2. Update .env file
cd /path/to/your/backend
sed -i "s/JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env

# 3. Restart the backend
sudo systemctl restart your-backend-service
# Or: pm2 restart backend
# Or: supervisorctl restart backend

# 4. Verify the change took effect
grep JWT_SECRET .env
```

### After JWT Rotation
1. Go to `/reroots-admin`
2. Click "Sign in with Google"
3. Use `teji.ss1986@gmail.com` or `admin@reroots.ca`
4. You're back in with a fresh, secure session

---

## 🟢 STEP 3: Rotate Other Secrets (Optional but Recommended)

While you're at it, consider rotating these too:

| Secret | How to Rotate |
|--------|---------------|
| `STRIPE_API_KEY` | Stripe Dashboard → Developers → API Keys → Roll Key |
| `RESEND_API_KEY` | Resend Dashboard → API Keys → Create New |
| `TWILIO_AUTH_TOKEN` | Twilio Console → Account → Auth Token → Rotate |
| `MONGO_URL` | Change DB password in MongoDB Atlas/Server |

---

## ✅ Security Checklist

- [ ] BFG Repo-Cleaner executed
- [ ] Force push completed
- [ ] Team re-cloned the repo
- [ ] JWT_SECRET rotated on production
- [ ] Backend restarted
- [ ] Successfully logged in with Google SSO
- [ ] (Optional) Other API keys rotated

---

**Document created:** February 21, 2026
**Priority:** 🔴 CRITICAL - Execute before Aura-Gen Duo launch
