# GitOps with Argo CD – Spring Boot (Dev & QA)

This README explains **GitOps from first principles**, using a **Spring Boot application**, **GitHub Actions (CI)**, and **Argo CD (CD)**.

The goal is clarity and auditability, not clever automation.

---

## 1. What problem GitOps solves

Traditional pipelines:
- CI builds the app
- CI directly deploys to Kubernetes

Problems:
- Cluster state can drift from Git
- Hard to audit who deployed what
- Rollbacks are tool-specific

**GitOps flips this model**:

> Git is the single source of truth for what should be running in the cluster.

The cluster is continuously reconciled to match Git.

---

## 2. Two-repo model (most common and safest)

### Repo A – Application repo (Spring Boot)

Purpose: **build artifacts only**

```
lending-app/
  src/
  Dockerfile
  pom.xml
  .github/workflows/ci.yml
```

Responsibilities:
- Compile and test code
- Build container image
- Push image to registry

**This repo does NOT deploy to Kubernetes.**

---

### Repo B – GitOps repo (environment state)

Purpose: **declare what runs in each environment**

```
lending-gitops/
  apps/
    lending-app/
      base/
      overlays/
        dev/
        qa/
```

Responsibilities:
- Kubernetes manifests (Deployment, Service, Route)
- Environment-specific configuration
- Image tag / commit hash

This repo represents the **desired state of the cluster**.

---

## 3. CI pipeline (GitHub Actions) – what it does

CI is intentionally boring and limited.

Typical flow:
1. Build & test Spring Boot app
2. Build container image
3. Push image to registry

Example outcome:
```
my-registry/lending-app:1a2b3c
```

**CI stops here.**

No kubectl. No helm. No cluster credentials.

---

## 4. Manual GitOps deployment (intentional & valid)

Deployment happens via **Git change**, not CI.

### Step-by-step

1. Developer opens the GitOps repo
2. Chooses environment (dev or qa)
3. Updates image tag
4. Commits or raises a PR

Example (`kustomization.yaml`):

```yaml
images:
  - name: my-registry/lending-app
    newTag: 1a2b3c
```

This commit now represents:

> "This is what should be running in dev."

---

## 5. Argo CD – what it does

Argo CD runs **inside the cluster** and continuously:

1. Pulls the GitOps repo
2. Renders manifests (plain YAML / Kustomize / Helm)
3. Compares Git vs live cluster state
4. Applies changes to reconcile the cluster

Argo CD does **not build images**.
Argo CD does **not contain business logic**.

---

## 6. End-to-end flow (manual promotion)

```
Developer pushes code
   |
   v
GitHub Actions (CI)
   - build
   - test
   - push image
   |
   v
Image registry
   |
   |  (manual Git change)
   v
GitOps repo (image tag updated)
   |
   v
Argo CD detects Git change
   |
   v
Kubernetes Deployment rolls out
```

---

## 7. Why teams prefer manual GitOps updates

### Clear separation of concerns

| Responsibility | Owner |
|---------------|-------|
| Build artifacts | CI |
| Decide what runs | Humans via Git |
| Apply to cluster | Argo CD |

---

### Auditability
- Every deployment is a Git commit
- Who, when, why is recorded
- Rollback = `git revert`

---

### Safety (especially for prod)
- CI has no prod access
- No accidental auto-deploys
- PR approvals enforce control

---

## 8. Dev vs QA with Kustomize (example)

### Base (shared)

```
apps/lending-app/base/
  deployment.yaml
  service.yaml
  kustomization.yaml
```

### Dev overlay

```
apps/lending-app/overlays/dev/
  kustomization.yaml   # image tag, replicas
```

### QA overlay

```
apps/lending-app/overlays/qa/
  kustomization.yaml   # different image tag, replicas
```

Only the **differences** live in overlays.

---

## 9. Rollback model

Rollback is boring (by design):

1. Revert Git commit in GitOps repo
2. Argo CD reconciles cluster back

No special tooling required.

---

## 10. Why this is considered “mature GitOps”

- Git is the only source of truth
- CI and CD are cleanly separated
- Humans control promotion
- Argo CD enforces convergence

This model is common in:
- banks
- regulated enterprises
- multi-team platforms

---

## 11. One-sentence summary (use in interviews)

> "Our CI only builds images. Deployment is a Git change in the GitOps repo, and Argo CD reconciles the cluster to match Git."

---

## 12. Key takeaway

**GitOps is not about speed.**

It is about:
- correctness
- traceability
- predictability

Boring on purpose.

