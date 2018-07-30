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

    results = parser.parse_args() if args is None else parser.parse_args(args)

    bdir = results.basedir
    sid = results.subjid

    # get data file
    # create name for output file
    # get location of first b0 (or set the default to 0 1)
    runcmd(fsl.fslroi('dwidata', 'dwib0s', 0, 1))

    # get other b0 volumes in other directions
    # if other b0 volume exists:
    # create name for output file
    runcmd(fsl.fslmerge('alldwib0s', 'dwib0s', 'otherdwib0s'))

    # get all grad directions for these files, or default to reasonable value
    # create name for output file
    runcmd(createacq('acqfile.txt', 2, '0 -1 0 0.5', '0 1 0 0.5'))

    # create name for output files
    runcmd(fsl.topup('alldwib0s', 'acqfile.txt', 'topupoutput', 'hifi'))
    runcmd(fsl.fslmaths('hifi', '-Tmean', 'hifi'))
    runcmd(fsl.bet('hifi', 'hifi_brain', '-m'))

    # get row corresponding to main dwi image stack
    # get number of diffusion volumes
    runcmd(createindex('indexfile.txt', 4, 1))

    # get bvals
    # get bvecs
    # create output file name
    runcmd(fsl.eddy("dwi", "brain", "acq.txt", "ind.txt",
                    "bvec", "bval", "topup", "out", exe="eddy_cuda8.0"))


if __name__ == "__main__":
    driver()
