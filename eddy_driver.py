#!/usr/bin/env python

from argparse import ArgumentParser
from subprocess import Popen, PIPE
import os.path as op
import os

import fsl


def runcmd(cmd):
    print(cmd)
#     try:
#         p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
#         outputs = p.communicate()
#     except Exception as e:
#         raise SystemExit("Command failed.\n CMD:{0}\n Error:{1}".format(cmd,
#                                                                         e))

def createacq(outp, n, *dirs):
    # Expects "dirs" in the following format:
    #   x y z b
    # Where, the first 3 args are the PE direction along these coords, and the
    # fourth is the strength of the PE pulse.
    try:
        assert(len(dirs) == n)
        dirs = "\n".join(d for d in dirs)
        return "fprintf '{0}' > {1}".format(dirs, outp)
    except AssertionError as e:
        raise SystemExit("Must be gradients for each B0 image.")


def createindex(outp, nvols, row):
    indx = ""
    for i in range(nvols):
        indx += str(row) + " "
    return "fprintf '{0}' > {1}".format(indx, outp)


def stripext(path):
    return op.join(op.dirname(path), op.basename(path).split('.')[0])


def driver(args=None):
    desc = """
           Wrapper around FSL's Eddy script, including topup and other necessary
           preprocessing steps for HCP-organized datasets. The Python-API for
           the enclosed functions will work on other data organizations too, but
           require more arguments. These instructions are taken from the
           following link on July 30, 2018:
           https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/eddy/UsersGuide"""
    parser = ArgumentParser("eddy_driver",description=desc)
    parser.add_argument("basedir", help="Directory of your HCP dataset.")
    parser.add_argument("subjid", help="ID of your subject.")
    parser.add_argument("--shell", help="which shell to process",
                        choices=[95, 96, 97], default=95)
    parser.add_argument("--dir", help="which shell to process",
                        choices=["LR", "RL"], default="LR")
    parser.add_argument("--exe", help="which version of eddy to run",
                        choices=["eddy", "eddy_cuda8.0", "eddy_openmp"],
                        default="eddy")

    results = parser.parse_args() if args is None else parser.parse_args(args)

    # Grab inputs
    bdir = results.basedir
    sid = results.subjid
    shell = results.shell
    direction = results.dir
    exe = results.exe

    #
    # Setup some helpful paths
    dir_curr = op.abspath(op.curdir)
    dir_data = op.join(bdir, sid, 'unprocessed', '3T', 'Diffusion')

    #
    # Extract B0 from volume of interest
    file_dwi = op.join(dir_data,
                       '{0}_3T_DWI_dir{1}_{2}.nii.gz'.format(sid, shell,
                                                             direction))
    file_dwi_bvec = stripext(file_dwi) + ".bvec"
    file_dwi_bval = stripext(file_dwi) + ".bval"
    file_dwi_b01 = op.join(dir_curr,
                           stripext(op.basename(file_dwi)) + '_b0.nii.gz')
    dwi_b01_loc = 0
    runcmd(fsl.fslroi(stripext(file_dwi),
                      stripext(file_dwi_b01),
                      dwi_b01_loc, dwi_b01_loc + 1))

    #
    # Extract B0 from complement volume
    _direction = "LR" if direction == "RL" else "RL"
    file_oth_dwi = op.join(dir_data,
                             '{0}_3T_DWI_dir{1}_{2}.nii.gz'.format(sid, shell,
                                                                   _direction))
    file_oth_b01 = op.join(dir_curr,
                           stripext(op.basename(file_oth_dwi)) + '_b0.nii.gz')
    runcmd(fsl.fslroi(stripext(file_oth_dwi),
                      stripext(file_oth_b01),
                      dwi_b01_loc, dwi_b01_loc + 1))

    #
    # Combines B0 volumes
    file_b0s_group = op.join(dir_curr,
                             stripext(op.basename(file_dwi)) + '_b0_grp.nii.gz')
    runcmd(fsl.fslmerge(stripext(file_b0s_group),
                        stripext(file_dwi_b01),
                        stripext(file_oth_b01)))

    #
    # Creates ACQ file for Topup and Eddy
    acqparams = ["1 0 0 0.05", "-1 0 0 0.05"]
    file_acq = op.join(dir_curr, "acqparams.txt")
    runcmd(createacq(file_acq,
                     2,
                     *acqparams))

    #
    # Runs Topup on the B0 volumes
    file_topup = op.join(dir_curr, "topup.nii.gz")
    file_hifi = op.join(dir_curr, "hifi.nii.gz")
    runcmd(fsl.topup(stripext(file_b0s_group),
                     file_acq,
                     stripext(file_topup),
                     stripext(file_hifi)))


    #
    # Takes mean from hifi volumes
    runcmd(fsl.fslmaths(stripext(file_hifi),
                        '-Tmean',
                        stripext(file_hifi)))

    #
    # Skull strips mean hifi volume
    file_hifi_brain = stripext(file_hifi) + "_brain.nii.gz"
    runcmd(fsl.bet(stripext(file_hifi),
                   stripext(file_hifi_brain),
                   '-m'))

    #
    # Create index file for Eddy
    with open(file_dwi_bval) as fhandle:
        data_dwi_bval = []
        for line in fhandle.readline():
            data_dwi_bval += line
    print(line)
    # get number of diffusion volumes
    runcmd(createindex('indexfile.txt', 4, 1))

    #
    # Run Eddy
    # create output file name
    runcmd(fsl.eddy(stripext(file_dwi),
                    stripext(file_hifi_brain),
                    file_acq,
                    file_index,
                    file_bvec,
                    file_bval,
                    stripext(file_topup),
                    stripext(file_out),
                    exe=exe))

    print("Eddy corrected file: {0}".format(file_eddy))


if __name__ == "__main__":
    driver()
