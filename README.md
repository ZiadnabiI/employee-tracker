<p align="center">
  <img src="LOGO.jpeg" alt="Employee Tracker Logo" width="200"/>
</p>

<h1 align="center">Employee Tracker</h1>

<p align="center">
  <strong>AI-Powered Employee Presence Monitoring — Built for Remote Teams</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#api-reference">API Reference</a> •
  <a href="#deployment">Deployment</a> •
  <a href="#pricing">Pricing</a> •
  <a href="#privacy">Privacy</a>
</p>

---

## 🚀 What is Employee Tracker?

Employee Tracker is a **SaaS platform** that uses AI-powered camera detection to monitor employee presence in real time. Supervisors get a web dashboard to track who's working, who's away, view activity logs, capture on-demand screenshots, and monitor application usage — all from one place.

Unlike traditional monitoring tools that just track mouse and keyboard input, Employee Tracker uses **YOLOv8 computer vision** to detect whether an employee is actually present at their workstation.

---

## ✨ Features

### 🖥️ Supervisor Dashboard
- **Real-time presence monitoring** — See who's present and who's away at a glance
- **Activity timeline** — Full log of work starts, breaks, and departures
- **On-demand screenshots** — Request a screenshot from any employee's machine
- **App usage tracking** — See which applications employees are using and for how long
- **Employee detail views** — Drill into individual employee activity

### 🤖 AI Desktop Agent (Windows)
- **Camera-based presence detection** using YOLOv8 (person detection)
- **Automatic heartbeat** — Sends presence status every 5 seconds
- **Away detection** — Automatically detects when employee leaves their desk (>10 seconds)
- **Screenshot capture** — Responds to supervisor screenshot requests
- **App monitoring** — Reports active application and window title
- **One-click Windows installer** via Inno Setup

### 🏢 Multi-Tenant SaaS
- **Company isolation** — Each organization's data is fully separated
- **Role-based access** — Owner, Admin, and Viewer roles for supervisors
- **Subscription billing** via Stripe (Free, Pro, Enterprise plans)
- **Employee invitation system** with activation keys and hardware binding
- **Department management** for organizing teams

### 🔔 Integrations
- **Slack notifications** for important events
- **Stripe** for subscription management and payments
- **PostgreSQL** for production data storage

---

## 🔧 How It Works

```
┌─────────────────┐         ┌──────────────────────┐         ┌──────────────┐
│  Desktop Agent   │ ──API──▶│   FastAPI Backend     │◀──Web──│  Supervisor   │
│  (Windows App)   │         │   (Render Cloud)      │         │  Dashboard    │
│                  │         │                        │         │              │
│ • YOLOv8 Camera  │         │ • Auth & Multi-tenant  │         │ • Real-time  │
│ • Heartbeat      │         │ • Activity Logging     │         │ • Logs       │
│ • Screenshots    │         │ • Stripe Billing       │         │ • Screenshots│
│ • App Tracking   │         │ • PostgreSQL           │         │ • App Usage  │
└─────────────────┘         └──────────────────────┘         └──────────────┘
```

1. **Employee installs** the desktop agent and activates with a unique key
2. **Agent detects presence** via webcam using YOLOv8 person detection
3. **Heartbeats are sent** every 5 seconds to the cloud backend
4. **Supervisors monitor** everything from the real-time web dashboard

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, Uvicorn |
| **Database** | PostgreSQL (production), SQLite (local dev) |
| **ORM** | SQLAlchemy |
| **Frontend** | HTML, CSS, Jinja2 Templates |
| **AI/ML** | YOLOv8 (Ultralytics) for person detection |
| **Payments** | Stripe (Subscriptions + Webhooks) |
| **Notifications** | Slack Webhooks |
| **Deployment** | Render (render.yaml) |
| **Desktop Installer** | PyInstaller + Inno Setup |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL (or use SQLite for local development)
- Stripe account (for billing features)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ZiadnabiI/employee-tracker.git
   cd employee-tracker
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables:**
   ```bash
   export DATABASE_URL="postgresql://user:password@host:5432/employee_tracker"
   export SECRET_KEY="your-secure-secret-key"
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
   export STRIPE_SECRET_KEY="sk_..."
   export STRIPE_WEBHOOK_SECRET="whsec_..."
   ```

4. **Run the server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Open your browser:**
   ```
   http://localhost:8000
   ```

### Setting Up the Desktop Agent

See the [Installer README](installer/README.md) for building the Windows desktop client.

---

## 📡 API Reference

### POST Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /admin/create-employee` | Create a new employee with an activation key |
| `POST /activate-device` | Bind a hardware ID to an activation key |
| `POST /verify-checkin` | Verify an activation key is valid and active |
| `POST /log-activity` | Log presence, breaks, and work status |

### GET Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /check-status/{activation_key}` | Check if an employee is active |
| `GET /dashboard/stats` | Get real-time dashboard statistics |
| `GET /` | Serve the web dashboard |

> 📄 Full API documentation is available in [`api_endpoints.txt`](api_endpoints.txt)

---

## ☁️ Deployment

### Deploy to Render

This project includes a `render.yaml` for one-click deployment:

1. Connect your GitHub repo to [Render](https://render.com)
2. Create a new **Web Service** from the repo
3. Set environment variables (`DATABASE_URL`, `SECRET_KEY`, etc.)
4. Deploy!

### Deploy with Procfile (Heroku-compatible)

```bash
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## 💰 Pricing

| Plan | Employees | Screenshot Frequency | Price |
|------|-----------|---------------------|-------|
| **Free** | Up to 5 | Every 10 minutes | $0/mo |
| **Pro** | Up to 50 | Every 5 minutes | Custom |
| **Enterprise** | Unlimited | Real-time | Custom |

Billing is handled via Stripe with automatic subscription management.

---

## 🔒 Privacy

Employee Tracker takes privacy seriously:

- Camera data is processed **locally on the employee's machine** — only presence status (Present/Away) is sent to the server
- Screenshots are only taken when **explicitly requested** by a supervisor or at configurable intervals
- All data is isolated per company (multi-tenant architecture)
- A full [Privacy Policy](templates/privacy.html) is included

> ⚠️ **Important:** Ensure compliance with local labor laws and privacy regulations (GDPR, CCPA, etc.) before deploying in your organization. Employee consent should be obtained before use.

---

## 📁 Project Structure

```
employee-tracker/
├── main.py                 # FastAPI application (routes, logic, webhooks)
├── auth.py                 # Authentication module (tokens, password hashing)
├── database.py             # SQLAlchemy models and database config
├── requirements.txt        # Python dependencies
├── Procfile                # Deployment process file
├── render.yaml             # Render deployment config
├── api_endpoints.txt       # API documentation
├── setup_admin.py          # Admin user setup script
├── templates/              # Jinja2 HTML templates
│   ├── landing.html        # Marketing landing page
│   ├── login.html          # Login page
│   ├── register.html       # Registration page
│   ├── dashboard_new.html  # Main supervisor dashboard
│   ├── employee_detail.html# Employee detail view
│   ├── pricing.html        # Pricing page
│   └── privacy.html        # Privacy policy
├── app/                    # Desktop agent
│   └── detector.py         # YOLOv8 camera detection client
├── installer/              # Windows installer
│   ├── installer.iss       # Inno Setup script
│   ├── build_installer.bat # Build automation
│   └── enable_camera.ps1   # Camera permissions helper
├── migrations/             # Database migration scripts
├── static/                 # Static assets (CSS, images)
└── docs/                   # Documentation
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

This project is proprietary software. All rights reserved.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/ZiadnabiI">Ziad Nabil</a>
</p>
