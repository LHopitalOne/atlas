import unittest

from atlas_bridge.core.http import Extraction, Protocol
from atlas_bridge.usecases.link import LinkFinder

from .support import extract

APP = """
from celery import Celery

app = Celery('proj')
"""

TASKS = """
from celery import shared_task
from .celery import app

@shared_task
def send_mail(to):
    pass

@app.task(bind=True, name='mail.digest')
def digest(self):
    pass

@shared_task(name=NAMES[0])
def unnamed():
    pass

def plain():
    pass
"""


def tasks(ex):
    return {(str(r.path), r.file, r.line, r.handler) for r in ex.routes if r.protocol == Protocol.TASK}


def sent(ex):
    return sorted((c.line, str(c.path)) for c in ex.calls if c.protocol == Protocol.TASK)


class CeleryDefinitionTest(unittest.TestCase):
    def test_tasks_are_named_after_their_module_or_given_name(self):
        ex = extract({'src/proj/__init__.py': '', 'src/proj/celery.py': APP, 'src/proj/tasks.py': TASKS})
        self.assertEqual(
            tasks(ex),
            {
                # 'src' holds no __init__.py: the package starts at proj, as the interpreter imports it
                ('/proj.tasks.send_mail', 'src/proj/tasks.py', 5, 'send_mail'),
                ('/mail.digest', 'src/proj/tasks.py', 9, 'digest'),
            },
        )  # a name= that cannot be read leaves the task out, and an undecorated function is no task
        self.assertEqual({r.framework for r in ex.routes if r.protocol == Protocol.TASK}, {'celery'})

    def test_a_module_outside_any_package_is_named_by_its_path(self):
        ex = extract({'worker/jobs.py': 'import celery\n\n@celery.shared_task()\ndef clean():\n    pass\n'})
        self.assertEqual(tasks(ex), {('/worker.jobs.clean', 'worker/jobs.py', 3, 'clean')})

    def test_task_decorators_of_other_objects_and_tests_are_not_tasks(self):
        ex = extract(
            {
                'proj/__init__.py': '',
                'proj/jobs.py': """
                from scheduler import app

                @app.task
                def not_celery():
                    pass
                """,
                'proj/tests/test_jobs.py': """
                from celery import shared_task

                @shared_task
                def fake():
                    pass
                """,
            }
        )
        self.assertEqual(tasks(ex), set())


class CelerySendTest(unittest.TestCase):
    def test_each_way_of_sending_a_task_resolved_through_imports(self):
        ex = extract(
            {
                'proj/__init__.py': '',
                'proj/celery.py': APP,
                'proj/tasks.py': TASKS,
                'proj/views.py': """
                from celery import chain, current_app, signature
                from proj.tasks import send_mail, digest, plain
                from proj import tasks
                from .celery import app

                def view(callback):
                    send_mail.delay('a')
                    tasks.digest.apply_async(countdown=3)
                    chain(send_mail.s('x'), digest.si())
                    app.send_task('proj.tasks.send_mail')
                    current_app.send_task('billing.tasks.charge')
                    signature('mail.digest')
                    plain.delay()
                    callback.delay()

                def shadowed(send_mail):
                    send_mail.delay()
                """,
            }
        )
        self.assertEqual(
            sent(ex),
            [
                (8, '/proj.tasks.send_mail'),
                (9, '/mail.digest'),
                (10, '/mail.digest'),  # signatures in a chain
                (10, '/proj.tasks.send_mail'),
                (11, '/proj.tasks.send_mail'),
                (12, '/billing.tasks.charge'),  # a task another repository defines, by its literal name
                (13, '/mail.digest'),
            ],
        )  # a function that is no task, a parameter and a name a parameter shadows send nothing

    def test_a_task_sent_by_name_links_to_the_repository_that_defines_it(self):
        worker = extract({'billing/__init__.py': '', 'billing/celery.py': APP, 'billing/tasks.py': TASKS}, 'billing')
        web = extract(
            {'web/views.py': "from celery import current_app\ncurrent_app.send_task('billing.tasks.send_mail')\n"}
        )
        links = LinkFinder(['svc', 'billing']).find(Extraction(worker.routes, web.calls))
        self.assertEqual([(lk.target, lk.route.handler) for lk in links], [('billing', 'send_mail')])


if __name__ == '__main__':
    unittest.main()
