
from __future__ import annotations


def job_payload(job) -> dict:
    """A job as the API reports it: ids plus the position name it stands for."""
    return {
        "id": job.id,
        "brand_id": job.brand_id,
        "employee_id": job.employee_id,
        "position_id": job.position_id,
        "role": job.position.name if job.position is not None else None,
        "status": job.status,
    }


def shift_payload(shift) -> dict:

    role = shift.role
    schedule = role.schedule if role is not None else None
    brand = schedule.brand if schedule is not None else None
    job = shift.job
    employee = job.employee if job is not None else None
    return {
        "shift_id": shift.id,
        "job_id": shift.job_id,
        "employee_id": job.employee_id if job is not None else None,
        "employee": employee.name if employee is not None else None,
        "role_id": shift.role_id,
        "role": role.name if role is not None else None,
        "schedule_id": schedule.id if schedule is not None else None,
        "brand_id": brand.id if brand is not None else None,
        "brand": brand.name if brand is not None else None,
        "date": shift.date.isoformat() if shift.date else None,
        "starting_time": shift.starting_time.isoformat() if shift.starting_time else None,
        "finishing_time": shift.finishing_time.isoformat() if shift.finishing_time else None,
    }
