# Vacation Management System

## Overview
The Vacation Management System is a full-stack web application built using Flask, SQLite, HTML, and CSS. It is designed to manage employee vacation requests within an organization using a role-based access control system.

The application supports multiple user roles such as Employee, HR, Department Head, and Admin, each with different permissions and dashboards.

---

## Features

### User Management
- User registration and login system
- Role-based access control (Employee, HR, Department Head, Admin)
- Secure password hashing using Werkzeug

### Vacation Workflow
- Employees can submit vacation requests
- Managers/HR can review, approve, or reject requests
- Department-level tracking of vacation balances
- Status updates for each request (Pending, Approved, Rejected)

### Dashboards
- Separate dashboards for each user role
- Role-specific views and permissions
- Organized request management interface

---

## Tech Stack

- **Backend:** Python (Flask)
- **Database:** SQLite (SQLAlchemy ORM)
- **Frontend:** HTML, CSS
- **Authentication:** Flask-Login
- **Security:** Werkzeug password hashing

---

## Project Structure
