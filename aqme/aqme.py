#!/usr/bin/env python

###########################################################################################.
###########################################################################################
###                                                                                     ###
###  AQME is a tool that allows to carry out automated:                                 ###
###  (CSEARCH) Conformational searches and creation of COM files using RDKit and CREST  ###
###  (CMIN) Geometry refinement of initial conformers with xTB and ANI                  ###
###  (QCORR) Out put file processing from QM calculations and automated issue fixing,   ###
###  including imaginary freqs, spin contamination, isomerization issues and            ###
###  error terminations, among others                                                   ###
###  (QPREP) Use QM outputs, XYZ, SDF, PDB, JSON and other 3D formats to create input   ###
###  files for multiple QM programs                                                     ###
###  (QDESCP) Generate xTB molecular descriptors, including Boltzmann averaged values,  ###
###  to use in machine learning models                                                  ###
###                                                                                     ###
###########################################################################################
###                                                                                     ###
###  Authors: Shree Sowndarya S. V., Juan V. Alegre Requena                             ###
###                                                                                     ###
###  Please, report any bugs or suggestions to:                                         ###
###  svss@colostate.edu or jvalegre@unizar.es                                           ###
###                                                                                     ###
###########################################################################################
###########################################################################################.

import sys
import subprocess

from aqme.csearch import csearch
from aqme.cmin import cmin
from aqme.qprep import qprep
from aqme.utils import command_line_args
from aqme.qcorr import qcorr
from aqme.qdescp import qdescp


def main():
    """
    Main function of AQME, acts as the starting point when the program is run through a terminal
    """

    # load user-defined arguments from command line
    args = command_line_args()
    args.command_line = True

    if not args.csearch and not args.cmin and not args.qprep and not args.qcorr and not args.qdescp:
        print('x  No module was specified in the command line! (i.e. --csearch for conformer generation). If you did specify a module, check that you are using quotation marks when using options (i.e. --files "*.sdf").\n')

    # this is a dummy import just to warn the user if Open babel is not installed
    try:
        command_run_1 = ["obabel", "-H"]
        subprocess.run(command_run_1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("x  Open Babel is not installed! You can install the program with 'conda install -c conda-forge openbabel'")
        sys.exit()
    try: 
        from rdkit.Chem import AllChem as Chem
    except ModuleNotFoundError:
        print("x  RDKit is not installed! You can install the program with 'conda install -c conda-forge rdkit'")
        sys.exit()

    # CSEARCH
    if args.csearch:
        csearch(**vars(args))

    # CMIN
    if args.cmin:
        cmin(**vars(args))

    # QPREP
    if args.qprep:
        qprep(**vars(args))

    # QCORR
    if args.qcorr:
        qcorr(**vars(args))

    # QDESCP
    if args.qdescp:
        qdescp(**vars(args))


if __name__ == "__main__":
    main()
