"""Python background tasks: the task library's definitions as routes and the calls that hand tasks to workers as
calls, over Protocol.TASK (table: the library entry points)."""

from .collector import TaskEndpoints
from .definitions import Task, TaskDefinitions
from .modules import ModuleNames
from .table import ByName, TaskTable

__all__ = ['ByName', 'ModuleNames', 'Task', 'TaskDefinitions', 'TaskEndpoints', 'TaskTable']
