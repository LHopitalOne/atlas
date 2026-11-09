"""The task libraries the Python extractor knows: what makes a function a task, and which calls hand a task to the
workers. Every row restates a library's documented API; the machinery that reads them (definitions, collector) is
shared."""

from typing import NamedTuple

from ..channels import Argument, LibraryType


class ByName(NamedTuple):
    """A call that sends a task by its registered name: a method of the app object (`app.send_task(name)`) or, with
    `method` empty, a function of the library module (`celery.signature(name)`)."""

    method: str
    function: str
    name: Argument


class TaskTable:
    """Celery: `@shared_task` and `@app.task` (with or without arguments; `name=` gives the task another name than
    '<module>.<function>') make a task; `task.delay(...)`, `task.apply_async(...)` and the signatures `task.s(...)`,
    `task.si(...)` and `task.signature(...)` (sent once applied or put in a chain, group or chord) send it;
    `app.send_task(name)`, `app.signature(name)` and `celery.signature(name)` send one by its name."""

    LIBRARY = 'celery'
    TYPES = (LibraryType('celery', 'Celery', ('Celery',)),)  # the app: `app = Celery('proj')`
    APPS = ('current_app',)  # names the library exports that stand for the app itself
    TASK_FUNCTIONS = ('shared_task',)  # functions of the library that make a task of the function they decorate
    TASK_METHODS = ('task',)  # methods of the app that do
    NAME = Argument(None, 'name')  # where a task decorator gives the task's name
    SENDS = frozenset({'delay', 'apply_async', 's', 'si', 'signature'})  # methods of a task that send it
    BY_NAME = (
        ByName('send_task', '', Argument(0, 'name')),
        ByName('signature', 'signature', Argument(0, 'varies')),
    )

    @classmethod
    def callees(cls) -> frozenset:
        """Every method or function name a sending call may be made by."""
        return cls.SENDS | {b.method for b in cls.BY_NAME} | {b.function for b in cls.BY_NAME if b.function}
