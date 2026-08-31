from database.models import Employee
from repositories.base import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee