import click


@click.command()
@click.argument(
    "project_dirs",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=True, resolve_path=True),
)
@click.option(
    "-u",
    "--useful_jobs",
    type=str,
    multiple=True,
    help=(
        "ID of job that gave useful results. Its running time and that of its parents "
        "will be used to calculate useful time. Can be passed multiple times."
    ),
)
def cli(project_dirs, useful_jobs):
    """Print the total amount of time wasted on a project."""
    if len(project_dirs) > 1 and useful_jobs:
        raise click.UsageError(
            "do not provide useful_job when analysing more than one project"
        )

    import json
    import logging
    from datetime import datetime, timedelta
    from pathlib import Path

    from rich import print
    from rich.logging import RichHandler
    from rich.progress import Progress

    logging.basicConfig(
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()],
    )

    logger = logging.getLogger(__name__)

    with Progress() as prog:
        for proj in prog.track(project_dirs, description="Reading projects..."):
            proj = Path(proj)

            total_running = timedelta(0)
            total_queued = timedelta(0)
            total_cpu = timedelta(0)
            total_gpu = timedelta(0)
            total_interactive = timedelta(0)
            skipped = 0

            parents = set()
            total_useful = timedelta(0)

            if useful_jobs:

                def get_parents(job, proj, parents):
                    with open(proj / job / "job.json") as f:
                        meta = json.load(f)

                    parents.add(job)
                    for par in meta["parents"]:
                        if par not in parents:
                            get_parents(par, proj, parents)

                for job in useful_jobs:
                    get_parents(job, proj, parents)

            jobs = list(proj.glob("J*"))
            for job in prog.track(jobs, description="Reading jobs..."):
                job_meta = job / "job.json"
                if not job_meta.exists():
                    logger.info(f"Missing job metadata for {job.name}, skipping.")
                    skipped += 1
                    continue
                with open(job_meta) as f:
                    meta = json.load(f)

                start = meta["started_at"]
                if start is None:
                    logger.info(f"job {job.name} was not started, skipping")
                    skipped += 1
                    continue

                launch = meta["launched_at"]

                end = meta["completed_at"]
                if end is None:
                    end = meta["failed_at"]
                if end is None:
                    logger.info(f"job {job.name} was not finished, skipping")
                    skipped += 1
                    continue

                if isinstance(end["$date"], int):
                    running = timedelta(milliseconds=end["$date"] - start["$date"])
                    queued = timedelta(milliseconds=start["$date"] - launch["$date"])
                elif isinstance(end["$date"], str):
                    running = datetime.fromisoformat(
                        end["$date"]
                    ) - datetime.fromisoformat(start["$date"])
                    queued = datetime.fromisoformat(
                        start["$date"]
                    ) - datetime.fromisoformat(launch["$date"])

                total_queued += queued

                if meta["interactive"]:
                    total_interactive += running

                resources = meta["resources_needed"].get("slots", None)
                if resources is None and meta.get("run_on_master_direct", False):
                    cpus = 1 * running  # I guess...
                    gpus = 0 * running
                else:
                    cpus = resources.get("CPU", 0) * running
                    gpus = resources.get("GPU", 0) * running

                total_running += running

                if useful_jobs and job.name in parents:
                    total_useful += running

                total_cpu += cpus
                total_gpu += gpus

            tot_with_queue = total_running + total_queued
            print(
                "================================================================================"
            )
            print(
                f"Time wasted by processors on [green]{proj.name}[/]: "
                f"[bold red]{total_running.days} days and {int(total_running.seconds / 3600)} hours[/].\n"
                f"Time wasted by you sitting in interactive jobs: "
                f"[bold red]{total_interactive.days} days and {int(total_interactive.seconds / 3600)} hours[/].\n"
                "Counting queue time: "
                f"[bold red]{tot_with_queue.days} days and {int(tot_with_queue.seconds / 3600)} hours[/].\n"
            )
            print(
                "If this project had been running on a single average CPU core\n"
                "and a single average GPU, it would have taken:\n"
                f"[bold red]{total_cpu.days} days and {int(total_cpu.seconds / 3600)} hours[/] of CPU time and\n"
                f"[bold red]{total_gpu.days} days and {int(total_gpu.seconds / 3600)} hours[/] of GPU time.\n"
            )
            if useful_jobs:
                print(
                    f"The useful jobs ([green]{', '.join(useful_jobs)}[/] "
                    f"and their {len(parents) - len(useful_jobs)} parents) ran for: "
                    f"[bold red]{total_useful.days} days and {int(total_useful.seconds / 3600)} hours[/].\n"
                    f"Which means you wasted {100 * (1 - total_useful / total_running):.2f}% of your time.\n"
                )
            if skipped:
                print(
                    f"[italic white]This is an underestimation; {skipped} jobs "
                    f"({int(skipped*100/len(jobs))}%) were skipped due to missing metadata.[/]"
                )
