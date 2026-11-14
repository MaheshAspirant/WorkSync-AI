-- WorkSync AI PostgreSQL schema
-- Generated from the SQLAlchemy metadata; use Alembic for upgrades.

CREATE TABLE holiday_calendar (
	holiday_id VARCHAR(16) NOT NULL, 
	holiday_date DATE NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	region VARCHAR(20) NOT NULL, 
	is_paid BOOLEAN NOT NULL, 
	is_recurring BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_holiday_calendar PRIMARY KEY (holiday_id), 
	CONSTRAINT uq_holiday_date_region UNIQUE (holiday_date, region)
);
CREATE INDEX ix_holiday_calendar_holiday_date ON holiday_calendar (holiday_date);

CREATE TABLE id_counters (
	counter_key VARCHAR(40) NOT NULL, 
	next_value INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_id_counters PRIMARY KEY (counter_key)
);

CREATE TABLE leave_policies (
	policy_id VARCHAR(16) NOT NULL, 
	leave_type VARCHAR(30) NOT NULL, 
	annual_entitlement_days FLOAT NOT NULL, 
	max_consecutive_days INTEGER NOT NULL, 
	requires_document_after_days INTEGER, 
	is_paid BOOLEAN NOT NULL, 
	min_notice_days INTEGER NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_leave_policies PRIMARY KEY (policy_id), 
	CONSTRAINT uq_leave_policies_leave_type UNIQUE (leave_type)
);

CREATE TABLE roles (
	role_id VARCHAR(16) NOT NULL, 
	name VARCHAR(30) NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	permissions JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_roles PRIMARY KEY (role_id), 
	CONSTRAINT uq_roles_name UNIQUE (name)
);

CREATE TABLE shift_templates (
	shift_template_id VARCHAR(16) NOT NULL, 
	code VARCHAR(8) NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	start_time TIME WITHOUT TIME ZONE NOT NULL, 
	end_time TIME WITHOUT TIME ZONE NOT NULL, 
	duration_hours FLOAT NOT NULL, 
	crosses_midnight BOOLEAN NOT NULL, 
	color VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_shift_templates PRIMARY KEY (shift_template_id), 
	CONSTRAINT uq_shift_templates_code UNIQUE (code)
);

CREATE TABLE skills (
	skill_id VARCHAR(16) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	description TEXT, 
	is_critical BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_skills PRIMARY KEY (skill_id), 
	CONSTRAINT uq_skills_name UNIQUE (name)
);
CREATE INDEX ix_skills_category ON skills (category);

CREATE TABLE teams (
	team_id VARCHAR(16) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	department VARCHAR(60) NOT NULL, 
	site VARCHAR(80) NOT NULL, 
	cost_center VARCHAR(30), 
	timezone VARCHAR(60) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_teams PRIMARY KEY (team_id), 
	CONSTRAINT uq_teams_name UNIQUE (name)
);
CREATE INDEX ix_teams_department ON teams (department);

CREATE TABLE coverage_requirements (
	coverage_id VARCHAR(16) NOT NULL, 
	team_id VARCHAR(16) NOT NULL, 
	shift_template_id VARCHAR(16) NOT NULL, 
	skill_id VARCHAR(16), 
	day_type VARCHAR(20) NOT NULL, 
	min_staff INTEGER NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_coverage_requirements PRIMARY KEY (coverage_id), 
	CONSTRAINT uq_coverage_version UNIQUE (team_id, shift_template_id, day_type, effective_from, skill_id), 
	CONSTRAINT fk_coverage_requirements_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (team_id), 
	CONSTRAINT fk_coverage_requirements_shift_template_id_shift_templates FOREIGN KEY(shift_template_id) REFERENCES shift_templates (shift_template_id), 
	CONSTRAINT fk_coverage_requirements_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (skill_id)
);
CREATE INDEX ix_coverage_requirements_shift_template_id ON coverage_requirements (shift_template_id);
CREATE INDEX ix_coverage_requirements_team_id ON coverage_requirements (team_id);
CREATE INDEX ix_coverage_requirements_skill_id ON coverage_requirements (skill_id);

CREATE TABLE employees (
	employee_id VARCHAR(16) NOT NULL, 
	team_id VARCHAR(16) NOT NULL, 
	first_name VARCHAR(60) NOT NULL, 
	last_name VARCHAR(60) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	phone VARCHAR(30), 
	job_title VARCHAR(80) NOT NULL, 
	employment_type VARCHAR(40) NOT NULL, 
	hire_date DATE NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	weekly_hours_cap FLOAT NOT NULL, 
	daily_hours_cap FLOAT NOT NULL, 
	overtime_cap_weekly FLOAT NOT NULL, 
	min_rest_hours FLOAT NOT NULL, 
	preferred_shift VARCHAR(20) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_employees PRIMARY KEY (employee_id), 
	CONSTRAINT fk_employees_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (team_id)
);
CREATE UNIQUE INDEX ix_employees_email ON employees (email);
CREATE INDEX ix_employees_team_id ON employees (team_id);
CREATE INDEX ix_employees_status ON employees (status);

CREATE TABLE shifts (
	shift_id VARCHAR(40) NOT NULL, 
	shift_date DATE NOT NULL, 
	shift_template_id VARCHAR(16) NOT NULL, 
	team_id VARCHAR(16) NOT NULL, 
	start_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	end_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	required_staff INTEGER NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_shifts PRIMARY KEY (shift_id), 
	CONSTRAINT uq_shift_team_date_template UNIQUE (team_id, shift_date, shift_template_id), 
	CONSTRAINT fk_shifts_shift_template_id_shift_templates FOREIGN KEY(shift_template_id) REFERENCES shift_templates (shift_template_id), 
	CONSTRAINT fk_shifts_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (team_id)
);
CREATE INDEX ix_shifts_shift_template_id ON shifts (shift_template_id);
CREATE INDEX ix_shifts_start_at ON shifts (start_at);
CREATE INDEX ix_shifts_team_id ON shifts (team_id);
CREATE INDEX ix_shifts_shift_date ON shifts (shift_date);

CREATE TABLE employee_availability (
	availability_id SERIAL NOT NULL, 
	employee_id VARCHAR(16) NOT NULL, 
	day_of_week INTEGER NOT NULL, 
	is_available BOOLEAN NOT NULL, 
	available_from TIME WITHOUT TIME ZONE NOT NULL, 
	available_to TIME WITHOUT TIME ZONE NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_employee_availability PRIMARY KEY (availability_id), 
	CONSTRAINT uq_availability_version UNIQUE (employee_id, day_of_week, effective_from), 
	CONSTRAINT fk_employee_availability_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id) ON DELETE CASCADE
);
CREATE INDEX ix_employee_availability_employee_id ON employee_availability (employee_id);

CREATE TABLE employee_skills (
	employee_id VARCHAR(16) NOT NULL, 
	skill_id VARCHAR(16) NOT NULL, 
	proficiency INTEGER NOT NULL, 
	certified BOOLEAN NOT NULL, 
	years_experience FLOAT NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_employee_skills PRIMARY KEY (employee_id, skill_id), 
	CONSTRAINT fk_employee_skills_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id) ON DELETE CASCADE, 
	CONSTRAINT fk_employee_skills_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (skill_id) ON DELETE CASCADE
);
CREATE INDEX ix_employee_skills_skill_id ON employee_skills (skill_id);

CREATE TABLE team_managers (
	team_manager_id SERIAL NOT NULL, 
	team_id VARCHAR(16) NOT NULL, 
	employee_id VARCHAR(16) NOT NULL, 
	is_primary BOOLEAN NOT NULL, 
	effective_from DATE NOT NULL, 
	effective_to DATE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_team_managers PRIMARY KEY (team_manager_id), 
	CONSTRAINT uq_team_manager_version UNIQUE (team_id, employee_id, effective_from), 
	CONSTRAINT fk_team_managers_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (team_id), 
	CONSTRAINT fk_team_managers_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id)
);
CREATE INDEX ix_team_managers_employee_id ON team_managers (employee_id);
CREATE INDEX ix_team_managers_team_id ON team_managers (team_id);

CREATE TABLE users (
	user_id VARCHAR(16) NOT NULL, 
	employee_id VARCHAR(16), 
	username VARCHAR(60) NOT NULL, 
	email VARCHAR(160) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role_id VARCHAR(16) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	last_login_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (user_id), 
	CONSTRAINT fk_users_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT uq_users_email UNIQUE (email), 
	CONSTRAINT fk_users_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (role_id)
);
CREATE UNIQUE INDEX ix_users_employee_id ON users (employee_id);
CREATE INDEX ix_users_role_id ON users (role_id);
CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE audit_logs (
	audit_id SERIAL NOT NULL, 
	actor_user_id VARCHAR(16), 
	actor_role VARCHAR(30), 
	action VARCHAR(60) NOT NULL, 
	entity_type VARCHAR(60) NOT NULL, 
	entity_id VARCHAR(80), 
	previous_state JSON, 
	new_state JSON, 
	reason TEXT, 
	ip_address VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_audit_logs PRIMARY KEY (audit_id), 
	CONSTRAINT fk_audit_logs_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (user_id)
);
CREATE INDEX ix_audit_logs_actor_user_id ON audit_logs (actor_user_id);
CREATE INDEX ix_audit_logs_entity_type ON audit_logs (entity_type);
CREATE INDEX ix_audit_logs_entity_id ON audit_logs (entity_id);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE TABLE leave_requests (
	leave_id VARCHAR(24) NOT NULL, 
	employee_id VARCHAR(16) NOT NULL, 
	policy_id VARCHAR(16) NOT NULL, 
	leave_type VARCHAR(30) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	total_days FLOAT NOT NULL, 
	reason TEXT NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	decided_at TIMESTAMP WITHOUT TIME ZONE, 
	decided_by_user_id VARCHAR(16), 
	manager_comment TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_leave_requests PRIMARY KEY (leave_id), 
	CONSTRAINT fk_leave_requests_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_leave_requests_policy_id_leave_policies FOREIGN KEY(policy_id) REFERENCES leave_policies (policy_id), 
	CONSTRAINT fk_leave_requests_decided_by_user_id_users FOREIGN KEY(decided_by_user_id) REFERENCES users (user_id)
);
CREATE INDEX ix_leave_requests_status ON leave_requests (status);
CREATE INDEX ix_leave_requests_employee_id ON leave_requests (employee_id);
CREATE INDEX ix_leave_requests_start_date ON leave_requests (start_date);
CREATE INDEX ix_leave_requests_leave_type ON leave_requests (leave_type);
CREATE INDEX ix_leave_requests_end_date ON leave_requests (end_date);

CREATE TABLE scheduling_runs (
	run_id VARCHAR(24) NOT NULL, 
	team_id VARCHAR(16), 
	scope_start DATE NOT NULL, 
	scope_end DATE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	solver_status VARCHAR(20) NOT NULL, 
	objective_value FLOAT, 
	assignments_created INTEGER NOT NULL, 
	coverage_gaps INTEGER NOT NULL, 
	hard_violations INTEGER NOT NULL, 
	soft_score FLOAT, 
	duration_seconds FLOAT, 
	parameters JSON NOT NULL, 
	created_by_user_id VARCHAR(16), 
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_scheduling_runs PRIMARY KEY (run_id), 
	CONSTRAINT fk_scheduling_runs_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (team_id), 
	CONSTRAINT fk_scheduling_runs_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (user_id)
);
CREATE INDEX ix_scheduling_runs_status ON scheduling_runs (status);
CREATE INDEX ix_scheduling_runs_team_id ON scheduling_runs (team_id);

CREATE TABLE system_config (
	config_key VARCHAR(60) NOT NULL, 
	config_value JSON, 
	description VARCHAR(255), 
	updated_by_user_id VARCHAR(16), 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_system_config PRIMARY KEY (config_key), 
	CONSTRAINT fk_system_config_updated_by_user_id_users FOREIGN KEY(updated_by_user_id) REFERENCES users (user_id)
);

CREATE TABLE leave_approval_history (
	history_id SERIAL NOT NULL, 
	leave_id VARCHAR(24) NOT NULL, 
	from_status VARCHAR(30), 
	to_status VARCHAR(30) NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	actor_user_id VARCHAR(16), 
	comment TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_leave_approval_history PRIMARY KEY (history_id), 
	CONSTRAINT fk_leave_approval_history_leave_id_leave_requests FOREIGN KEY(leave_id) REFERENCES leave_requests (leave_id) ON DELETE CASCADE, 
	CONSTRAINT fk_leave_approval_history_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (user_id)
);
CREATE INDEX ix_leave_approval_history_leave_id ON leave_approval_history (leave_id);

CREATE TABLE shift_assignments (
	assignment_id VARCHAR(16) NOT NULL, 
	shift_id VARCHAR(40) NOT NULL, 
	employee_id VARCHAR(16) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	assignment_source VARCHAR(20) NOT NULL, 
	assigned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	scheduled_hours FLOAT NOT NULL, 
	is_overtime BOOLEAN NOT NULL, 
	run_id VARCHAR(24), 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_shift_assignments PRIMARY KEY (assignment_id), 
	CONSTRAINT fk_shift_assignments_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (shift_id), 
	CONSTRAINT fk_shift_assignments_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_shift_assignments_run_id_scheduling_runs FOREIGN KEY(run_id) REFERENCES scheduling_runs (run_id)
);
CREATE INDEX ix_shift_assignments_run_id ON shift_assignments (run_id);
CREATE INDEX ix_shift_assignments_shift_id ON shift_assignments (shift_id);
CREATE INDEX ix_shift_assignments_status ON shift_assignments (status);
CREATE INDEX ix_shift_assignments_employee_id ON shift_assignments (employee_id);

CREATE TABLE attendance_events (
	attendance_id VARCHAR(64) NOT NULL, 
	employee_id VARCHAR(16) NOT NULL, 
	shift_id VARCHAR(40), 
	assignment_id VARCHAR(16), 
	scheduled_start TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	scheduled_end TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	actual_check_in TIMESTAMP WITHOUT TIME ZONE, 
	actual_check_out TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(30) NOT NULL, 
	late_minutes INTEGER NOT NULL, 
	early_departure_minutes INTEGER NOT NULL, 
	actual_hours FLOAT NOT NULL, 
	overtime_hours FLOAT NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	reconciliation_status VARCHAR(20) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_attendance_events PRIMARY KEY (attendance_id), 
	CONSTRAINT fk_attendance_events_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_attendance_events_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (shift_id), 
	CONSTRAINT fk_attendance_events_assignment_id_shift_assignments FOREIGN KEY(assignment_id) REFERENCES shift_assignments (assignment_id)
);
CREATE INDEX ix_attendance_events_shift_id ON attendance_events (shift_id);
CREATE INDEX ix_attendance_events_employee_id ON attendance_events (employee_id);
CREATE INDEX ix_attendance_events_status ON attendance_events (status);
CREATE UNIQUE INDEX ix_attendance_events_assignment_id ON attendance_events (assignment_id);

CREATE TABLE scheduling_decisions (
	decision_id SERIAL NOT NULL, 
	run_id VARCHAR(24) NOT NULL, 
	shift_id VARCHAR(40) NOT NULL, 
	employee_id VARCHAR(16) NOT NULL, 
	assignment_id VARCHAR(16), 
	reason TEXT NOT NULL, 
	skill_match BOOLEAN NOT NULL, 
	availability_result VARCHAR(40) NOT NULL, 
	leave_eligible BOOLEAN NOT NULL, 
	constraint_evaluation JSON NOT NULL, 
	optimization_score FLOAT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_scheduling_decisions PRIMARY KEY (decision_id), 
	CONSTRAINT fk_scheduling_decisions_run_id_scheduling_runs FOREIGN KEY(run_id) REFERENCES scheduling_runs (run_id) ON DELETE CASCADE, 
	CONSTRAINT fk_scheduling_decisions_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (shift_id), 
	CONSTRAINT fk_scheduling_decisions_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_scheduling_decisions_assignment_id_shift_assignments FOREIGN KEY(assignment_id) REFERENCES shift_assignments (assignment_id)
);
CREATE INDEX ix_scheduling_decisions_run_id ON scheduling_decisions (run_id);
CREATE INDEX ix_scheduling_decisions_employee_id ON scheduling_decisions (employee_id);
CREATE INDEX ix_scheduling_decisions_shift_id ON scheduling_decisions (shift_id);
CREATE UNIQUE INDEX ix_scheduling_decisions_assignment_id ON scheduling_decisions (assignment_id);

CREATE TABLE scheduling_exceptions (
	issue_id VARCHAR(24) NOT NULL, 
	run_id VARCHAR(24), 
	issue_type VARCHAR(40) NOT NULL, 
	employee_id VARCHAR(16), 
	shift_id VARCHAR(40), 
	assignment_id VARCHAR(16), 
	transaction_type VARCHAR(30), 
	transaction_id VARCHAR(30), 
	severity VARCHAR(20) NOT NULL, 
	description TEXT NOT NULL, 
	detection_source VARCHAR(40) NOT NULL, 
	resolution_status VARCHAR(20) NOT NULL, 
	detected_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	resolved_by_user_id VARCHAR(16), 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	resolution_note TEXT, 
	fingerprint VARCHAR(220) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_scheduling_exceptions PRIMARY KEY (issue_id), 
	CONSTRAINT fk_scheduling_exceptions_run_id_scheduling_runs FOREIGN KEY(run_id) REFERENCES scheduling_runs (run_id), 
	CONSTRAINT fk_scheduling_exceptions_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_scheduling_exceptions_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (shift_id), 
	CONSTRAINT fk_scheduling_exceptions_assignment_id_shift_assignments FOREIGN KEY(assignment_id) REFERENCES shift_assignments (assignment_id), 
	CONSTRAINT fk_scheduling_exceptions_resolved_by_user_id_users FOREIGN KEY(resolved_by_user_id) REFERENCES users (user_id), 
	CONSTRAINT uq_scheduling_exceptions_fingerprint UNIQUE (fingerprint)
);
CREATE INDEX ix_scheduling_exceptions_run_id ON scheduling_exceptions (run_id);
CREATE INDEX ix_scheduling_exceptions_severity ON scheduling_exceptions (severity);
CREATE INDEX ix_scheduling_exceptions_shift_id ON scheduling_exceptions (shift_id);
CREATE INDEX ix_scheduling_exceptions_issue_type ON scheduling_exceptions (issue_type);
CREATE INDEX ix_scheduling_exceptions_transaction_id ON scheduling_exceptions (transaction_id);
CREATE INDEX ix_scheduling_exceptions_employee_id ON scheduling_exceptions (employee_id);
CREATE INDEX ix_scheduling_exceptions_resolution_status ON scheduling_exceptions (resolution_status);

CREATE TABLE swap_requests (
	swap_id VARCHAR(24) NOT NULL, 
	requester_employee_id VARCHAR(16) NOT NULL, 
	target_employee_id VARCHAR(16) NOT NULL, 
	requester_assignment_id VARCHAR(16) NOT NULL, 
	target_assignment_id VARCHAR(16) NOT NULL, 
	reason TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	requester_agreed BOOLEAN NOT NULL, 
	target_agreed BOOLEAN NOT NULL, 
	target_responded_at TIMESTAMP WITHOUT TIME ZONE, 
	manager_user_id VARCHAR(16), 
	decided_at TIMESTAMP WITHOUT TIME ZONE, 
	decision_comment TEXT, 
	applied_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_swap_requests PRIMARY KEY (swap_id), 
	CONSTRAINT fk_swap_requests_requester_employee_id_employees FOREIGN KEY(requester_employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_swap_requests_target_employee_id_employees FOREIGN KEY(target_employee_id) REFERENCES employees (employee_id), 
	CONSTRAINT fk_swap_requests_requester_assignment_id_shift_assignments FOREIGN KEY(requester_assignment_id) REFERENCES shift_assignments (assignment_id), 
	CONSTRAINT fk_swap_requests_target_assignment_id_shift_assignments FOREIGN KEY(target_assignment_id) REFERENCES shift_assignments (assignment_id), 
	CONSTRAINT fk_swap_requests_manager_user_id_users FOREIGN KEY(manager_user_id) REFERENCES users (user_id)
);
CREATE INDEX ix_swap_requests_target_employee_id ON swap_requests (target_employee_id);
CREATE INDEX ix_swap_requests_requester_employee_id ON swap_requests (requester_employee_id);
CREATE INDEX ix_swap_requests_status ON swap_requests (status);

CREATE TABLE swap_approval_history (
	history_id SERIAL NOT NULL, 
	swap_id VARCHAR(24) NOT NULL, 
	from_status VARCHAR(20), 
	to_status VARCHAR(20) NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	actor_user_id VARCHAR(16), 
	comment TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT pk_swap_approval_history PRIMARY KEY (history_id), 
	CONSTRAINT fk_swap_approval_history_swap_id_swap_requests FOREIGN KEY(swap_id) REFERENCES swap_requests (swap_id) ON DELETE CASCADE, 
	CONSTRAINT fk_swap_approval_history_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (user_id)
);
CREATE INDEX ix_swap_approval_history_swap_id ON swap_approval_history (swap_id);
