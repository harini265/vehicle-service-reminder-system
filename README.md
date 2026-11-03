# Roadwise — Vehicle Service Reminder System

A small, deployable vehicle maintenance tracker. Keep vehicle details, odometer readings, service dates, and upcoming reminders in one place. The web app ships with optional demo records on first launch.

## Run locally with Docker

Requirements: Docker Desktop with Compose.

```sh
docker compose up --build
```

Open the app at <http://localhost:5000>, Prometheus at <http://localhost:9090>, and Grafana at <http://localhost:3000> (user `admin`, password `roadwise-local`). Set `GRAFANA_PASSWORD` in your environment before starting Compose to change the local Grafana password. Data persists in named Docker volumes.

To run the Flask app without Docker, use Python 3.12+: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python app/app.py`. The SQLite database is stored at `./data/vehicles.db` when run directly (create `data/` first or set `DATABASE_PATH`).

## Features

- Add and track vehicles with nickname, make, model, year, plate, and odometer.
- Schedule maintenance with last service date, due date, due mileage, and notes.
- See upcoming and overdue service at a glance, then mark a service complete.
- Lightweight SQLite persistence and health endpoint (`/health`).
- Prometheus application metrics (`/metrics`) and a provisioned Grafana dashboard.

## Deployment flow

```text
Code (Git/GitHub) → Provision (Terraform) → Config (Ansible) → Build/Deploy (Docker + Jenkins) → Monitor (Grafana)
```

1. **Git/GitHub:** Commit this repository and push to GitHub. Jenkins checks out the connected repository.
2. **Terraform:** In `infra/terraform`, copy `terraform.tfvars.example` to `terraform.tfvars`, set your AWS key pair and your public IP CIDR, then run `terraform init`, `terraform plan`, and `terraform apply`. This provisions a small Ubuntu EC2 host and outputs its public IP. Set a real image name published to a registry in `app_image`. `terraform destroy` removes the demo infrastructure.
3. **Ansible:** Update `infra/ansible/inventory.ini.example` with the EC2 address and key, then run `ansible-galaxy collection install community.docker` and `ansible-playbook -i infra/ansible/inventory.ini infra/ansible/site.yml`. Set `APP_IMAGE` to the published image if needed. The playbook configures Docker and starts the app. The supplied Terraform user-data also installs Docker for a quick bootstrap; Ansible applies the repeatable host configuration.
4. **Docker + Jenkins:** Create a Jenkins Pipeline from this repo and configure credentials `dockerhub` (Docker Hub username/password) and `deploy-ssh` (SSH private key). Set `DOCKERHUB_USERNAME`, `DEPLOY_USER`, and `DEPLOY_HOST` as Jenkins environment/job variables. The pipeline builds each commit; on `main`, it publishes the tagged image and deploys to `/opt/roadwise` on the host. For a first deployment, provision with `app_image` set to the same registry image Jenkins will push.
5. **Grafana:** In the Compose deployment, Prometheus scrapes the app's `/metrics` endpoint; Grafana is provisioned with the Prometheus data source and Roadwise dashboard. Open Grafana at port 3000 and select **Roadwise Application Overview**.

### Terraform security note

The sample opens the app port 5000 publicly to make a student demo easy to reach. Restrict the ingress CIDR or put a TLS reverse proxy/load balancer in front before using it for real users. Keep SSH ingress limited to your own IP, and replace all sample credentials.

## Repository map

- `app/` — Flask web app, API, and responsive dashboard UI.
- `Dockerfile`, `docker-compose.yml` — container build and local stack.
- `Jenkinsfile` — CI build, registry publish, and host deploy pipeline.
- `infra/terraform/` — AWS EC2 provisioning.
- `infra/ansible/` — Docker host configuration and app deployment.
- `monitoring/` — Prometheus scrape config and Grafana provisioning/dashboard.
