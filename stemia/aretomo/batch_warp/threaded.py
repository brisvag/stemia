from concurrent import futures
import os
import subprocess

from rich import print


def run_threaded(progress, partials, label='', max_workers=None, dry_run=False, **kwargs):
    max_workers = max_workers or min(32, os.cpu_count() + 4)  # see concurrent docs

    with futures.ThreadPoolExecutor(max_workers) as executor:
        main_task = progress.add_task(label, total=len(partials))

        jobs = []
        for fn in partials:
            job = executor.submit(fn)
            jobs.append(job)

        tasks = []
        for i, thread in enumerate(executor._threads):
            tasks.append(progress.add_task(f'thread #{i}...', total=None))

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

        for t in tasks:
            progress.update(t, visible=False)

        if exist:
            print(f'[red]{exist} files already existed and were not overwritten')

        if errors:
            print(f'[red]{len(errors)} commands have failed:')
            for err in errors:
                print(f'[yellow]{" ".join(err.cmd)}[/yellow] failed with:\n[red]{err.stderr.decode()}')
