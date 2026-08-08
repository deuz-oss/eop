"""Advanced Payroll calculation components.

Each class here is a small, composed, Domain-Service-shaped calculator
(E8: compositional, no premature framework) that `PayrollCalculationService`
injects via its constructor. Every component reads upstream capabilities
(Compensation, Allowance, Overtime, Attendance/Leave) strictly read-only
(E3/E10 -- domain ownership boundaries as specified) and lives entirely
inside this package -- `AttendanceEvent`, `LeaveRequest`, `OvertimeRequest`,
and `Timesheet` are never modified here.
"""
