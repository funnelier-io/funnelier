# Funnelier — Git Versioning & GitHub Sync Strategy

> Created: April 16, 2026
> Applies to: `funnelier` repository

---

## 📍 Current State

| Item | Status |
|---|---|
| Local commits | 36 (all on `master`) |
| Remote | **None configured** |
| Branches | `master` only |
| Tags | None |
| Uncommitted work | Phase 36 partial (13 files) |
| CI workflows | Exist (`.github/workflows/ci.yml`, `cd.yml`) but never triggered |

---

## 🚀 Step 1: Initial GitHub Sync

### 1.1 Create the GitHub repository

```bash
# Option A: GitHub CLI
gh repo create funnelier --private --source=. --remote=origin

# Option B: Manual — create repo on GitHub, then:
git remote add origin git@github.com:<org>/funnelier.git
```

### 1.2 Commit or stash uncommitted Phase 36 work

```bash
cd /Volumes/Blackhole/Developer_Storage/Repositories/Work/funnelier

# Option A: Commit Phase 36 progress
git add -A
cat > /tmp/funnelier_commit.txt << 'EOF'
feat: Phase 36 — Camunda BPMS Advanced Process Features (partial)

- SMS compensation worker for failed send recovery
- Stale delivery notification worker (24h timer)
- ERP sync escalation BPMN process and worker
- Updated campaign_lifecycle.bpmn with error boundaries
- Updated funnel_journey.bpmn with message correlation
- Updated deployment.py, workers init, journey routes
- Unit tests updated
EOF
git commit -F /tmp/funnelier_commit.txt

# Option B: Stash for later
git stash push -m "Phase 36 WIP"
```

### 1.3 Rename branch & tag baseline

```bash
# Rename master → main
git branch -m master main

# Tag the baseline
git tag -a v0.1.0 -m "Release v0.1.0: Phases 1-35, 447 unit tests, 14 dashboard pages, Camunda BPMS integration"

# Push everything
git push -u origin main
git push origin --tags
```

### 1.4 Create dev branch

```bash
git checkout -b dev
git push -u origin dev
```

---

## 🔀 Step 2: Branching Strategy

```
main         ← Production releases (protected, PR-only)
dev          ← Integration branch (protected, PR-only)
feature/*    ← New features → PR to dev
fix/*        ← Bug fixes → PR to dev
hotfix/*     ← Emergency production fixes → PR to main + cherry-pick to dev
chore/*      ← Maintenance (deps, docs, CI) → PR to dev
release/*    ← Release prep (freeze, final QA) → PR to main
```

### Branch Protection Rules (GitHub Settings)

**`main` branch:**
- ✅ Require pull request (min 1 review)
- ✅ Require status checks: `ci / lint`, `ci / test-backend`, `ci / build-frontend`
- ✅ Require branch to be up-to-date
- ✅ No direct push
- ✅ No force push
- ✅ No deletions

**`dev` branch:**
- ✅ Require pull request (min 1 review)
- ✅ Require status checks: `ci / lint`, `ci / test-backend`
- ✅ No force push
- ✅ No deletions

---

## 📝 Step 3: Commit Convention

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `chore`, `refactor`, `docs`, `perf`, `test`, `style`, `ci`

**Scopes:** `auth`, `leads`, `campaigns`, `communications`, `sales`, `analytics`, `segments`,
`notifications`, `tenants`, `billing`, `team`, `camunda`, `frontend`, `i18n`, `infra`, `ci`

**Examples:**
```
feat(analytics): add cohort comparison chart
fix(campaigns): prevent duplicate SMS sends on retry
chore(ci): add playwright to CI matrix
docs(roadmap): mark Phase 37 as completed
```

**Multi-line commits:** Use `git commit -F /tmp/funnelier_commit.txt` to avoid shell quoting issues.

---

## 🏷️ Step 4: Versioning (Semantic Versioning)

```
MAJOR.MINOR.PATCH

0.x.x  →  Pre-production / active development
1.0.0  →  First production release
```

### Version Milestones

| Version | Milestone | Estimated |
|---|---|---|
| `v0.1.0` | Baseline — all 35 phases, Camunda integration | Apr 2026 |
| `v0.2.0` | Feature hardening, UX polish, expanded tests | Sep 2026 |
| `v0.9.0` | Release candidate — security audit, load tested | Dec 2026 |
| `v1.0.0` | Production launch | Mar 2027 |

### Tagging Releases

```bash
# From main branch after merging a release/* PR
git tag -a v0.2.0 -m "Release v0.2.0: multi-tenant onboarding, A/B testing, PWA"
git push origin v0.2.0
```

---

## 🔄 Step 5: Development Workflow

### Feature Development

```bash
# 1. Start from dev
git checkout dev && git pull origin dev

# 2. Create feature branch
git checkout -b feature/phase-37-onboarding-wizard

# 3. Work, commit (using conventional commits)
git add -A
git commit -F /tmp/funnelier_commit.txt

# 4. Push and create PR → dev
git push -u origin feature/phase-37-onboarding-wizard
# Create PR on GitHub targeting dev

# 5. After review + CI passes → squash merge to dev
# 6. Delete feature branch
```

### Release Process

```bash
# 1. Create release branch from dev
git checkout dev && git pull
git checkout -b release/v0.2.0

# 2. Final fixes, version bump, changelog
# 3. PR → main (require review + CI)
# 4. After merge: tag on main
git checkout main && git pull
git tag -a v0.2.0 -m "Release v0.2.0: ..."
git push origin v0.2.0

# 5. Back-merge main → dev
git checkout dev && git merge main && git push
```

### Hotfix Process

```bash
# 1. Branch from main
git checkout main && git pull
git checkout -b hotfix/fix-auth-bypass

# 2. Fix, commit, PR → main
# 3. After merge: tag patch version
git tag -a v0.1.1 -m "Hotfix v0.1.1: fix auth bypass"
git push origin v0.1.1

# 4. Cherry-pick to dev
git checkout dev && git cherry-pick <commit> && git push
```

---

## ⚙️ Step 6: GitHub Repository Settings

### Recommended Settings

- **Default branch:** `main`
- **Merge button:** Allow squash merge (default), allow merge commits, disable rebase merge
- **Auto-delete head branches:** ✅ Enabled
- **Dependabot:** ✅ Enabled for pip and npm security updates
- **GitHub Actions:** CI triggered on PR to `main`/`dev` + push to `main`/`dev`

### Required Files

| File | Status |
|---|---|
| `.env.example` | ✅ Exists |
| `.github/workflows/ci.yml` | ✅ Exists |
| `.github/workflows/cd.yml` | ✅ Exists |
| `.github/copilot-instructions.md` | ✅ Exists |
| `AGENTS.md` | ✅ Exists |
| `docs/ROADMAP.md` | ✅ Created |
| `docs/GIT_STRATEGY.md` | ✅ This file |
| `docs/ARCHITECTURE.md` | ✅ Exists |
| `docs/GETTING_STARTED.md` | ✅ Exists |
| `docs/IMPLEMENTATION_SUMMARY.md` | ✅ Exists |
| `docs/CAMUNDA_FEASIBILITY.md` | ✅ Exists |
| `docs/CHANGELOG.md` | 📋 Create at first release |

---

## 📋 Immediate Action Checklist

- [ ] Commit or stash Phase 36 uncommitted work
- [ ] Create GitHub repository (private)
- [ ] Rename `master` → `main`
- [ ] Push all history to GitHub
- [ ] Tag `v0.1.0`
- [ ] Create `dev` branch and push
- [ ] Configure branch protection rules on `main` and `dev`
- [ ] Enable Dependabot
- [ ] Enable auto-delete head branches
- [ ] Verify CI workflow triggers on first PR
- [ ] Create `docs/CHANGELOG.md` template

