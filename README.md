# IoT Environmental Data Platform

A production-style backend API for ingesting, storing, and retrieving environmental sensor data from an IoT device (**Raspberry Pi Pico W + BME688**).

This project simulates a real-world telemetry ingestion system, designed with scalability and clean architecture in mind.

## 🚀 Project Overview

This system collects environmental data every 30 seconds from a microcontroller and stores it in a relational database via a REST API.

### Captured Metrics:
* **Temperature** (°C)
* **Humidity** (%)
* **Pressure** (Pa)
* **Gas Resistance** (Ohms)
* **Timestamp** (Server-generated)
* **Reboot Flag** (Device state tracking)

### Backend Goals:
* **High Availability:** Handle continuous telemetry ingestion.
* **Performance:** Provide pagination for large datasets to prevent memory overload.
* **Extensibility:** Support future ETL pipelines and dashboard integrations (like Grafana).
* **Data Integrity:** Validated schemas using Pydantic.

---

## 🏗 Architecture

The system follows a linear data flow to ensure low latency and clear separation of concerns:



**IoT Device** → **FastAPI API** → **SQLAlchemy ORM** → **PostgreSQL Database**

### Key Design Decisions:
* **Server-side Timestamps:** Prevents data collisions if the IoT device loses its RTC sync.
* **Nullable Gas Field:** Accommodates sensors that only send gas resistance periodically due to burn-in requirements.
* **Service Layer Pattern:** Separation of routes, services, and models for easier testing.

---

## 🛠 Tech Stack

* **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
* **ORM:** [SQLAlchemy](https://www.sqlalchemy.org/)
* **Database:** PostgreSQL (Production) / SQLite (Local Dev)
* **Validation:** Pydantic
* **Server:** Uvicorn
* **Deployment:** Render / Docker

---

## 📦 Database Schema: `sensor_readings`

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | Integer | Primary Key (Auto-increment) |
| `timestamp` | DateTime | Server generated (UTC) |
| `temperature` | Float | Measured in Celsius |
| `humidity` | Float | Relative Humidity % |
| `pressure` | Integer | Measured in Pascals |
| `gas_resistance` | Integer | Nullable (Sensor warm-up) |
| `reboot_flag` | String | Tracks device resets |

---

## 🔌 API Endpoints

### Data Ingestion
* `POST /readings/` - Create a new sensor reading.

### Data Retrieval
* `GET /readings/` - Get all readings (Paginated).
    * *Params:* `skip` (default 0), `limit` (default 100).
* `GET /readings/latest` - Get the most recent sensor entry.
* `GET /readings/{id}` - Get a specific reading by ID.

### Management
* `DELETE /readings/{id}` - Remove a specific record.

---

## 🛠 Installation & Setup
To be added
