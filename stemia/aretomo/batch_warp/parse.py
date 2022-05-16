from pathlib import Path, PureWindowsPath
import mdocfile
from xml.etree import ElementTree


def parse_data(progress, warp_dir, mdoc_dir=None, output_dir=None, just=None, train=False):
    imod_dir = warp_dir / 'imod'
    if not imod_dir.exists():
        raise FileNotFoundError('warp directory does not have an `imod` subdirectory')

    if just:
        mdocs = [Path(mdoc_dir) / (ts_name + '.mdoc') for ts_name in just]
    else:
        mdocs = sorted(list(Path(mdoc_dir).glob('*.mdoc')))

    if not mdocs:
        raise FileNotFoundError('could not find any mdoc files')

    odd_dir = warp_dir / 'average' / 'odd'
    even_dir = warp_dir / 'average' / 'even'

    tilt_series = []
    tilt_series_unprocessed = []

    for mdoc in progress.track(mdocs, description='Reading mdocs...'):
        df = mdocfile.read(mdoc)
        ts_name = df.image_file[0].name
        stack = imod_dir / ts_name / (ts_name + '.st')

        # skip if not preprocessed in warp
        if not stack.exists():
            tilt_series_unprocessed.append(ts_name)
            continue

        # extract even/odd paths
        tilts = [warp_dir / PureWindowsPath(tilt).name for tilt in df.sub_frame_path]
        odd = []
        even = []
        for tilt in tilts:
            xml = ElementTree.parse(tilt.with_suffix('.xml')).getroot()
            if xml.attrib['UnselectManual'] == 'True':
                continue

            odd.append(odd_dir / (tilt.stem + '.mrc'))
            even.append(even_dir / (tilt.stem + '.mrc'))

        if train:
            for img in odd + even:
                if not img.exists():
                    raise FileNotFoundError(img)

        # extract metadata from warp xmls (we assume the last xml has the same data as the others)
        for param in xml.find('OptionsCTF'):
            if param.get('Name') == 'BinTimes':
                bin = float(param.get('Value'))
            elif param.get('Name') == 'Voltage':
                kv = int(param.get('Value'))
            elif param.get('Name') == 'Cs':
                cs = float(param.get('Value'))
        for param in xml.find('CTF'):
            if param.get('Name') == 'Defocus':
                defocus = float(param.get('Value'))

        tilt_series.append({
            'name': ts_name,
            'stack': stack,
            'rawtlt': stack.with_suffix('.rawtlt'),
            # due to a quirk of aretomo, with_suffix is named wrong because all extensions are removed
            'aln': output_dir / (ts_name.partition('.')[0] + '.aln'),
            'fix': output_dir / (ts_name + '_fix.st'),
            'odd': odd,
            'even': even,
            'stack_odd': output_dir / (ts_name + '_odd.st'),
            'stack_even': output_dir / (ts_name + '_even.st'),
            'recon_odd': output_dir / 'odd' / (ts_name + '.mrc'),
            'recon_even': output_dir / 'even' / (ts_name + '.mrc'),
            'recon': output_dir / (ts_name + '.mrc'),
            'aretomo_kwargs': {
                'dose': df.exposure_dose[0],
                'px_size': df.pixel_spacing[0] * 2**bin,
                'cs': cs,
                'kv': kv,
                'defocus': defocus,
            }
        })

    return tilt_series, tilt_series_unprocessed
