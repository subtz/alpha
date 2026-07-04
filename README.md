# SQMS: smartcard Queue Management System

A robust, enterprise-grade Django web application designed to optimize and streamline student queue processes. The system features secure user registration, email verification, interactive dashboards, real-time push notifications, custom analytics, and a Cloudinary storage integration for profile pictures suitable for zero-loss cloud deployments (such as Render's ephemeral filesystem).

---

## Table of Contents
1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Database Schema & Models](#2-database-schema--models)
3. [Core Feature Walkthrough](#3-core-feature-walkthrough)
   - [Queueing System & Concurrency Control](#queueing-system--concurrency-control)
   - [Web Push Notifications & VAPID Flow](#web-push-notifications--vapid-flow)
   - [Email Verification & Security Notices](#email-verification--security-notices)
   - [Cloudinary Media Storage Integration](#cloudinary-media-storage-integration)
4. [Environment Variables & Configuration](#4-environment-variables--configuration)
5. [Local Installation & Setup](#5-local-installation--setup)
6. [Render Deployment Guide](#6-render-deployment-guide)
7. [Testing and Verification Manual](#7-testing-and-verification-manual)

---

## 1. System Overview & Architecture

SQMS is built using **Django** and handles everything from user administration to real-time asynchronous push messaging. It uses a **Model-View-Template (MVT)** architecture with optimized service-worker integration to support offline fallbacks (PWA features).

```
                            +----------------------------------------+
                            |            Django Web App              |
                            +----+--------------------+----------+---+
                                 |                    |          |
                                 v                    v          v
                       +---------+-------+   +--------+---+   +--+--------+
                       |   SQLite /      |   | Cloudinary |   |  Web Push |
                       |   PostgreSQL    |   |   (Media)  |   |  Service  |
                       +-----------------+   +------------+   +-----------+
```

### Key Technical Aspects:
- **Database Concurrency:** Database-level locking (`select_for_update()`) inside atomic transactions prevents double-ticketing issues during high-load queue registration.
- **Asynchronous Service Worker:** A dedicated background service worker (`service-worker.js`) intercepting requests, offering caching, offline fallbacks, and handling background push events even when the tab is closed.
- **Robust Email System:** Outbound verification emails sent via SMTP with custom rate-limiting using local memory caches.

---

## 2. Database Schema & Models

Below is an overview of the core database entities defined in `calc/models.py`:

```
               +-------------------+
               |   ValidStudent    |
               +---------+---------+
                         | (1)
                         |
                         | (N)
               +---------v---------+          +--------------+
               |  StudentProfile   |--------->|     User     |
               +---------+---------+ (1)  (1) +------+-------+
                         |                           | (1)
                         |                           |
                         | (N)                       | (N)
               +---------v---------+          +------v--------------+
               |    QueueEntry     |          |  PushSubscription   |
               +---------+---------+          +---------------------+
                         | (N)
                         |
         +---------------+---------------+
         | (1)                           | (1)
+--------v---------+            +--------v---------+
|      Queue       |            |     Service      |
+------------------+            +------------------+
```

### Core Entities:
- **ValidStudent:** Holds pre-authorized registration numbers, names, and year constraints. Prevents malicious external users from creating arbitrary student accounts.
- **StudentProfile:** Extends the built-in Django `User` model, linking a valid student identity and holding their `profile_picture`.
- **Queue:** Configures max capacity, eligibility restrictions, auto-serve parameters, and current ticket tracking.
- **QueueEntry:** Represents a student's active status inside a queue (`waiting`, `serving`, `served`, `skipped`).
- **PushSubscription:** Stores endpoints, public keys (`p256dh`), and auth secrets required to send target Web Push notifications to a user's browser.
- **NotificationLog:** Comprehensive log of outbound notification attempts, tracking success/failure for audits.

---

## 3. Core Feature Walkthrough

### Queueing System & Concurrency Control
To prevent two students from grabbing the same ticket number under race conditions, the system uses a PostgreSQL/SQLite-compatible row lock:
```python
with transaction.atomic():
    queue_locked = Queue.objects.select_for_update().get(id=queue.id)
    next_position = queue_locked.current_ticket_number + 1
    queue_locked.current_ticket_number = next_position
    queue_locked.save()
    
    # Safely creates the ticket entry (e.g. SC-001)
```

### Web Push Notifications & VAPID Flow
1. **Subscription:** Upon login, the frontend service worker registers and requests a push subscription from the browser push service (Mozilla/Chrome).
2. **Key Exchange:** The browser returns a payload with an endpoint, `p256dh` key, and `auth` token, which is sent via POST to the Django backend and stored in the database.
3. **Notification dispatch:** When a student becomes "Next in line" or is being served, `pywebpush` is triggered:
```python
webpush(
    subscription_info=subscription_info,
    data=json.dumps({"title": "SQMS", "body": message_text, "url": url}),
    vapid_private_key=settings.VAPID_PRIVATE_KEY,
    vapid_claims={"sub": "mailto:admin@sqms.com"}
)
```

### Email Verification & Security Notices
Upon registering, accounts are set to `is_active=False`. A secure base64 token is generated and emailed. Additionally, whenever a new login or password change occurs, automated security alerts are fired to keep the account safe.

### Cloudinary Media Storage Integration
By configuring Django globally to use `MediaCloudinaryStorage`, file uploads dynamically post to Cloudinary. It retains identical clean logic in forms/views without requiring code restructuring:
- Allowed file size is limited to **2MB**.
- Accepted mime types are explicitly restricted to **JPEG** and **PNG**.

---

## 4. Environment Variables & Configuration

Create a `.env` file in the root directory (matching the structure below):

| Environment Variable | Description | Example / Default |
| --- | --- | --- |
| `SECRET_KEY` | Secret Django key for hash signature. | `your-django-secret-key` |
| `DEBUG` | Enable verbose error reporting locally. | `True` (Local) / `False` (Production) |
| `DATABASE_URL` | Connection URL (SQLite or Postgres). | `sqlite:///db.sqlite3` |
| `GROQ_API_KEY` | Key for automated queue insights helper. | `gsk_...` |
| `EMAIL_HOST_USER` | Sending Gmail address for SMTP emails. | `example@gmail.com` |
| `EMAIL_HOST_PASSWORD` | App-specific Gmail password. | `xxxx xxxx xxxx xxxx` |
| `VAPID_PUBLIC_KEY` | Public key for browser Push Notifications. | *Generated via VAPID scripts* |
| `VAPID_PRIVATE_KEY` | Private key for browser Push Notifications. | *Generated via VAPID scripts* |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary name for image hosting. | `your_cloud_name` |
| `CLOUDINARY_API_KEY` | Cloudinary integration key. | `your_api_key` |
| `CLOUDINARY_API_SECRET` | Cloudinary api secret token. | `your_api_secret` |

---

## 5. Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/subtz/alpha.git
   cd alpha
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Database and Load Mock Data:**
   ```bash
   python manage.py migrate
   python manage.py loaddata data.json
   ```

5. **Generate VAPID Keys for Local Push Testing (Optional):**
   ```bash
   python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('Public:', v.public_key.decode()); print('Private:', v.private_key.decode())"
   ```
   Add these printed outputs to your `.env` file for `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`.

6. **Start Local Development Server:**
   ```bash
   python manage.py runserver
   ```

---

## 6. Render Deployment Guide

Follow these steps to deploy SQMS successfully to Render's free tier with zero-loss storage:

### Step 1: Render Environment Setup
In your Render Dashboard, create a **Web Service** with the following details:
- **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- **Start Command:** `gunicorn alpha.wsgi:application`

### Step 2: Environment Variables Config
Under the **Environment** tab in Render, add the exact keys matching your `.env`:
- Set `DEBUG` to `False`
- Add `SECRET_KEY`
- Hook up a Render PostgreSQL Database and add its connection string as `DATABASE_URL`
- Configure `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`
- Input your `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `VAPID_PUBLIC_KEY`, and `VAPID_PRIVATE_KEY`

---

## 7. Testing and Verification Manual

### Local Verification of Cloudinary Uploads
To guarantee your uploads bypass local filesystems and successfully route to Cloudinary:
1. Ensure your `.env` has valid `CLOUDINARY_*` values.
2. Fire up the application (`python manage.py runserver`).
3. Log in as a registered student.
4. Access the **Dashboard**, go to profile settings, and upload a JPEG/PNG picture under 2MB.
5. Once saved, **right-click** on the image and click **Open Image in New Tab**.
6. **Verify the URL:** The domain must be `https://res.cloudinary.com/` (not local `127.0.0.1`).
7. **Cloudinary Console:** Log into Cloudinary, navigate to "Media Library", and confirm the file is saved within `profile_pictures/`.

### Checking Local SQLite vs Postgres Switching
Change the `DATABASE_URL` in `.env` to test Postgres databases locally. Execute:
```bash
python manage.py check
```
This validates database connectivity and model layouts without writing files.

---
Developed and optimized with robust cloud fail-safes. For assistance or reporting bugs, please raise an issue.
