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

```text
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

