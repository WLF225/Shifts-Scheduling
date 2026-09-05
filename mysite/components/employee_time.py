
from __future__ import annotations

from datetime import time as time_type
from typing import Any

from components.base import BaseComponent
from components.exceptions import NotFound
from components.parsing import parse_modes
from repositories.employee import EmployeeRepository
from repositories.shift import ShiftRepository

# The window FREE slots are measured against.
WORKDAY_START = time_type(0, 0)
WORKDAY_END = time_type(23, 59)

MODES = ("free", "busy")


class EmployeeTimeComponent(BaseComponent):

    def times(self, employee_pk=None, mode: Any = None) -> dict:

        employee = self._repo(EmployeeRepository).get(employee_pk)
        if employee is None:
            raise NotFound(f"Employee {employee_pk} not found")

        modes = parse_modes(mode, MODES)
        shifts = self._repo(ShiftRepository).for_employee(employee.id)

        payload = {"employee_id": employee.id}
        if "busy" in modes:
            payload["busy"] = [self._busy_block(shift) for shift in shifts]
        if "free" in modes:
            payload["free"] = self._free(shifts)
        return payload

    @staticmethod
    def _busy_block(shift) -> dict:
        role = shift.role
        schedule = role.schedule if role is not None else None
        brand = schedule.brand if schedule is not None else None
        return {
            "shift_id": shift.id,
            "date": shift.date.isoformat() if shift.date else None,
            "starting_time": shift.starting_time.isoformat(),
            "finishing_time": shift.finishing_time.isoformat(),
            "role": role.name if role is not None else None,
            "brand": brand.name if brand is not None else None,
        }

    @staticmethod
    def _free(shifts) -> list[dict]:
        """The complement of the busy blocks, day by day.

        Only days the employee already works are reported - a day with no shift
        at all is free by definition, and listing every such day would be an
        unbounded answer.
        """
        by_day: dict[object, list] = {}
        for shift in shifts:
            by_day.setdefault(shift.date, []).append(shift)

        free: list[dict] = []
        for day in sorted(by_day):
            blocks = sorted(
                by_day[day], key=lambda s: (s.starting_time, s.finishing_time)
            )
            cursor = WORKDAY_START
            for block in blocks:
                if block.starting_time > cursor:
                    free.append(
                        {
                            "date": day.isoformat() if day else None,
                            "starting_time": cursor.isoformat(),
                            "finishing_time": block.starting_time.isoformat(),
                        }
                    )
                # Overlapping shifts must not rewind cursor.
                if block.finishing_time > cursor:
                    cursor = block.finishing_time
            if cursor < WORKDAY_END:
                free.append(
                    {
                        "date": day.isoformat() if day else None,
                        "starting_time": cursor.isoformat(),
                        "finishing_time": WORKDAY_END.isoformat(),
                    }
                )
        return free