# Traditional vs Modern CI/CD
|  -|Traditional | Modern |
| --|-------------|--------|
| Idea | Pipeline pushes change to envs  | Git is Source Of Truth. Env pulls the desired state|
| Credentials| Pipeline is trusted & powerful. Has credentials for k8s cluster, cloud provider, VMs etc| Pipeline does NOT need creds. It needs access to Git and Artifact Registry. GitOps Agent (ArgoCD/Flux) running inside cluster has infra creds. Uses k8s service account. May Assume IAM roles.| 
| Deploy logic | inside pipeline `kubectl apply` `helm upgrade` `ansible playbook` `cloud cli` | lives in Git (k8s Manifest, helm charts, kustomize overlays) GitOps controller reconciliation logic in ArgoCD that detects drift bewtee desired (git) and actual(cluster) state. Pipeline describes deployment. Cluster executes deployment |
|Drift| Drift common say manual scaling. `change the cluster, it stays`|` change Git, or it won’t stay`|

# Pipeline as Config

In modern CI/CD, a pipeline is defined as code — usually YAML or declarative configuration — that lives in a Git repository.
* Tekton: Pipeline and Task YAMLs stored in Git (runs as ephermal pod)
* GitHub Actions: .github/workflows/*.yaml (run as VM spun by Github)
* Jenkins: Jenkinsfile (Groovy DSL, usually in Git repo)
* GitLab CI: .gitlab-ci.yml
* Azure DevOps: azure-pipelines.yml

| Key point: The pipeline definition is version-controlled alongside your application code.|
--- 

#### Pipeline in Traditional CI/CD
- pipeline runs build, test, and deploys directly to the environment. 
Example: Jenkinsfile might do `kubectl apply -f deployment.yaml` to prod
- The pipeline itself is in Git (or sometimes in the tool’s UI, less ideal)

#### Pipeline in GitOps
- Pipeline runs build, test, package, and updates Git repository
- Example: Tekton pipeline updates values.yaml in GitOps repo
- Deployment does not happen in the pipeline — ArgoCD pulls changes and reconciles cluster
- Pipeline config still lives in Git (Tekton YAML, GitHub Actions YAML, Jenkinsfile, etc.)




# Enterprise CI/CD Flow (Traditional with Lightspeed, Tekton, Harness, Ansible)
- Dev push to github -> webhook -> Lightspeed Enterprise CI Orchestaror -> Runs Tekton Pipeline (ephemeral pod) -> build Image and publish to artifactory
- Pipelines are created in Lightspeed UI
- Harness (runs as Deamon Pod) Deploys (using ansible playbook) to cluster

1.  Developer pushes code or merges a PR. Repository contains code, `pipeline.yaml`,  `Dockerfile`,* Helm chart (or chart reference). GitHub is configured to notify Lightspeed when events occur.
2. GitHub sends an event (push / PR / tag) to Lightspeed using Webhook. Payload includes: Repository, Branch, Commit SHA
3. Lightspeed:* Identifies the application, Selects the correct CI pipeline, Applies enterprise rules (branch filters, policies) `GitHub does *not* run the pipeline itself`
4. Lightspeed Triggers a **Tekton PipelineRun** inside Kubernetes. Lightspeed acts as the **controller**, Tekton as the **executor**.
4. Build Visibility in Lightspeed: After Tekton completes, Lightspeed records:* Build status, Image version, Helm chart version, Commit metadata.This is why Lightspeed UI shows: Builds, Artifacts, Manifests
6. At this stage: CI is complete but nothing is deployed yet
7.  Harness: Continuous Deployment (CD)
    * Consumes pre-built artifacts
    * Manages deployment, approvals, rollbacks
    * Renders Helm templates. Applies manifests to OpenShift
    * Pod readiness, Health checks,  Rollback conditions

# GitOps for infra code
### Team managed Infra repo
- Pipeline only runs terraform plan
- No apply — prevents accidental changes. Each team can see what changes would happen, but cannot change shared infra directly
```
team1-aws-infra/
├─ modules/
├─ envs/dev/
├─ envs/sit/
├─ envs/prod/
└─ .github/workflows/plan-only.yml   # only runs terraform plan
```

### Central deployment repo (GitOps)
```
central-gitops-deploy/
├─ apps/
│   └─ app1/
│       ├─ main.tf        # Terraform code to deploy the app
│       └─ vars.tfvars    # Desired app commit SHA
├─ environments/
│   └─ dev/
│       └─ deployment.yaml   # K8s manifest using commit SHA
├─ .github/workflows/deploy.yml  # GitHub Actions CI/CD
└─ README.md

# main.tf
variable "app_commit" {
  type = string
}

provider "kubernetes" {
  config_path = "~/.kube/config"  # or use K8s provider for EKS
}

resource "kubernetes_deployment" "app1" {
  metadata {
    name      = "app1"
    namespace = "dev"
  }

  spec {
    replicas = 2
    selector {
      match_labels = {
        app = "app1"
      }
    }
    template {
      metadata {
        labels = {
          app = "app1"
        }
      }
      spec {
        container {
          name  = "app1"
          image = "ghcr.io/my-org/app1:${var.app_commit}"  # uses commit as tag
          ports {
            container_port = 8080
          }
        }
      }
    }
  }
}

#vars.tfvars 
#-------
# Specify the app commit to deploy
app_commit = "abc123"   # replace with desired commit SHA


```
- Each app has its own folder
- vars.tfvars specifies which commit SHA or Docker tag to deploy
-Teams cannot modify other apps; folder permissions or branch rules enforce this