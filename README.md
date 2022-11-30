# STEMIA

**S**cripts and **T**ools for **E**lectron **M**icroscopy **I**mage **A**nalysis.

This is a simple personal collection of (sometimes...) useful scripts and tools for cryoem/cryoet.

## Installation

```bash
pip install stemia
```

## Tools

Everything is accessible through the main command line interface `stemia`. Try `stemia -h`.

### stemia aretomo aln2xf

```
Usage: stemia aretomo aln2xf [OPTIONS] ALN_FILE

  Convert AreTomo `aln` file to imod `xf` format.

Options:
  -f, --overwrite  overwrite existing output
  --help           Show this message and exit.
```

### stemia aretomo batch_warp

```
Usage: stemia aretomo batch_warp [OPTIONS] WARP_DIR

  Run aretomo in batch on data preprocessed in warp.

  Needs to be ran after imod stacks were generated. Requires ccderaser and
  AreTomo. Assumes the default Warp directory structure with generated imod
  stacks. Some warp xml files may be updated to disable too dark images.

Options:
  -m, --mdoc-dir PATH
  -o, --output-dir PATH           output directory for all the processing. If
                                  None, defined as warp_dir/aretomo
  -d, --dry-run                   only print some info, without running the
                                  commands.
  -v, --verbose                   print individual commands
  -j, --just TEXT                 quickly reconstruct just this tomogram with
                                  a simple setup. Useful for testing and to
                                  estimate sample thickness
  -t, --thickness INTEGER         unbinned thickness of the SAMPLE (ice or
                                  lamella); the reconstruction will be 20%
                                  thicker, but this will be used for alignment
  -b, --binning INTEGER           binning for aretomo reconstruction (relative
                                  to warp binning)
  -a, --tilt-axis FLOAT           starting tilt axis for AreTomo, if any
  -p, --patches INTEGER           number of patches for local alignment in
                                  aretomo (NxN)
  -f, --overwrite                 overwrite any previous existing run
  --train                         whether to train a new denosing model
  --topaz-patch-size INTEGER      patch size for denoising in topaz.
  --start-from [fix|align|reconstruct|stack_halves|reconstruct_halves|denoise]
                                  use outputs from a previous run, starting
                                  processing at this step
  --stop-at [fix|align|reconstruct|stack_halves|reconstruct_halves|denoise]
                                  terminate processing after this step
  --ccderaser TEXT                command for ccderaser
  --aretomo TEXT                  command for aretomo
  --help                          Show this message and exit.
```

### stemia aretomo batch

```
Usage: stemia aretomo batch [OPTIONS]

  Run AreTomo on a full directory.

Options:
  --help  Show this message and exit.
```

### stemia cryosparc csplot

```
Usage: stemia cryosparc csplot [OPTIONS] JOB_DIR

  Read a cryosparc job directory and plot interactively any column.

  All the related data from parent jobs will also be loaded. An interactive
  ipython shell will be opened with data loaded into a pandas dataframe.

  JOB_DIR:     a cryosparc job directory.

Options:
  --drop-na         drop rows that contain NaN values (e.g: micrographs with
                    no particles)
  --no-particles    do not read particles data
  --no-micrographs  do not read micrographs data
  --help            Show this message and exit.
```

### stemia cryosparc generate_tilt_angles

```
Usage: stemia cryosparc generate_tilt_angles [OPTIONS] STAR_FILE TILT_ANGLE
                                             TILT_AXIS

  Generate angle priors for a tilted dataset.

  Read a Relion STAR_FILE with in-plane angles and generate priors for rot and
  tilt angles based on a TILT_ANGLE around a TILT_AXIS.

Options:
  -r, --radians           Provide angles in radians instead of degrees
  -o, --star-output FILE  where to put the updated version of the star file
                          [default: <STAR_FILE>_tilted.star]
  -f, --overwrite         overwrite output if exists
  --help                  Show this message and exit.
```

### stemia image center_filament

```
Usage: stemia image center_filament [OPTIONS] INPUT [OUTPUT]

  Center an mrc image (stack) containing filament(s).

  Can update particles in a RELION .star file accordingly. If OUTPUT is not
  given, default to INPUT_centered.mrc

Options:
  -s, --update-star FILE        a RELION .star file to update with new
                                particle positions
  -o, --star-output FILE        where to put the updated version of the star
                                file. Only used if -s is passed [default:
                                STARFILE_centered.star]
  --update-by [class|particle]  whether to update particle positions by
                                classes or 1 by 1. Only used if -s is passed
                                [default: class]
  -f, --overwrite               overwrite output if exists
  -n, --n-filaments INTEGER     number of filaments on the image  [default: 2]
  -p, --percentile INTEGER      percentile for binarisation  [default: 85]
  --help                        Show this message and exit.
```

### stemia image extract_z_snapshots

```
Usage: stemia image extract_z_snapshots [OPTIONS] [INPUTS]...

  Grab z slices at regular intervals from a tomogram as jpg images.

  INPUTS: any number of paths of volume images

Options:
  -o, --output-dir PATH
  -s, --slices INTEGER   number of equidistant slices to extract
  --keep-extrema         whether to keep slices at z=0 and z=-1 (if false,
                         slices is reduced by 2)
  --average INTEGER      number of slices to average over
  --axis INTEGER         axis along which to do the slicing
  --help                 Show this message and exit.
```

### stemia image flip_z

```
Usage: stemia image flip_z [OPTIONS] STAR_PATH

  Flip the z axis for particles in a RELION star file.

  STAR_PATH: star file to flip along z

  Assumes all tomograms have the same shape.

Options:
  -o, --output FILE
  -m, --mrc_path FILE
  --star_pixel_size FLOAT
  --mrc_pixel_size FLOAT
  --z_shape INTEGER
  --help                   Show this message and exit.
```

### stemia image rescale

```
Usage: stemia image rescale [OPTIONS] INPUT OUTPUT TARGET_PIXEL_SIZE

  Rescale an mrc image to the specified pixel size.

  TARGET_PIXEL_SIZE: target pixel size in Angstrom

Options:
  --input-pixel-size FLOAT  force input pizel size and ignore mrc header
  -f, --overwrite           overwrite output if exists
  --help                    Show this message and exit.
```

### stemia warp fix_mdoc

```
Usage: stemia warp fix_mdoc [OPTIONS] DATA_DIR

  Fix mdoc files to point to the right data.

Options:
  --help  Show this message and exit.
```

### stemia warp offset_angle

```
Usage: stemia warp offset_angle [OPTIONS] [WARP_DIR]

  Offset tilt angles in warp xml files.

Options:
  --help  Show this message and exit.
```

### stemia warp parse_xml

```
Usage: stemia warp parse_xml [OPTIONS] XML_FILE

  Parse a warp xml file and print its content.

Options:
  --help  Show this message and exit.
```

### stemia warp prepare_isonet

```
Usage: stemia warp prepare_isonet [OPTIONS] WARP_DIR ISO_STAR

  Update an isonet starfile with preprocessing data from warp.

Options:
  --help  Show this message and exit.
```

### stemia warp summarize

```
Usage: stemia warp summarize [OPTIONS] [WARP_DIR]

  Summarize the state of a Warp project.

  Reports for each tilt series: - discarded: number of discarded tilts -
  total: total number oftilts in raw data - stacked: number of image slices in
  imod output directory - mismatch: whether stacked != (total - discarded) -
  resolution: estimated resolution if processed

Options:
  --help  Show this message and exit.
```

### stemia warp preprocess_serialem

```
Usage: stemia warp preprocess_serialem [OPTIONS] RAW_DATA_DIR

  Prepare and unpack data from sterialEM for Warp.

  You must be in a new directory for this to work; new files will be placed
  there with the same name as the original tifs.

  RAW_DATA_DIR: the directory containing the raw data

Options:
  --help  Show this message and exit.
```
