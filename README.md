# OfficeMate AI

## Hybrid Work Allocation & Resource Management Agent

OfficeMate AI is an AI-powered workplace management platform designed to simplify hybrid work operations for employees and managers.

The system brings employee work schedules, tasks, attendance, parking, cafeteria resources and workplace information into a single application.

It also provides an AI assistant that uses Retrieval-Augmented Generation (RAG) and an LLM to answer workspace-related questions using available application data and policies.

---

## Problem Statement

Hybrid workplaces often manage work-from-office schedules, tasks, parking and workplace resources using spreadsheets, emails and chat messages.

This creates several problems:

- Employees have difficulty finding their current work schedule.
- Managers have limited visibility into team schedules.
- Task allocation and updates may be handled manually.
- Parking and cafeteria information can be difficult to track.
- Employees repeatedly ask managers for the same workplace information.

OfficeMate AI addresses these problems by providing a centralized workplace management platform with an AI assistant.

---

## Objectives

The main objectives of OfficeMate AI are:

1. Manage WFO, WFH and Hybrid work schedules.
2. Provide employees with their assigned tasks and workplace information.
3. Allow managers to assign and modify tasks.
4. Maintain workplace information in a centralized SQLite database.
5. Provide AI-assisted answers using RAG and LLM technologies.
6. Provide an OpenAPI specification for workplace-related services.
7. Display updated application data through the Streamlit interface.

---

## Key Features

### Employee Webpage

- Employee authentication
- Hybrid work schedule
- WFO/WFH information
- Assigned tasks
- Task status
- Attendance information
- Parking information
- Cafeteria information
- Schedule change request
- AI workplace assistant

### Manager Webpage

- Manager authentication
- Team directory
- Employee selection
- Task assignment
- Work mode assignment
- Task modification
- Task status management
- Due-date management
- Team information
- Workplace resource information

### AI Assistant

The AI assistant can answer questions related to:

- Work schedules
- Assigned tasks
- Task status
- Workplace policies
- Employee workspace information
- Resource information

The chatbot follows a RAG-based workflow:

User Question
       ↓
Chatbot Controller
       ↓
Retrieve Relevant Information
       ↓
RAG Layer
       ↓
LLM
       ↓
Generated Answer
       ↓
Streamlit Interface

---

## System Architecture

                    OfficeMate AI
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
      Home          Employee Portal   Manager Portal
        │                │                │
        │                ▼                ▼
        │          Employee Data      Team Data
        │                │                │
        │                └───────┬────────┘
        │                        ▼
        │                  SQLite Database
        │                        │
        └──────────────┬─────────┘
                       ▼
                AI Assistant
                       │
                       ▼
                 Chatbot Layer
                       │
                       ▼
                  RAG Retrieval
                       │
                       ▼
                      LLM
                       │
                       ▼
              Contextual AI Response

---

## Application Output & User Interface

OfficeMate AI provides separate interfaces for employees and managers through a Streamlit-based web application.

### 1. Landing Page

The landing page introduces OfficeMate AI as a hybrid work and workplace resource management platform.

It provides navigation to:

- Home
- Dashboard
- AI Chatbot
- Login / Signup

The landing page highlights the main capabilities of the system:

- Smart WFH/WFO allocation
- Workplace resource management
- Parking and cafeteria coordination
- RAG-powered AI assistant
- Employee and manager portals

### Landing Page Output

OfficeMate AI Home Page 

<img width="1907" height="695" alt="image" src="https://github.com/user-attachments/assets/883292db-8e1d-4fcd-81d9-685daddc89f1" />


---

### 2. Employee Dashboard

After employee authentication, the employee dashboard provides a personalized view of workplace information.

The dashboard displays:

- Employee name
- Today's work mode
- Assigned task count
- Attendance status
- Task status breakdown
- Weekly WFH/WFO distribution
- Personal workspace analytics

The dashboard is connected to application data so that employee information can be displayed based on the authenticated user.

### Employee Dashboard Output

OfficeMate AI Employee Dashboard 

<img width="1800" height="822" alt="image" src="https://github.com/user-attachments/assets/7a5e4c1f-802c-4f9a-bc97-2a0f4e8b0d99" />


---

### 3. Manager Dashboard

The manager dashboard provides workplace and team management capabilities.

Managers can:

- View team information
- Select employees
- Assign tasks
- Modify existing tasks
- Set work modes
- Update task status
- Manage due dates
- View team-related workplace information

Changes made by the manager are stored in the application database and can be reflected in the employee workflow.

### Manager Dashboard Output

OfficeMate AI Manager Dashboard 

<img width="1837" height="837" alt="image" src="https://github.com/user-attachments/assets/da277298-6655-41ff-8963-278b8aac9e31" />


---

### 4. AI Assistant

The OfficeMate AI Assistant allows authenticated users to ask workplace-related questions using natural language.

Example questions include:

What is my work mode today?

What are my assigned tasks?

What is the status of my task?

When is my next WFO day?

Which tasks are pending for my team?

Which employees are working from office?

AI Assistant Output
---

OfficeMate AI Chatbot

<img width="1852" height="777" alt="image" src="https://github.com/user-attachments/assets/a6aa5f0a-7504-4cd6-b38c-2f8a4443746d" />
 ```
