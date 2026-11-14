# AI Usage Disclosure & Prompt History

Project: WorkSync AI — Intelligent Workforce Scheduling & Leave Management System

## 1. How I Used AI
I used Large Language Models (LLMs) as development assistants throughout the project to accelerate architecture exploration, implementation, debugging, synthetic-data design, and UI/UX refinement. AI supported my development workflow, but I remained responsible for reviewing the implementation, making technical decisions, and validating the final application.

I treated AI output as a draft to be inspected, tested, and adapted — not as an authority. Where generated suggestions or code did not align with the project’s three-tier architecture, data model, or business rules, I changed or rejected them.

## 2. Prompt History
The following are representative prompts used during this work:

1. "Design an end-to-end workforce scheduling and leave management system with a strict three-tier architecture, role-based dashboards, traceable scheduling decisions, and separate presentation, application and data tiers."
2. "Model employees, teams, skills, shift templates, dated shifts, assignments, leave requests, holidays, attendance, coverage requirements and shift swaps with primary keys, foreign keys, bridge tables, effective dates, lifecycle states and preserved history."
3. "Generate a reproducible workforce dataset with 2,000 employees, 100 teams, 90 days of shifts and 5,000 leave requests using deterministic IDs, fixed seed 20261022, valid parent-child references, realistic distributions and parameterised starter/full scales."
4. "Implement an OR-Tools CP-SAT scheduler that respects approved leave, overlapping shifts, skills, team eligibility, availability, minimum rest, weekly hour caps, overtime limits and coverage requirements, and returns labelled partial plans with explicit gaps when infeasible."
5. "Record, for every generated assignment, the employee, shift, assignment reason, skill match, availability result, leave eligibility, constraint evaluation, optimization score and scheduling timestamp so a manager can understand the decision."
6. "Implement leave lifecycle PENDING → APPROVED / REJECTED / CANCELLED and swap lifecycle REQUESTED → APPROVED / REJECTED / CANCELLED → APPLIED with target agreement, manager approval, skill/rest/hour validation, and append-only approval history."
7. "Derive attendance status, actual hours and overtime from check-in/check-out records and shift assignments; never generate overtime independently of attendance; reconcile attendance against the active assignment."
8. "Inject labelled edge cases for employee double-booking, approved leave overlapping an assignment, missing required skills, overtime-cap breaches and swaps applied without approval, while keeping ground truth separate from operational inputs."
9. "Redesign the application as a modern enterprise workforce dashboard with role-aware navigation, KPI cards, a weekly shift calendar, leave/swap workflows, conflict management, interactive analytics and a professional visual system."
10. "Analyze frontend build and backend integration issues — static asset serving, API proxy/CORS, SQLAlchemy response serialization, lifecycle history errors, assignment uniqueness during regeneration and dataset seeding — and provide fixes preserving existing behaviour."
11. "Produce architecture, ER diagram, data dictionary, business rules, validation summary, detector evaluation, reproducibility report, source manifest and setup documentation with measurable, verifiable results."
12. "Run the full generator twice with the same seed and compare row counts and SHA-256 checksums for every exported CSV, JSON, ground-truth, manifest and validation file."

## 3. Where AI Accelerated My Work
AI significantly accelerated:

- Exploring the three-tier architecture and service boundaries.
- Structuring the relational model and identifying entity relationships/cardinality.
- Designing the deterministic synthetic-data pipeline and anomaly injector.
- Drafting the CP-SAT constraint model and objective structure.
- Implementing leave, swap, attendance, overtime, and conflict workflows.
- Improving dashboard layouts, navigation, and visual consistency.
- Troubleshooting build, API-proxy, serialization, and runtime issues.
- Preparing technical documentation, evaluation reports, and reproducibility evidence.

## 4. Where I Relied Heavily on AI
I relied more heavily on AI for:

- Generating initial implementation approaches and code structures.
- UI/UX design recommendations and frontend refinement.
- Debugging unfamiliar or environment-specific errors.
- Suggesting validation strategies and anomaly scenarios.
- Drafting long-form technical documentation.
- Reviewing project configuration and startup requirements for running the application locally.

AI suggestions and code were treated as development assistance rather than automatically accepted as correct.

## 5. What I Personally Reviewed, Changed and Validated
I maintained responsibility for the final implementation by:

- Reviewing generated code and adapting it to the project’s architecture.
- Checking entity relationships, primary keys, foreign keys, cardinality, and identifier consistency.
- Reviewing business rules for leave, swaps, attendance, overtime, coverage, and scheduling constraints.
- Checking that anomaly labels and ground-truth files are separate from operational data and are not read by the detector or scheduler.
- Reviewing frontend build and runtime behavior, including accessibility and usability.
- Running the application locally and troubleshooting startup, health-check, and authentication issues.
- Verifying that approved leave blocks assignment, unapproved swaps cannot be applied through normal workflows, and scheduling decisions are explainable.
- Reviewing validation evidence: local runtime checks, health endpoint responses, login flow, and successful access to the dashboard.
- Confirming the app is currently operational in this environment.

## 6. Personal Contribution and Accountability
AI helped accelerate development, but this project required my involvement in understanding workforce scheduling and leave-management workflows, integrating the three tiers, evaluating implementation choices, reviewing data integrity, and testing the application.

I take responsibility for the final submitted implementation and acknowledge that AI-generated outputs require independent technical review and validation. Any limitations documented in the project — including local environment differences and Docker availability in this session — remain my responsibility to disclose and address.

Conclusion: I used AI as a productivity and problem-solving tool while maintaining responsibility for the project’s architecture, integration, functionality, and final quality.

## 7. Session-Specific Activity for This Run
For this current session, the work was focused on hosting and validating the application locally. My actual actions were:

- Reviewed project configuration files and startup expectations.
- Confirmed the application is designed to run as a FastAPI backend + Vite frontend.
- Identified that Docker Compose was not available in this environment.
- Installed Python dependencies from backend/requirements.txt.
- Installed frontend dependencies from frontend/package.json.
- Started the backend locally on port 8000.
- Started the frontend locally on port 3000.
- Verified API health via http://localhost:8000/api/health.
- Opened the browser to validate the app UI.
- Confirmed the login page rendered correctly.
- Used the demo admin credentials and successfully accessed the dashboard.
- Confirmed the application is running and usable.

This run did not require code modification. The key work was environment startup and runtime verification, which was accelerated by AI-assisted review of the project configuration and startup model.
