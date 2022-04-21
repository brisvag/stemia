import threading
from concurrent import futures
import os
import math
import subprocess

from rich import print


def run_threaded(progress, partials, label='', max_workers=None, dry_run=False, **kwargs):
    def update_bar(thread_to_task):
        progress.update(thread_to_task[threading.get_ident()], advance=1)

    max_workers = max_workers or min(32, os.cpu_count() + 4)  # see concurrent docs
    thread_to_task = {}

    with futures.ThreadPoolExecutor(max_workers) as executor:
        main_task = progress.add_task(label, total=len(partials))

        jobs = []
        for fn in partials:
            job = executor.submit(fn)
            job.add_done_callback(lambda _: update_bar(thread_to_task))
            jobs.append(job)

        for thread in executor._threads:
            task = progress.add_task('thread worker...', total=math.ceil(len(partials) / max_workers))
            thread_to_task[thread.ident] = task
        if executor._threads == 1:
            task.disable = True

        exist = 0
        errors = []
        for job in futures.as_completed(jobs):
            try:
                job.result()
            except FileExistsError:
                exist += 1
            except subprocess.CalledProcessError as e:
                errors.append(e)
            progress.update(main_task, advance=1)

        for t in thread_to_task.values():
            progress.update(t, visible=False)

        if exist:
            print(f'[red]{exist} files already existed and were not overwritten')

        if errors:
            print(f'[red]{len(errors)} commands have failed:')
            for err in errors:
                print(f'[yellow]{" ".join(err.cmd)}[/yellow] failed with:\n[red]{err.stderr.decode()}')
