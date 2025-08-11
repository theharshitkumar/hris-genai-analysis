# Retriever tool
few_shots_examples = {
    'How many employees are in the Engineering department in New York?': """SELECT COUNT(*) FROM employees WHERE department = 'Engineering' AND location = 'New York'""",
    'Which manager has the highest number of direct reports?': """SELECT manager_id, COUNT(*) as num_reports FROM employees GROUP BY manager_id ORDER BY num_reports DESC LIMIT 1""",
    'What is the average tenure in the Sales department?': """SELECT AVG(tenure_years) FROM employees WHERE department = 'Sales'""",
    'Who are the top 3 longest-tenured employees in Marketing?': """SELECT first_name, last_name, tenure_years FROM employees WHERE department = 'Marketing' ORDER BY tenure_years DESC LIMIT 3""",
    'List teams reporting to the Director of Operations in APAC': """SELECT team_name FROM teams WHERE manager_id = (SELECT employee_id FROM employees WHERE job_title = 'Director of Operations' AND region = 'APAC')""",
}

retriever_tool_description = (
    "The 'sql_get_few_shot' tool is designed for efficient and accurate retrieval of "
    'SQL query examples closely related to a given user query. It identifies the most '
    'relevant pre-defined SQL query from a curated set.'
)

# Other tools

COLUMNS_DESCRIPTIONS = {
    'employee_id': 'Unique numeric identifier assigned to each employee.',
    'first_name': "Employee's first name.",
    'last_name': "Employee's last name.",
    'department': 'The functional business unit the employee belongs to (e.g., Engineering, Sales).',
    'job_title': "The full designation of the employee's role (e.g., Software Engineer, Sales Executive).",
    'job_level': 'The seniority or grade level of the job, usually numeric (e.g., 1 = entry-level, 5 = senior/executive).',
    'location': 'The physical office location where the employee is based (e.g., New York, Chicago).',
    'region': 'The broader geographical region the location falls under (e.g., NA = North America, EMEA, APAC).',
    'manager_id': 'Employee ID of the direct (line) manager the employee reports to.',
    'joining_date': 'Date when the employee officially joined the organization.',
    'exit_date': 'Date when the employee exited the organization (empty if still active).',
    'performance_rating': 'Most recent performance score of the employee, typically on a numeric scale (e.g., 1-5).',
    'tenure_years': 'Number of years the employee has been with the company (calculated from joining_date to today or exit_date).',
    'is_active': 'Indicates whether the employee is currently active in the organization (TRUE/FALSE).',
    'supervisor_id': 'Employee ID of a secondary/dotted-line supervisor (used in matrix organizations for cross-functional oversight).',
}
