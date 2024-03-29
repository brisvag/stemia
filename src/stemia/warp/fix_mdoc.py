import click


@click.command()
@click.argument(
    "mdoc_dir", type=click.Path(exists=True, dir_okay=True, resolve_path=True)
)
@click.option(
    "-d", "--data-dir", type=click.Path(exists=True, dir_okay=True, resolve_path=True)
)
@click.option("--dates", is_flag=True, help="fix date format")
@click.option("--paths", is_flag=True, help="fix image paths")
def cli(mdoc_dir, data_dir, dates, paths):
    """Fix mdoc files to point to the right data and follow warp format."""
    import re
    from pathlib import Path

    from mdocfile.data_models import Mdoc
    from rich import print
    from rich.progress import track

    if not paths and not dates:
        raise ValueError("provide at least --paths or --dates")

    mdoc_dir = Path(mdoc_dir)
    if data_dir is None:
        data_dir = mdoc_dir
    else:
        data_dir = Path(data_dir)

    mdocs = [f for f in mdoc_dir.glob("*.mdoc") if not f.stem.endswith("_fixed")]
    failed = {}
    for md_file in track(mdocs, description="Fixing..."):
        mdoc = Mdoc.from_file(md_file)
        basename = mdoc.global_data.ImageFile.stem
        cleaned_sections = []
        for section in mdoc.section_data:
            if paths:
                # find correct file based on basename, zvalue and tilt angle
                glob = f"{basename}_{section.ZValue + 1:03}_{round(section.TiltAngle):.2f}_*.mrc"

                try:
                    newpath = next(data_dir.glob(glob))
                except StopIteration:
                    failed.setdefault(md_file, []).append(glob)
                    continue

                # replace path with the correct file (only name matters)
                section.SubFramePath = rf"X:\spoof\frames\{newpath.name}"

            if dates:
                # fix datetime to warp-compatible format (dd-MMM-yy)
                if section.DateTime is not None:
                    # crop year
                    section.DateTime = re.sub(r"-\d\d(\d\d)", r"-\1", section.DateTime)
                    # swap year and day if detectable american format

            cleaned_sections.append(section)

        mdoc.section_data = cleaned_sections

        with open(md_file.parent / (md_file.stem + "_fixed.mdoc"), "w+") as f:
            f.write(mdoc.to_string())

    if failed:
        print("No files matching the followings sections:")
        for k, v in failed.items():
            print(k.name, ":")
            print("\n- ".join(v))
