# SQMS Project Report Draft

This draft is based only on repository evidence and uses source citations for each substantive claim.

## Abstract

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

## Acknowledgment

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

## Chapter 1: Introduction

### 1.1 Background

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 1.2 Problem Statement

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 1.3 Objectives

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 1.4 Research Questions

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 1.5 Significance

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 1.6 Scope

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

## Chapter 2: Literature Review

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

## Chapter 3: Methodology

### 3.1 SDLC Model

The repository history suggests an iterative and incremental development pattern rather than a single waterfall delivery, because the project evolved through repeated commits that added or refined queue handling, PWA support, push subscriptions, profile pictures, and deployment configuration (see [git log output] and [calc/views.py](calc/views.py), [calc/models.py](calc/models.py), [alpha/settings.py](alpha/settings.py)). Because no formal SDLC document is present in the repository, this should be reported as an inferred iterative/incremental approach rather than a formally documented methodology.

### 3.2 System Development Tools and Technologies

The system is implemented in Django 5.2.1 and uses Django authentication, SendGrid-backed email delivery, Cloudinary media storage, web push notification support, and PWA assets (see [requirements.txt](requirements.txt), [alpha/settings.py](alpha/settings.py), [calc/static/calc/manifest.json](calc/static/calc/manifest.json), [calc/static/calc/service-worker.js](calc/static/calc/service-worker.js)). The current email backend is explicitly set to `EMAIL_BACKEND = "sendgrid_backend.SendgridBackend"` in [alpha/settings.py](alpha/settings.py), with `SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")`. The Groq integration is implemented in the helper function `def call_groq_api(payload):` in [calc/utils.py](calc/utils.py), which posts to `https://api.groq.com/openai/v1/chat/completions` using `settings.GROQ_API_KEY`. The only call site found in the repository is `return JsonResponse(call_groq_api(payload))` inside `send_test_push` in [calc/views.py](calc/views.py). Based on the code, this is not used for push notifications; it is used for a Groq API request from a staff test endpoint, and no chatbot interface was found in the repository.

### 3.3 Requirements Analysis

#### 3.3.1 Functional Requirements

- The system supports student registration with validation of registration numbers and email verification before account activation (see [calc/views.py](calc/views.py), [calc/models.py](calc/models.py), and [templates/calc/register.html](templates/calc/register.html)).
- The system allows authenticated students to view available queues, join a queue, and receive queue status information after joining (see [calc/views.py](calc/views.py), [templates/calc/queue_list.html](templates/calc/queue_list.html), [templates/calc/notifications.html](templates/calc/notifications.html), and [templates/calc/dashboard.html](templates/calc/dashboard.html)).
- The system exposes AJAX polling endpoints for queue status updates: `student_queue_status` returns JSON for the logged-in student’s current position, ticket number, ETA, and serving status, while `queue_status_api` returns JSON for the current serving entry and waiting list of a specific queue; these endpoints are routed in [calc/urls.py](calc/urls.py) and used by [templates/calc/notifications.html](templates/calc/notifications.html) and [templates/calc/display.html](templates/calc/display.html).
- The system supports staff queue control actions such as serving the next student, skipping the current student, pausing or resuming a queue, and enabling or configuring automatic serving (see [calc/views.py](calc/views.py), [templates/calc/admin_queue_dashboard.html](templates/calc/admin_queue_dashboard.html), and [templates/calc/staff_dashboard_home.html](templates/calc/staff_dashboard_home.html)).
- The system provides analytics and reporting for served, waiting, and skipped queue entries, including PDF export for staff reports (see [calc/views.py](calc/views.py), [templates/calc/analytics_dashboard.html](templates/calc/analytics_dashboard.html), and [templates/calc/staff_reports.html](templates/calc/staff_reports.html)).
- The system includes push notifications and a PWA flow for browser-based notification delivery and offline-friendly assets (see [calc/views.py](calc/views.py), [calc/static/calc/service-worker.js](calc/static/calc/service-worker.js), [calc/static/calc/manifest.json](calc/static/calc/manifest.json), and [templates/calc/notifications.html](templates/calc/notifications.html)).
- The system supports upload of student profile pictures through a form that validates file size and MIME type before saving to the configured media storage backend (see [calc/views.py](calc/views.py) and [templates/calc/dashboard.html](templates/calc/dashboard.html)).

#### 3.3.2 Non-Functional Requirements

- The queueing workflow uses database transactions and row-level locking with select_for_update() to reduce race conditions when ticket numbers and queue entries are created or advanced (see [calc/views.py](calc/views.py)).
- The application uses Django authentication and role-based access control through login_required and staff_member_required decorators so that students, staff, and administrators access different parts of the system (see [calc/views.py](calc/views.py) and [calc/urls.py](calc/urls.py)).
- The system includes email verification, password reset flows, and security email notifications to strengthen account security (see [calc/views.py](calc/views.py), [templates/calc/password_reset_form.html](templates/calc/password_reset_form.html), and [templates/calc/verify_email_sent.html](templates/calc/verify_email_sent.html)).
- The deployment configuration uses environment variables for secrets, database settings, email credentials, Cloudinary configuration, and VAPID keys, which supports configuration-based deployment across local and cloud environments (see [alpha/settings.py](alpha/settings.py)).
- The project uses Cloudinary-backed media storage and Whitenoise for static files so that uploaded media and static assets are handled in a deployment-friendly way (see [alpha/settings.py](alpha/settings.py) and [requirements.txt](requirements.txt)).

### 3.4 UML Diagrams

The repository contains the data entities and application flows needed to create the following diagrams accurately.

- Use case diagram: the actors should include Student, Staff, and Administrator; the main use cases should include account registration, login, password reset, profile picture upload, queue browsing and joining, queue status monitoring, queue control actions, analytics viewing, reporting, and push notification subscription (see [calc/urls.py](calc/urls.py), [calc/views.py](calc/views.py), and [templates/calc](templates/calc)).
- Class diagram: the core classes should include ValidStudent, StudentProfile, Queue, Customer, Service, QueueEntry, PushSubscription, NotificationLog, and the built-in Django User model; the important relationships are one-to-one between User and StudentProfile, many-to-one between QueueEntry and Queue/Customer/Service, and one-to-many relationships from User to PushSubscription and NotificationLog (see [calc/models.py](calc/models.py)).
- Sequence diagram: the main flow should show a Student joining a queue, the application creating a QueueEntry and assigning a ticket number, the staff advancing the queue, and the system sending notification messages to the relevant student(s) (see [calc/views.py](calc/views.py), [calc/tests.py](calc/tests.py), and [templates/calc/notifications.html](templates/calc/notifications.html)).
- Activity diagram: the process should show the queue lifecycle from creation and activation through waiting, serving, skipping, completion, and optional auto-mode transitions, including the branching conditions for pauses and auto-serve intervals (see [calc/models.py](calc/models.py) and [calc/views.py](calc/views.py)).

## Chapter 4: Results and Discussion

### 4.1 Database Design

The database design is centered on queue operations and user-account linkage. The main entities are as follows (see [calc/models.py](calc/models.py)).

- ValidStudent stores pre-authorized registration numbers, full names, year-of-study values, and status flags, and is used to validate student registration before an account is created (see [calc/models.py](calc/models.py)).
- StudentProfile links a Django User to a ValidStudent, stores a profile picture, and is the main student-specific profile object used by the dashboard and profile upload workflow (see [calc/models.py](calc/models.py)).
- Queue stores queue configuration data such as name, description, allowed years, active/paused status, capacity, current ticket number, auto-mode settings, and timestamps (see [calc/models.py](calc/models.py)).
- Customer stores the customer identity used for queue participation and is linked to an email address that is also used to identify the Django user account (see [calc/models.py](calc/models.py)).
- Service stores service definitions such as name, description, estimated time, and activity status, and is referenced by each queue entry (see [calc/models.py](calc/models.py)).
- QueueEntry is the core transaction entity that links a Queue, a Customer, and a Service; it records position, ticket number, status, timestamps, and notes (see [calc/models.py](calc/models.py)).
- PushSubscription stores browser push subscription data for a user, including endpoint, p256dh key, and auth key, and is used to send notifications to students (see [calc/models.py](calc/models.py)).
- NotificationLog records the outcome of notification attempts, including success/failure state, message content, and error detail (see [calc/models.py](calc/models.py)).

### 4.2 Implemented Interfaces by Role

#### 4.2.1 Student Interface

The student-facing interface is implemented through the dashboard, queue list, notifications page, and profile-picture upload views (see [templates/calc/dashboard.html](templates/calc/dashboard.html), [templates/calc/queue_list.html](templates/calc/queue_list.html), [templates/calc/notifications.html](templates/calc/notifications.html), and [templates/calc/profile_picture_upload.html](templates/calc/profile_picture_upload.html)). Students can register, verify their email, log in, view their current queue status, join a queue, and update their profile picture from these interfaces (see [calc/views.py](calc/views.py)).

#### 4.2.2 Staff Interface

The staff-facing interface is implemented through the staff dashboard, queue control page, analytics dashboard, and reports page (see [templates/calc/staff_dashboard_home.html](templates/calc/staff_dashboard_home.html), [templates/calc/admin_queue_dashboard.html](templates/calc/admin_queue_dashboard.html), [templates/calc/analytics_dashboard.html](templates/calc/analytics_dashboard.html), and [templates/calc/staff_reports.html](templates/calc/staff_reports.html)). Staff users can open a specific queue, view the currently serving student and waiting list, advance or skip students, pause or resume the queue, and review analytics and reports (see [calc/views.py](calc/views.py)).

#### 4.2.3 Admin Interface

The project exposes a Django admin interface through the standard admin route and registers the main queue-management models for administrative management (see [alpha/urls.py](alpha/urls.py) and [calc/admin.py](calc/admin.py)). The admin interface is therefore the built-in Django administration layer for Queue, Customer, Service, QueueEntry, ValidStudent, StudentProfile, and PushSubscription records.

#### 4.2.4 Display Interface

A display-oriented interface is implemented for a live queue screen that shows the currently serving ticket and the waiting list (see [templates/calc/display.html](templates/calc/display.html) and [calc/views.py](calc/views.py)). The corresponding view selects an active queue and passes the current serving entry and waiting entries to the template for display.

### 4.3 System Testing

Automated tests are present in [calc/tests.py](calc/tests.py) and cover notification-related and queue-advancement behavior. The existing tests validate push-subscription model persistence, push-subscription endpoint handling, successful and failing notification delivery, and the queue-advance workflow that updates statuses and creates notification logs (see [calc/tests.py](calc/tests.py)). No automated tests were found in the repository for registration, password reset, queue joining, analytics filtering, or PDF export workflows, so that remains a gap for future validation.

## Chapter 5: Conclusion, Recommendations and Limitations

### 5.1 Conclusion

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 5.2 Recommendations

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

### 5.3 Limitations

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]

## References

[PLACEHOLDER — NOT DERIVABLE FROM CODEBASE, FILL MANUALLY]
