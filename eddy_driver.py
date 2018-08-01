#!/usr/bin/env python

from argparse import ArgumentParser
from subprocess import Popen, PIPE
import nibabel as nib
import os.path as op
import os
import time
import fsl


def runcmd(cmd, verb=False):
    if verb:
        print("Running: " + cmd)
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()

    out = out.decode('utf-8')
    err = err.decode('utf-8')
    print "OUT = {0}".format(out)
    print "ERR = {0}".format(err)
    if len(err) > 0:
        raise SystemExit("Command failed.\n CMD:{0}\n Error:{1}".format(cmd,
                                                                        err))
    return out, err


def sanitizedwi(inp, outp):
    image_dwi = nib.load(inp)
    _data_shape = image_dwi.shape
    if any(dim % 2 for dim in _data_shape[:3]):
        _data_shape_clean = tuple([2*int(d/2) for d in _data_shape[:3]] +
                                  [_data_shape[3]])
        _data_image_clean = image_dwi.get_data()[:_data_shape_clean[0],
                                                 :_data_shape_clean[1],
                                                 :_data_shape_clean[2],
                                                 :]
        image_dwi_clean = nib.Nifti1Image(_data_image_clean,
                                          affine=image_dwi.affine,
                                          header=image_dwi.header)
        print "what"
        image_dwi_clean.update_header()
        nib.save(image_dwi_clean, outp)
        return outp
    return inp


def createacq(outp, n, *dirs):
    # Expects "dirs" in the following format:
    #   x y z b
    # Where, the first 3 args are the PE direction along these coords, and the
    # fourth is the strength of the PE pulse.
    try:
        assert(len(dirs) == n)
        dirs = "\n".join(d for d in dirs)
        return "printf '{0}' > {1}".format(dirs, outp)
    except AssertionError as e:
        raise SystemExit("Must be gradients for each B0 image.")


def createindex(outp, nvols, row):
    indx = " ".join(["1"] * nvols) + "\n"
    return "printf '{0}' > {1}".format(indx, outp)


def stripext(path):
    return op.join(op.dirname(path), op.basename(path).split('.')[0])


def hcpparser():
    desc = """
           Wrapper around FSL's Eddy script, including topup and other necessary
           preprocessing steps for HCP-organized datasets. The Python-API for
           the enclosed functions will work on other data organizations too, but
           require more arguments. These instructions are taken from the
           following link on July 30, 2018:
           https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/eddy/UsersGuide"""
    parser = ArgumentParser("eddy_driver",description=desc)
    parser.add_argument("basepath", help="Directory of your HCP dataset.")
    parser.add_argument("subjid", help="ID of your subject.")
    parser.add_argument("--output", help="output directory location if not CWD")
    parser.add_argument("--shell", help="which shell to process",
                        choices=[95, 96, 97], default=95)
    parser.add_argument("--dir", help="which shell to process",
                        choices=["LR", "RL"], default="LR")
    parser.add_argument("--exe", help="which version of eddy to run",
                        choices=["eddy", "eddy_cuda8.0", "eddy_openmp"],
                        default="eddy")
    parser.add_argument("--verbose", "-v", help="Toggles printing commands",
                        action="store_true")
    return parser


def hcpdriver(args=None):
    parser = hcpparser()
    results = parser.parse_args() if args is None else parser.parse_args(args)

    # Grab inputs
    bdir = results.basepath
    sid = results.subjid
    shell = results.shell
    direction = results.dir
    exe = results.exe
    verb = results.verbose

    # Create output directory, if needed
    cmd = "mkdir -p " + results.output if results.output is not None else None
    if cmd:
        runcmd(cmd, verb=verb)
    #
    # Setup some helpful paths
    dir_curr = op.abspath(results.output)
    dir_data = op.join(bdir, sid, 'unprocessed', '3T', 'Diffusion')
    file_dwi = op.join(dir_data,
                       '{0}_3T_DWI_dir{1}_{2}.nii.gz'.format(sid, shell,
                                                             direction))
    file_dwi_bvec = stripext(file_dwi) + ".bvec"
    file_dwi_bval = stripext(file_dwi) + ".bval"
    #
    # Sanitizes image volume if odd number in one direction
    file_dwi_clean = op.join(dir_curr,
                             stripext(op.basename(file_dwi)) + '_clean.nii.gz')
    file_dwi = sanitizedwi(file_dwi, file_dwi_clean)
    #
    # Extract B0 from volume of interest
    file_dwi_b01 = op.join(dir_curr,
                           stripext(op.basename(file_dwi)) + '_b0.nii.gz')
    dwi_b01_loc = 0
    runcmd(fsl.fslroi(stripext(file_dwi),
                      stripext(file_dwi_b01),
                      dwi_b01_loc, dwi_b01_loc + 1),
           verb=verb)

    #
    # Extract B0 from complement volume
    _direction = "LR" if direction == "RL" else "RL"
    file_oth_dwi = op.join(dir_data,
                           '{0}_3T_DWI_dir{1}_{2}.nii.gz'.format(sid, shell,
                                                                 _direction))
    file_oth_dwi_clean = op.join(dir_curr,
                                 stripext(op.basename(file_oth_dwi)) +\
                                 '_clean.nii.gz')
    file_oth_dwi = sanitizedwi(file_dwi, file_dwi_clean)

    file_oth_b01 = op.join(dir_curr,
                           stripext(op.basename(file_oth_dwi)) + '_b0.nii.gz')
    runcmd(fsl.fslroi(stripext(file_oth_dwi),
                      stripext(file_oth_b01),
                      dwi_b01_loc, dwi_b01_loc + 1),
           verb=verb)

    #
    # Combines B0 volumes
    file_b0s_group = op.join(dir_curr,
                             stripext(op.basename(file_dwi)) + '_b0_grp.nii.gz')
    runcmd(fsl.fslmerge(stripext(file_b0s_group),
                        stripext(file_dwi_b01),
                        stripext(file_oth_b01)),
           verb=verb)

    #
    # Creates ACQ file for Topup and Eddy
    # TODO: not hard code this at 2
    acqparams = ["1 0 0 0.05", "-1 0 0 0.05"]
    file_acq = op.join(dir_curr, "acqparams.txt")
    runcmd(createacq(file_acq,
                     2,
                     *acqparams),
           verb=verb)

    #
    # Runs Topup on the B0 volumes
    file_topup = op.join(dir_curr, "topup.nii.gz")
    file_hifi = op.join(dir_curr, "hifi.nii.gz")
    runcmd(fsl.topup(stripext(file_b0s_group),
                     file_acq,
                     stripext(file_topup),
                     stripext(file_hifi)),
           verb=verb)


    #
    # Takes mean from hifi volumes
    runcmd(fsl.fslmaths(stripext(file_hifi),
                        '-Tmean',
                        stripext(file_hifi)),
           verb=verb)

    #
    # Skull strips mean hifi volume
    file_hifi_brain = stripext(file_hifi) + "_brain.nii.gz"
    runcmd(fsl.bet(stripext(file_hifi),
                   stripext(file_hifi_brain),
                   '-m'),
           verb=verb)

    #
    # Create index file for Eddy
    with open(file_dwi_bval, 'r') as fhandle:
        data_dwi_bval = fhandle.read()
    n_bvals = len(data_dwi_bval.split(" ")) - 1
    file_index = op.join(dir_curr, "index.txt")
    runcmd(createindex(file_index,
                       n_bvals,
                       1),
           verb=verb)

    #
    # Run Eddy
    file_eddy = op.join(dir_curr,
                       stripext(op.basename(file_dwi)) + '_eddy.nii.gz')
    time1 = time.time()
    runcmd(fsl.eddy(stripext(file_dwi),
                    stripext(file_hifi_brain),
                    file_acq,
                    file_index,
                    file_dwi_bvec,
                    file_dwi_bval,
                    stripext(file_topup),
                    stripext(file_eddy),
                    exe=exe),
           verb=verb)
    time2 = time.time()
    print("Eddy corrected file: {0}".format(file_eddy))
    print("Time to Correct File : {0} seconds".format(time2-time1))

if __name__ == "__main__":
    hcpdriver()
