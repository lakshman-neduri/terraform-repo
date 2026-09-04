# Terraform CI/CD with GitHub Actions and AI Plan Review

## Overview

This repository demonstrates a Terraform CI/CD workflow using GitHub Actions with:

* Git-based environment promotion
* Terraform CLI workspaces
* GitHub Environments
* AWS authentication using GitHub OIDC
* Automated Terraform plan
* Manual Terraform apply for QA/Production
* AI-assisted Terraform plan analysis using Gemini

The goal of this POC is to demonstrate how Terraform infrastructure changes can be automatically planned, reviewed, and promoted through environments while using AI to provide an additional summary and risk analysis of Terraform changes.

---

# Architecture

```text
                         GitHub Repository
                                │
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
             feature/*                     main
                  │                           │
                  │ PR                        │
                  ▼                           │
        Terraform Plan - DEV                 │
                  │                           │
                  ▼                           │
           Gemini AI Review                   │
                  │                           │
                  ▼                           │
             PR Comment                      │
                                              │
                  Merge                       │
                  └──────────────┬─────────────┘
                                 │
                                 ▼
                              main
                                 │
                                 │ PR
                                 ▼
                             release
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
                 QA Plan                  PROD Plan
                    │                         │
                    ▼                         ▼
                AI Review                 AI Review
                    │                         │
                    └────────────┬────────────┘
                                 │
                          Manual Approval
                                 │
                         workflow_dispatch
                                 │
                         ┌───────┴───────┐
                         │               │
                         ▼               ▼
                        QA              PROD
                       Apply            Apply
```

---

# 1. Branching Strategy

The repository follows a simple environment promotion model.

```text
feature/*
    │
    │ Pull Request
    ▼
   main
    │
    │ Pull Request
    ▼
 release
```

## Branch Responsibilities

### `feature/*`

Feature branches are used for infrastructure development.

Example:

```text
feature/add-ecr
feature/update-ec2
feature/add-s3
```

Changes are developed and tested through a Pull Request.

---

### `main`

The `main` branch represents the **Dev environment**.

When a Pull Request is opened from a feature branch to `main`:

```text
feature/* → main
```

GitHub Actions automatically runs:

```text
Terraform Init
       ↓
Select dev workspace
       ↓
Terraform Plan
       ↓
AI Terraform Review
```

The Terraform plan and AI review are provided as part of the Pull Request review.

After the Pull Request is merged, the Dev Terraform changes can be applied automatically.

---

### `release`

The `release` branch represents the promotion path for **QA and Production**.

The promotion flow is:

```text
main → release
```

When a Pull Request is opened from `main` to `release`, Terraform plans are generated for:

```text
qa
prod
```

The plans run using a GitHub Actions matrix.

This allows the same Terraform configuration to be evaluated against both environments before deployment.

---

# 2. Terraform Workspaces

Terraform CLI workspaces are used to maintain separate Terraform states for different environments.

The following workspaces are used:

```text
dev
qa
prod
```

The workspace is selected during the GitHub Actions workflow.

For example:

```bash
terraform workspace select dev
```

or during initial setup:

```bash
terraform workspace select -or-create dev
```

The same Terraform configuration is used for all environments, while each workspace maintains its own state.

Conceptually:

```text
Terraform Configuration
          │
          ├──────────────┐
          │              │
          ▼              ▼
       dev state       qa state
          │
          │
          ▼
       prod state
```

---

# 3. Terraform Remote State

Terraform state is stored remotely in an Amazon S3 backend.

Example backend configuration:

```hcl
terraform {
  backend "s3" {
    bucket               = "lakshman-terraform-state-bucket"
    region               = "us-east-1"
    use_lockfile         = true
    workspace_key_prefix = "environments"
  }
}
```

The repository-specific backend key is supplied during `terraform init`.

Example:

```bash
terraform init \
  -backend-config="key=terraform-repo/terraform.tfstate"
```

With Terraform workspaces, the state is logically separated by environment.

Conceptually:

```text
S3
└── environments/
    ├── dev/
    │   └── terraform-repo/terraform.tfstate
    │
    ├── qa/
    │   └── terraform-repo/terraform.tfstate
    │
    └── prod/
        └── terraform-repo/terraform.tfstate
```

This allows GitHub Actions to run Terraform against the correct environment state.

---

# 4. GitHub Environments

GitHub Environments are mapped to the Terraform environments:

| GitHub Environment | Terraform Workspace |
| ------------------ | ------------------- |
| `dev`              | `dev`               |
| `qa`               | `qa`                |
| `prod`             | `prod`              |

The workflow dynamically selects the GitHub Environment.

For example:

```yaml
environment: dev
```

or:

```yaml
environment: ${{ matrix.workspace }}
```

This provides a clean mapping:

```text
GitHub Environment
        │
        ▼
Terraform Workspace
        │
        ▼
Environment-specific infrastructure
```

GitHub Environment variables and secrets can also be used for environment-specific configuration.

Example:

```text
AWS_REGION
AWS_ROLE_ARN
```

Production can additionally be configured with required reviewers if approval is required before deployment.

---

# 5. AWS Authentication

GitHub Actions authenticates with AWS using **GitHub OIDC** rather than storing long-lived AWS access keys.

The workflow uses:

```yaml
permissions:
  contents: read
  id-token: write
```

AWS credentials are configured using:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
    aws-region: ${{ vars.AWS_REGION }}
```

The authentication flow is:

```text
GitHub Actions
      │
      │ OIDC token
      ▼
AWS IAM
      │
      │ Assume Role
      ▼
Temporary AWS credentials
      │
      ▼
Terraform
      │
      ├── S3 State
      └── AWS Infrastructure
```

This avoids storing permanent AWS access keys in GitHub.

---

# 6. Dev Terraform Plan

For a Pull Request targeting `main`, the Dev workflow runs Terraform against the `dev` workspace.

The major steps are:

```yaml
- name: Terraform Init
  run: terraform init -input=false

- name: Select Dev workspace
  run: terraform workspace select dev

- name: Verify Workspace
  run: terraform workspace show

- name: Terraform Plan
  run: terraform plan -input=false -out=tfplan.binary
```

The saved plan is then converted to JSON:

```yaml
- name: Convert Terraform Plan to JSON
  run: terraform show -json tfplan.binary > tfplan.json
```

The JSON representation is used as the input for the AI review.

---

# 7. Terraform Plan Summary

In addition to the AI review, the workflow generates a deterministic Terraform plan summary.

The summary can identify:

* Resources to create
* Resources to update
* Resources to destroy
* Resources requiring replacement

Example:

```text
Terraform Plan Summary

Create:   2
Change:   1
Replace:  1
Destroy:  0
```

This provides a quick overview of the infrastructure changes before deployment.

---

# 8. AI Terraform Plan Review

An AI review layer was added to analyze the Terraform plan.

The workflow uses:

```text
Terraform Plan
      │
      ▼
tfplan.binary
      │
      ▼
terraform show -json
      │
      ▼
tfplan.json
      │
      ▼
Python AI Review Script
      │
      ▼
Gemini API
      │
      ▼
AI Terraform Review
```

The Python script extracts the resource changes from the Terraform plan and sends the relevant information to Gemini.

The AI is instructed to analyze:

* Infrastructure changes
* Resource creation
* Resource updates
* Resource deletion
* Resource replacements
* Security risks
* Availability risks
* Unexpected configuration changes
* Potential cost implications

---

# 9. AI Risk Classification

The AI classifies the overall Terraform change using:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

It also provides a recommendation:

```text
SAFE TO PROCEED
REVIEW REQUIRED
HIGH RISK
```

For example, changing an ECR repository name can result in a replacement:

```text
aws_ecr_repository.frontend_poc[0]

delete → create
```

The AI can identify this as a potentially destructive change and explain the possible impact, such as repository image loss or application references to the previous repository URL.

The AI is used as an **additional review layer**, not as the final authority for applying infrastructure changes.

---

# 10. Gemini Integration

The Gemini Python SDK is installed in the GitHub Actions runner:

```yaml
python -m pip install google-genai
```

The Gemini API key is stored as a GitHub Actions secret:

```text
GEMINI_API_KEY
```

The workflow exposes the secret to the Python script through an environment variable:

```yaml
env:
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

The Python script uses the Gemini SDK to generate the Terraform review.

Example:

```python
from google import genai

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.7-flash",
    contents=prompt
)

print(response.text)
```

The AI output is stored as:

```text
ai-review.md
```

---

# 11. Pull Request AI Review

The AI review can be posted back to the Pull Request.

The overall developer experience becomes:

```text
Developer changes Terraform
          │
          ▼
Create Pull Request
          │
          ▼
GitHub Actions
          │
          ▼
Terraform Plan
          │
          ▼
AI Review
          │
          ▼
Pull Request
          │
          ├── Terraform summary
          │
          └── AI Terraform review
```

The developer can therefore see both the deterministic Terraform plan and an AI-generated explanation of the changes.

---

# 12. Release Plan

When promoting:

```text
main → release
```

the release plan workflow uses a matrix:

```yaml
strategy:
  matrix:
    workspace:
      - qa
      - prod
```

This generates separate Terraform plans for:

```text
QA
 │
 └── Terraform Plan
       ↓
     AI Review

PROD
 │
 └── Terraform Plan
       ↓
     AI Review
```

This allows changes to be reviewed for both environments before applying them.

---

# 13. Release Apply

Production and QA deployment are not automatically applied from the Pull Request.

The release apply workflow uses:

```yaml
on:
  workflow_dispatch:
```

The user selects the target environment:

```text
qa
prod
```

The workflow then:

```text
Select Environment
       │
       ▼
GitHub Environment
       │
       ▼
Terraform Workspace
       │
       ▼
Terraform Plan
       │
       ▼
Terraform Apply
```

A fresh Terraform plan is generated immediately before the apply.

The saved plan is then applied:

```bash
terraform apply -input=false tfplan.binary
```

This ensures that the apply uses the exact plan generated during that workflow execution.

---

# 14. Complete CI/CD Flow

The complete implementation is:

```text
                    feature/*
                       │
                       │ PR
                       ▼
                     main
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
         Dev Terraform      AI Review
             Plan                │
              │                  │
              └────────┬─────────┘
                       │
                     Merge
                       │
                       ▼
                     main
                       │
                       │ PR
                       ▼
                   release
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
            QA Plan          PROD Plan
              │                 │
              ▼                 ▼
          AI Review          AI Review
              │                 │
              └────────┬────────┘
                       │
                  Human Review
                       │
                       ▼
               Manual Dispatch
                       │
                 ┌─────┴─────┐
                 │           │
                 ▼           ▼
                QA          PROD
               Apply        Apply
```

---

# 15. Technologies Used

* **Terraform** — Infrastructure as Code
* **AWS** — Cloud infrastructure
* **Amazon S3** — Remote Terraform state
* **GitHub Actions** — CI/CD automation
* **GitHub Environments** — Environment-specific configuration and deployment controls
* **GitHub OIDC** — AWS authentication
* **Terraform CLI Workspaces** — Environment-specific state management
* **Python** — AI integration
* **Google Gemini API** — Terraform plan analysis
* **GitHub Pull Requests** — Infrastructure change review

---

# 16. Key Benefits

### Environment isolation

Each environment has a separate Terraform workspace and state.

### Automated validation

Terraform plans are generated automatically for Pull Requests.

### Controlled promotion

Infrastructure changes move through:

```text
Dev → QA → Prod
```

rather than being applied directly from feature branches.

### Reduced AWS credential management

GitHub OIDC provides temporary AWS credentials instead of long-lived access keys.

### AI-assisted review

Gemini provides an additional explanation and risk assessment of Terraform changes.

### Human control

AI provides recommendations, but infrastructure deployment remains controlled through the CI/CD workflow and manual release deployment process.

---

# Conclusion

This POC combines Terraform, GitHub Actions, AWS, and AI into a single infrastructure delivery workflow.

The core principle is:

```text
Git
 ↓
Terraform
 ↓
Plan
 ↓
AI Review
 ↓
Human Review
 ↓
Apply
```

Terraform remains responsible for determining the actual infrastructure changes, while AI provides an additional layer of explanation and risk analysis to help developers understand those changes before they are applied.
