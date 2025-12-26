 
# Micro Learning System

A microservices-based learning platform that transforms long courses into 5-minute micro-lessons.

## Architecture

- **User Service**: User authentication and management (FastAPI + PostgreSQL)
- **Content Service**: Course content management and transformation (FastAPI + MongoDB)
- **Notification Service**: Event-driven notifications (To be implemented)
- **Analytics Service**: Learning progress tracking (To be implemented)

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Git

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd micro-learning-system