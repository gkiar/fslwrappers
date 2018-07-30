#!/usr/bin/env python

from argparse import ArgumentParser
from subprocess import Popen, PIPE
import os.path as op
import os


def bet(inp, outp, *flags):
    if len(flags):
        flags = " ".join([str(f) for f in flags])
    else:
        flags = ""

    return ("bet "
            "{0} "
            "{1} "
            "{2}".format(inp, outp, flags))


def eddy(dwi, brain, acq, ind, bvec, bval, topup, out, exe="eddy"):
    return ("{} ".format(exe) +
            "--imain={0} "
            "--mask={1} "
            "--acqp={2} "
            "--index={3} "
            "--bvecs={4} "
            "--bvals={5} "
            "--topup={6} "
            "--out={7}".format(dwi, brain, acq, ind, bvec, bval, topup, out))


def fslmaths(*args):
    # This isn't super helpful since fslmaths can do anything...
    return ("fslmaths "
            "{0}".format(" ".join([str(a) for a in args])))


def fslmerge(outp, *inps):
    try:
        assert(len(inps) > 1)
        inps = " ".join(str(i) for i in inps)
        return ("fslmerge "
                "-t {0} "
                "{1}".format(outp, inps))
    except AssertionError as e:
        raise SystemExit("Improper arguments provided. Pls read docs")


def fslroi(inp, outp, *loc):
    try:
        assert(len(loc) == 2 or len(loc) == 6)
        assert(all(type(l) == int for l in loc))
        loc = " ".join(str(l) for l in loc)
        return ("fslroi "
                "{0} "
                "{1} "
                "{2}".format(inp, outp, loc))
    except AssertionError as e:
        raise SystemExit("Improper arguments provided. Pls read docs")


def topup(b0s, acq, outp, bmask, mode="b02b0.cnf"):
    try:
        assert(all((not f.endswith(('.nii', '.nii.gz'))
                   for f in [b0s, outp, bmask])))
        return ("topup "
                "--imain={0} "
                "--datain={1} "
                "--config={4} "
                "--out={2} "
                "--iout={3}".format(b0s, acq, outp, bmask, mode))
    except AssertionError as e:
        raise SystemExit("Improper arguments provided. Pls read docs")
