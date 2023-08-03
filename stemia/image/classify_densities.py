import click


@click.command()
@click.argument('classes', nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def cli(classes):
    from pathlib import Path

    import mrcfile
    import numpy as np
    import pandas as pd
    from rich.progress import Progress
    from scipy.cluster.hierarchy import dendrogram, linkage

    from stemia.utils.image_processing import compute_dist_field, create_mask_from_field

    if not classes:
        return

    with mrcfile.open(classes[0], header_only=True) as mrc:
        shape = mrc.header[['nx', 'ny']].item()

    radius = min(shape) / 2
    dist_field = compute_dist_field(
        shape=shape,
        field_type='sphere',
    )
    mask = create_mask_from_field(
        field=dist_field,
        radius=radius * 0.6,
        padding=radius * 0.8,
    )

    field_squared = dist_field**2

    df = pd.DataFrame(columns=['total_density', 'radius_of_gyration'])
    df.index.name = 'image'
    with Progress() as progress:
        for cl in progress.track(classes, description='Reading data...'):
            data = mrcfile.read(cl)
            for idx, img in enumerate(progress.track(data, description='Calculating features...')):
                img_name = f'{Path(cl).stem}_{idx}'
                img -= img.min()
                img *= mask
                total_density = img.sum()
                gyr = np.sqrt(np.sum(field_squared * img))
                df.loc[img_name] = [total_density, gyr]

    Z = linkage(df.to_numpy(), 'centroid', optimal_ordering=True)
    from matplotlib import pyplot as plt
    fig = plt.figure(figsize=(25, 10))
    dn = dendrogram(Z)
    plt.savefig('classification.png')
    df.to_csv('classification.csv', sep='\t')
