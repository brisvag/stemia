import click


@click.command()
@click.argument(
    "project_dirs",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=True, resolve_path=True),
)
def cli(project_dirs):
    """Print the total amount of time wasted on a project."""
    import json
    from datetime import timedelta
    from pathlib import Path

    from rich import print
    from rich.progress import Progress

    with Progress() as prog:
        for proj in prog.track(project_dirs, description="Reading projects..."):
            proj = Path(proj)
            total_time = timedelta(0)
            skipped = 0
            jobs = list(proj.glob("J*"))
            for job in prog.track(jobs, description="Reading jobs..."):
                job_meta = job / "job.json"
                if not job_meta.exists():
                    # print(f'Missing job metadata for {job.name}, skipping.')
                    skipped += 1
                    continue
                with open(job_meta) as f:
                    meta = json.load(f)

                start = meta["started_at"]
                if start is None:
                    # print(f'job {job.name} was not started, skipping')
                    skipped += 1
                    continue

                end = meta["completed_at"]
                if end is None:
                    end = meta["failed_at"]
                if end is None:
                    # print(f'job {job.name} was not finished, skipping')
                    skipped += 1
                    continue

                total_time += timedelta(milliseconds=end["$date"] - start["$date"])

            print(f"Time wasted on {proj.name}: {total_time}.")
            if skipped:
                print(
                    f"This is an underestimation; {skipped} jobs "
                    f"({int(skipped*100/len(jobs))}%) were skipped due to missing metadata."
                )
