import unittest

from atlas_bridge.core.http import Protocol

from .support import Channels

T = Protocol.TASK

ENUMS = (
    "export enum Queues { Mail = 'mail', Thumbs = 'thumbs' }\n"
    "export enum MailJob { Welcome = 'welcome', Reset = 'reset-password', Count }\n"
    "export const BATCH = { DIGEST: 'digest' } as const;\n"
)


def paths(found):
    return [path for _, _, path, _, _ in found.calls], [(path, line) for _, _, path, _, line in found.routes]


class BullmqTest(unittest.TestCase):
    def test_queue_jobs_and_a_worker_of_every_job(self):
        found = Channels.of(
            "const { Queue, Worker } = require('bullmq');\n"
            "const queue = new Queue('thumbs', { connection });\n"
            'async function make(id) {\n'
            "  await queue.add('resize', { id });\n"
            "  await queue.addBulk([{ name: 'crop', data: { id } }, { name: dynamicName(), data: {} }]);\n"
            '  await queue.getJobCounts();\n'
            '}\n'
            "const worker = new Worker('thumbs', async (job) => resize(job.data), { connection });\n"
        )
        self.assertEqual(paths(found), (['/thumbs/resize', '/thumbs/crop'], [('/thumbs/{job}', 8)]))
        self.assertEqual({c[0] for c in found.calls} | {r[0] for r in found.routes}, {T})

    def test_a_processor_that_dispatches_on_the_job_name(self):
        found = Channels.of(
            "import { Worker } from 'bullmq';\n"
            "new Worker('reports', processReport);\n"
            "new Worker('exports', ({ name }) => { switch (name) { case 'csv': return; } });\n"
            'function processReport(job) {\n'
            '  switch (job.name) {\n'
            "    case 'daily': return daily(job);\n"
            '    case kindOf(job): return other(job);\n'  # not known: the worker takes every other job too
            '  }\n'
            '}\n'
        )
        self.assertEqual(paths(found)[1], [('/reports/daily', 2), ('/reports/{job}', 2), ('/exports/csv', 3)])

    def test_a_switch_nested_in_a_case_names_no_job(self):
        found = Channels.of(
            "import { Worker } from 'bullmq';\n"
            "new Worker('media', async (job) => {\n"
            '  switch (job.name) {\n'
            "    case 'scale': switch (job.data.format) { case 'png': break; } break;\n"
            '  }\n'
            '});\n'
        )
        self.assertEqual(paths(found)[1], [('/media/scale', 2)])

    def test_nestjs_injected_queue_and_processor_with_enum_names(self):
        found = Channels(
            {
                'src/enums.ts': ENUMS,
                'src/mail.service.ts': (
                    "import { Injectable } from '@nestjs/common';\n"
                    "import { InjectQueue } from '@nestjs/bullmq';\n"
                    "import { Queue } from 'bullmq';\n"
                    "import { Queues, MailJob, BATCH } from './enums';\n"
                    '@Injectable()\n'
                    'export class MailService {\n'
                    '  constructor(@InjectQueue(Queues.Mail) private readonly queue: Queue) {}\n'
                    '  welcome(user) { return this.queue.add(MailJob.Welcome, { user }); }\n'
                    '  count() { return this.queue.add(MailJob.Count, {}); }\n'  # a counted member: not read
                    '  many() { return this.queue.addBulk([{ name: BATCH.DIGEST, data: {} }]); }\n'
                    '}\n'
                ),
                'src/mail.processor.ts': (
                    "import { Processor, WorkerHost } from '@nestjs/bullmq';\n"
                    "import { Job } from 'bullmq';\n"
                    "import { Queues, MailJob } from './enums';\n"
                    '@Processor(Queues.Mail)\n'
                    'export class MailProcessor extends WorkerHost {\n'
                    '  async process(job: Job): Promise<void> {\n'
                    '    switch (job.name) {\n'
                    '      case MailJob.Welcome: return;\n'
                    "      case 'digest': return;\n"
                    '    }\n'
                    '  }\n'
                    '}\n'
                ),
                'src/thumbs.processor.ts': (
                    "import { Processor, WorkerHost } from '@nestjs/bullmq';\n"
                    "@Processor({ name: 'thumbs' })\n"
                    'class ThumbsProcessor extends WorkerHost {\n'
                    '  async process(job) { return work(job); }\n'
                    '}\n'
                ),
            }
        )
        calls, routes = paths(found)
        self.assertEqual(sorted(calls), ['/mail/digest', '/mail/welcome'])
        self.assertEqual(sorted(routes), [('/mail/digest', 4), ('/mail/welcome', 4), ('/thumbs/{job}', 2)])

    def test_a_queue_method_of_another_library_is_not_a_job(self):
        found = Channels.of("import { Queue } from 'other-queue';\nnew Queue('mail').add('welcome', {});\n")
        self.assertEqual(found.calls, [])


if __name__ == '__main__':
    unittest.main()
