######################################################.
#          This file stores functions used           #
#                in multiple modules                 #
######################################################.

import os
import sys
import getopt
import numpy as np
import glob
import yaml
import pandas as pd
from pathlib import Path
from rdkit.Chem.rdMolAlign import GetBestRMS
from rdkit.Chem.rdmolops import RemoveHs
from rdkit import Geometry
from rdkit.Chem import Mol
from rdkit.Chem import AllChem as Chem
from aqme.argument_parser import set_options, var_dict
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")


def periodic_table():
	items = """X
			H                                                                                                  He
			Li Be  B                                                                             C   N   O   F  Ne
			Na Mg Al                                                                            Si   P   S  Cl  Ar
			K Ca Sc                                           Ti  V Cr Mn Fe Co Ni Cu  Zn  Ga  Ge  As  Se  Br  Kr
			Rb Sr  Y                                           Zr Nb Mo Tc Ru Rh Pd Ag  Cd  In  Sn  Sb  Te   I  Xe
			Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta  W Re Os Ir Pt Au  Hg  Tl  Pb  Bi  Po  At  Rn
			Fr Ra Ac Th Pa  U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Uub Uut Uuq Uup Uuh Uus Uuo
			"""
	periodic_table = items.replace("\n", " ").strip().split()
	periodic_table[0] = ""

	return periodic_table


# load paramters from yaml file
def load_from_yaml(self):
	"""
	Loads the parameters for the calculation from a yaml if specified. Otherwise
	does nothing.
	"""

	txt_yaml = f'\no  Importing AQME parameters from {self.varfile}'
	error_yaml = False
	# Variables will be updated from YAML file
	try:
		if os.path.exists(self.varfile):
			if os.path.splitext(self.varfile)[1] in [".yaml",".yml",".txt"]:
				with open(self.varfile, "r") as file:
					try:
						param_list = yaml.load(file, Loader=yaml.SafeLoader)
					except yaml.scanner.ScannerError:
						txt_yaml = f'\nx  Error while reading {self.varfile}. Edit the yaml file and try again (i.e. use ":" instead of "=" to specify variables)'
						error_yaml = True
		if not error_yaml:
			for param in param_list:
				if hasattr(self, param):
					if getattr(self, param) != param_list[param]:
						setattr(self, param, param_list[param])

	except UnboundLocalError:
		txt_yaml = "\nx  The specified yaml file containing parameters was not found! Make sure that the valid params file is in the folder where you are running the code."

	return self,txt_yaml


# class for logging
class Logger:
	"""
	Class that wraps a file object to abstract the logging.
	"""

	# Class Logger to writargs.input.split('.')[0] output to a file
	def __init__(self, filein, append, suffix="dat"):
		self.log = open(f"{filein}_{append}.{suffix}", "w")

	def write(self, message):
		"""
		Appends a newline character to the message and writes it into the file.

		Parameters
		----------
		message : str
		   Text to be written in the log file.
		"""
		self.log.write(f"{message}\n")
		print(f"{message}\n")

	def fatal(self, message):
		"""
		Writes the message to the file. Closes the file and raises an error exit

		Parameters
		----------
		message : str
		   text to be written in the log file.
		"""
		self.write(message)
		self.finalize()
		raise SystemExit(1)

	def finalize(self):
		"""
		Closes the file
		"""
		self.log.close()


def creation_of_dup_csv_cmin(cmin):

	"""
	Generates a pandas.DataFrame object with the appropiate columns for the
	conformational search and the minimization.

	Parameters
	----------
	cmin : str
		Minimization method. Current valid methods are: ['xtb','ani']

	Returns
	-------
	pandas.DataFrame
	"""

	# Boolean aliases from args
	is_xtb = cmin == "xtb"
	is_ani = cmin == "ani"

	# column blocks definitions

	xtb_columns = [
		"xTB-Initial-samples",
		"xTB-energy-window",
		"xTB-initial_energy_threshold",
		"xTB-RMSD-and-energy-duplicates",
		"xTB-Unique-conformers",
	]
	ANI_columns = [
		"ANI-Initial-samples",
		"ANI-energy-window",
		"ANI-initial_energy_threshold",
		"ANI-RMSD-and-energy-duplicates",
		"ANI-Unique-conformers",
	]
	end_columns = ["CMIN time (seconds)", "Overall charge"]

	# Check Minimization Method
	if is_ani:
		columns = ANI_columns
	if is_xtb:  # is_ani and is_xtb will not happen, but this is what was written
		columns = xtb_columns

	columns += end_columns
	return pd.DataFrame(columns=columns)


def move_file(destination, source, file):
	"""
	Moves files from the source folder to the destination folder and creates
	the destination folders when needed.

	Parameters
	----------
	destination : str
		Path to the destination folder
	src : str
		Path to the source folder
	file : str
		Full name of the file (file + extension)
	"""

	destination.mkdir(exist_ok=True, parents=True)
	filepath = source / file
	try:
		filepath.rename(destination / file)
	except FileExistsError:
		filepath.replace(destination / file)


def get_info_input(file):
	"""
	Takes an input file and retrieves the coordinates of the atoms and the
	total charge.

	Parameters
	----------
	file : str or pathlib.Path
		A path pointing to a valid .com or .gjf file

	Returns
	-------
	coordinates : list
		A list of strings (without \\n) that contain the xyz coordinates of the .gjf or .com file
	charge : str
		A str with the number corresponding to the total charge of the .com or .gjf file
	"""

	with open(file, "r") as input_file:
		input_lines = input_file.readlines()

	_iter = input_lines.__iter__()

	line = ""
	# input for Gaussian calculations
	if str(file).split(".")[1] in ["com", "gjf"]:

		# Find the command line
		while "#" not in line:
			line = next(_iter)

		# in case the keywords are distributed in multiple lines
		while len(line.split()) > 0:
			line = next(_iter)

		# pass the title lines
		_ = next(_iter)
		while line:
			line = next(_iter).strip()

		# Read charge and multiplicity
		charge, mult = next(_iter).strip().split()

		# Store the atom types and coordinates until next empty line.
		atoms_and_coords = []
		line = next(_iter).strip()
		while line:
			atoms_and_coords.append(line.strip())
			line = next(_iter).strip()

	# input for ORCA calculations
	if str(file).split(".")[1] == ".inp":

		# Find the line with charge and multiplicity
		while "* xyz" not in line or "* int" not in line:
			line = next(_iter)

		# Read charge and multiplicity
		charge = line.strip().split()[-2]

		# Store the coordinates until next *
		atoms_and_coords = []
		line = next(_iter).strip()
		while len(line.split()) > 1:
			atoms_and_coords.append(line.strip())
			line = next(_iter).strip()
	return atoms_and_coords, charge, mult


def smi_to_mol(
	smi,
	program,
	log
):
	smi = smi.split(".")

	if len(smi) > 1:
		if program not in ["crest"]:
			log.write("\nx  Program not supported for conformer generation of complexes! Specify: program='crest' for complexes")
			log.finalize()
			sys.exit()

		mol = nci_ts_mol(smi)

	else:
		params = Chem.SmilesParserParams()
		params.removeHs = False
		mol = Chem.MolFromSmiles(smi[0], params)
		Chem.EmbedMolecule(mol)

	return mol


def nci_ts_mol(smi):
	'''
	Set mol objects and their corresponding constraints
	'''

	molsH = []
	mols = []
	for m in smi:
		mols.append(Chem.MolFromSmiles(m))
		molsH.append(Chem.AddHs(Chem.MolFromSmiles(m)))

	for m in molsH:
		Chem.EmbedMultipleConfs(m, numConfs=1)
	for m in mols:
		Chem.EmbedMultipleConfs(m, numConfs=1)

	coord = [0.0, 0.0, 5.0]
	molH = molsH[0]
	for fragment in molsH[1:]:
		offset_3d = Geometry.Point3D(coord[0], coord[1], coord[2])
		molH = Chem.CombineMols(molH, fragment, offset_3d)
		coord[1] += 5
		Chem.SanitizeMol(molH)

	coord = [0.0, 0.0, 5.0]
	mol = mols[0]
	for fragment in mols[1:]:
		offset_3d = Geometry.Point3D(coord[0], coord[1], coord[2])
		mol = Chem.CombineMols(mol, fragment, offset_3d)
		coord[1] += 5
	mol = Chem.AddHs(mol)
	Chem.SanitizeMol(mol)

	atom_map = []
	for atom in mol.GetAtoms():
		atom_map.append(atom.GetAtomMapNum())

	max_map = max(atom_map)
	for a in mol.GetAtoms():
		if a.GetSymbol() == "H":
			max_map += 1
			a.SetAtomMapNum(int(max_map))

	Chem.ConstrainedEmbed(mol, molH)

	return mol


def rules_get_charge(mol, args, type):
	"""
	Automatically sets the charge for metal complexes
	"""

	C_group = ["C", "Se", "Ge"]
	N_group = ["N", "P", "As"]
	O_group = ["O", "S", "Se"]
	F_group = ["Cl", "Br", "I"]

	M_ligands, N_carbenes, bridge_atoms, neighbours = [], [], [], []
	charge_rules = np.zeros(len(mol.GetAtoms()), dtype=int)
	neighbours, metal_found = [], False
	for i, atom in enumerate(mol.GetAtoms()):
		# get the neighbours of metal atom and calculate the charge of metal center + ligands
		if atom.GetIdx() in args.metal_idx:
			metal_found = True
			charge_idx = args.metal_idx.index(atom.GetIdx())
			neighbours = atom.GetNeighbors()
			charge_rules[i] = args.metal_oxi[charge_idx]
			for neighbour in neighbours:
				M_ligands.append(neighbour.GetIdx())
				if neighbour.GetTotalValence() == 4:
					if neighbour.GetSymbol() in C_group:
						carbene_like = False
						bridge_ligand = False
						for inside_neighbour in neighbour.GetNeighbors():
							if inside_neighbour.GetSymbol() in N_group:
								if inside_neighbour.GetTotalValence() == 4:
									for N_neighbour in inside_neighbour.GetNeighbors():
										# this option detects bridge ligands that connect two metals such as M--CN--M
										# we use I since the M is still represented as I at this point
										if N_neighbour.GetSymbol() == "I":
											bridge_ligand = True
											bridge_atoms.append(
												inside_neighbour.GetIdx()
											)
									if not bridge_ligand:
										carbene_like = True
										N_carbenes.append(inside_neighbour.GetIdx())
						if not carbene_like:
							charge_rules[i] = charge_rules[i] - 1
				elif neighbour.GetTotalValence() == 3:
					if neighbour.GetSymbol() in N_group:
						charge_rules[i] = charge_rules[i] - 1
				elif neighbour.GetTotalValence() == 2:
					if neighbour.GetSymbol() in O_group:
						nitrone_like = False
						for inside_neighbour in neighbour.GetNeighbors():
							if inside_neighbour.GetSymbol() in N_group:
								nitrone_like = True
						if not nitrone_like:
							charge_rules[i] = charge_rules[i] - 1

				elif neighbour.GetTotalValence() == 1:
					if neighbour.GetSymbol() in F_group:
						charge_rules[i] = charge_rules[i] - 1
		else:
			charge_rules[i] = atom.GetFormalCharge()
	# recognizes charged N and O atoms in metal ligands (added to the first metal of the list as default)
	# this group contains atoms that do not count as separate charge groups (i.e. N from Py ligands)
	if len(neighbours) > 0:
		invalid_charged_atoms = M_ligands + N_carbenes + bridge_atoms
		for atom in mol.GetAtoms():
			if atom.GetIdx() not in invalid_charged_atoms:
				if atom.GetSymbol() in N_group:
					if atom.GetTotalValence() == 4:
						charge_rules[0] = charge_rules[0] + 1
				if atom.GetSymbol() in O_group:
					if atom.GetTotalValence() == 1:
						charge_rules[0] = charge_rules[0] - 1

	if metal_found:
		if type == "csearch":
			return np.sum(charge_rules)
		if type == "cmin":
			return charge_rules

	# for organic molecules when using a list containing organic and organometallics molecules mixed
	else:
		charge = Chem.GetFormalCharge(mol)
		if type == "csearch":
			return charge, metal_found
		if type == "cmin":
			return [charge], metal_found


def substituted_mol(self, mol, checkI):
	"""
	Returns a molecule object in which all metal atoms specified in args.metal_atoms
	are replaced by Iodine and the charge is set depending on the number of
	neighbors.

	"""

	Neighbors2FormalCharge = dict()
	for i, j in zip(range(2, 9), range(-3, 4)):
		Neighbors2FormalCharge[i] = j

	for atom in mol.GetAtoms():
		symbol = atom.GetSymbol()
		if symbol in self.args.metal_atoms:
			self.args.metal_sym[self.args.metal_atoms.index(symbol)] = symbol
			self.args.metal_idx[self.args.metal_atoms.index(symbol)] = atom.GetIdx()
			self.args.complex_coord[self.args.metal_atoms.index(symbol)] = len(
				atom.GetNeighbors()
			)
			if checkI == "I":
				atom.SetAtomicNum(53)
				n_neighbors = len(atom.GetNeighbors())
				if n_neighbors > 1:
					formal_charge = Neighbors2FormalCharge[n_neighbors]
					atom.SetFormalCharge(formal_charge)

	return self.args.metal_idx, self.args.complex_coord, self.args.metal_sym


def getDihedralMatches(mol, heavy):
	# this is rdkit's "strict" pattern
	pattern = r"*~[!$(*#*)&!D1&!$(C(F)(F)F)&!$(C(Cl)(Cl)Cl)&!$(C(Br)(Br)Br)&!$(C([CH3])([CH3])[CH3])&!$([CD3](=[N,O,S])-!@[#7,O,S!D1])&!$([#7,O,S!D1]-!@[CD3]=[N,O,S])&!$([CD3](=[N+])-!@[#7!D1])&!$([#7!D1]-!@[CD3]=[N+])]-!@[!$(*#*)&!D1&!$(C(F)(F)F)&!$(C(Cl)(Cl)Cl)&!$(C(Br)(Br)Br)&!$(C([CH3])([CH3])[CH3])]~*"
	qmol = Chem.MolFromSmarts(pattern)
	matches = mol.GetSubstructMatches(qmol)

	# these are all sets of 4 atoms, uniquify by middle two
	uniqmatches = []
	seen = set()
	for (a, b, c, d) in matches:
		if (b, c) not in seen and (c, b) not in seen:
			if heavy:
				if (
					mol.GetAtomWithIdx(a).GetSymbol() != "H"
					and mol.GetAtomWithIdx(d).GetSymbol() != "H"
				):
					seen.add((b, c))
					uniqmatches.append((a, b, c, d))
			if not heavy:
				if (
					mol.GetAtomWithIdx(c).GetSymbol() == "C"
					and mol.GetAtomWithIdx(d).GetSymbol() == "H"
				):
					pass
				else:
					seen.add((b, c))
					uniqmatches.append((a, b, c, d))
	return uniqmatches


def set_metal_atomic_number(mol, metal_idx, metal_sym):
	"""
	Changes the atomic number of the metal atoms using their indices.

	Parameters
	----------
	mol : rdkit.Chem.Mol
		RDKit molecule object
	metal_idx : list
		sorted list that contains the indices of the metal atoms in the molecule
	metal_sym : list
		sorted list (same order as metal_idx) that contains the symbols of the metals in the molecule
	"""

	for atom in mol.GetAtoms():
		if atom.GetIdx() in metal_idx:
			re_symbol = metal_sym[metal_idx.index(atom.GetIdx())]
			atomic_number = periodic_table().index(re_symbol)
			atom.SetAtomicNum(atomic_number)


def get_conf_RMS(mol1, mol2, c1, c2, heavy, max_matches_rmsd):
	"""
	Takes in two rdkit.Chem.Mol objects and calculates the RMSD between them.
	(As side efect mol1 is left in the aligned state, if heavy is specified
	the side efect will not happen)

	Parameters
	----------
	mol1 : rdkit.Chem.Mol
		Probe molecule
	mol2 : rdkit.Chem.Mol
		Target molecule. The probe is aligned to the target to compute the RMSD
	c1 : int
		Conformation of mol1 to use for the RMSD
	c2 : int
		Conformation of mol2 to use for the RMSD
	heavy : bool
		If True it will ignore the H atoms when computing the RMSD
	max_matches_rmsd : int
		the max number of matches found in a SubstructMatch()

	Returns
	-------
	float
		Returns the best RMSD found
	"""

	if heavy:
		mol1 = RemoveHs(mol1)
		mol2 = RemoveHs(mol2)
	return GetBestRMS(mol1, mol2, c1, c2, maxMatches=max_matches_rmsd)


def command_line_args():
	'''
	Load default and user-defined arguments specified through command lines. Arrguments are loaded as a dictionary
	'''
	
	# First, create dictionary with user-defined arguments
	kwargs = {}
	available_args = ['help']
	bool_args = [
		"verbose",
		"csearch",
		"cmin",
		"qprep",
		"qcorr",
		"qstat",
		"qpred",
		"metal_complex",
		"time",
		"heavyonly",
		"cregen",
		"lowest_only",
		"lowest_n",
		"chk",
		"dup",
		"fullcheck",
		"rot_dihedral",
		"nmr_online",
		"qsub",
		"qsub_ana"]

	for arg in var_dict:
		if arg in bool_args:
			available_args.append(f'{arg}')
		else:
			available_args.append(f'{arg} =')

	try:
		opts,_ = getopt.getopt(sys.argv[1:], 'h', available_args)
	except getopt.GetoptError as err:
		print(err)
		sys.exit()
	
	for arg,value in opts:
		if arg.find('--') > -1:
			arg_name = arg.split('--')[1].strip()
		elif arg.find('-') > -1:
			arg_name = arg.split('-')[1].strip()
		if arg_name in bool_args:
			value = True
		if value == 'None':
			value = None
		if arg_name in ("h", "help"):
			print('o  AQME is installed correctly! For more information about the available options, see the documentation in https://github.com/jvalegre/aqme')
			sys.exit()
		else:
			kwargs[arg_name] = value
	
	# Second, load all the default variables as an "add_option" object
	args = load_variables(kwargs,'command')

	return args


def load_variables(kwargs,aqme_module):
	'''
	Load default and user-defined variables
	'''

	# first, load default values and options manually added to the function
	self = set_options(kwargs)

	# this part loads variables from yaml files (if varfile is used)
	txt_yaml = ''
	if self.varfile is not None:
		self,txt_yaml = load_from_yaml(self)
	
	if aqme_module != 'command':
		self.initial_dir = Path(os.getcwd())
		self.w_dir_main = Path(self.w_dir_main)
		if self.isom_type is not None:
			self.isom_inputs = Path(self.isom_inputs)

		# go to working folder and detect files
		error_setup = False
		try:
			os.chdir(self.w_dir_main)
		except FileNotFoundError:
			txt_yaml += '\nx  The PATH specified as input in the w_dir_main option might be invalid!'
			error_setup = True
		
		if error_setup:
			self.w_dir_main = Path(os.getcwd())

		if not isinstance(self.files, list):
			if not isinstance(self.files, Mol):
				self.files = glob.glob(self.files)
			else:
				self.files = [self.files]

		# start a log file to track the QCORR module
		logger_1, logger_2 = 'AQME', 'data'
		if aqme_module == 'qcorr':
			# detects cycle of analysis (0 represents the starting point)
			self.round_num,self.resume_qcorr = check_run(self.w_dir_main)
			logger_1 = 'QCORR-run'
			logger_2 = f'{str(self.round_num)}'

		elif aqme_module == 'csearch':
			logger_1 = 'CSEARCH'

		elif aqme_module == 'qprep':
			logger_1 = 'QPREP'
		
		if txt_yaml not in ['', f'\no  Importing AQME parameters from {self.varfile}', "\nx  The specified yaml file containing parameters was not found! Make sure that the valid params file is in the folder where you are running the code.\n"]:
			self.log = Logger(self.w_dir_main / logger_1,logger_2)
			self.log.write(txt_yaml)
			error_setup = True

		if not error_setup:
			if not self.command_line:
				self.log = Logger(self.w_dir_main / logger_1,logger_2)
			else:
				# prevents errors when using command lines and running to remote directories
				path_command = Path(f'{os.getcwd()}')
				self.log = Logger(path_command / logger_1,logger_2)

			if self.command_line:
				self.log.write(f"\nCommand line used in AQME: aqme {' '.join([str(elem) for elem in sys.argv[1:]])}")

			if aqme_module in ['qcorr','qprep']:
				if len(self.files) == 0:
					self.log.write(f'x  There are no output files in {self.w_dir_main}.')
					error_setup = True

		if error_setup:
			# this is added to avoid path problems in jupyter notebooks
			self.log.finalize()
			os.chdir(self.initial_dir)
			sys.exit()
	
	return self


def read_file(initial_dir, w_dir, file):
	"""
	Reads through a file and retrieves a list with all the lines.
	"""

	os.chdir(w_dir)
	outfile = open(file, "r")
	outlines = outfile.readlines()
	outfile.close()
	os.chdir(initial_dir)

	return outlines


def QM_coords(outlines,min_RMS,n_atoms,program):
	'''
	Retrieves atom types and coordinates from QM output files
	'''

	atom_types,cartesians = [],[]
	per_tab = periodic_table()
	count_RMS = -1

	if program == 'gaussian':
		if min_RMS > -1:
			for i,line in enumerate(outlines):
				if line.find('Standard orientation:') > -1:
					count_RMS += 1
				if count_RMS == min_RMS:
					range_lines = [i+5,i+5+n_atoms]
					break
		else:
			for i in reversed(range(len(outlines))):
				if outlines[i].find('Standard orientation:') > -1:
					range_lines = [i+5,i+5+n_atoms]
					break

		for i in range(range_lines[0],range_lines[1]):
			massno = int(outlines[i].split()[1])
			if massno < len(per_tab):
				atom_symbol = per_tab[massno]
			else:
				atom_symbol = "XX"
			atom_types.append(atom_symbol)
			cartesians.append([float(outlines[i].split()[3]), float(outlines[i].split()[4]), float(outlines[i].split()[5])])

	return atom_types,cartesians


def cclib_atoms_coords(cclib_data):
	"""
	Function to convert atomic numbers and coordinate arrays from cclib into
	a format compatible with QPREP.
	"""
	atom_numbers = cclib_data["atoms"]["elements"]["number"]
	atom_types = []
	per_tab = periodic_table()
	for atom_n in atom_numbers:
		if atom_n < len(per_tab):
			atom_symbol = per_tab[atom_n]
		else:
			atom_symbol = "XX"
		atom_types.append(atom_symbol)

	cartesians_array = cclib_data["atoms"]["coords"]["3d"]
	cartesians = [
		cartesians_array[i : i + 3] for i in range(0, len(cartesians_array), 3)
	]

	return atom_types, cartesians


def check_run(w_dir):
	"""
	Determines the folder where input files are gonna be generated in QCORR.
	"""

	if "unsuccessful_QM_outputs" in w_dir.as_posix():
		resume_qcorr = True
		for folder in w_dir.as_posix().replace("\\", "/").split("/"):
			if "run_" in folder:
				folder_count = int(folder.split("_")[1]) + 1
	else:
		input_folder = w_dir.joinpath("unsuccessful_QM_outputs/")
		resume_qcorr = False
		folder_count = 1

		if os.path.exists(input_folder):
			dir_list = os.listdir(input_folder)
			for folder in dir_list:
				if folder.find("run_") > -1:
					folder_count += 1

	return folder_count, resume_qcorr


def read_xyz_charge_mult(file):
	"""
	Reads charge and multiplicity from XYZ files. These parameters should be defined
	in the title lines as charge=X and mult=Y (i.e. FILENAME charge=1 mult=1 Eopt -129384.564)
	"""

	charge_xyz,mult_xyz = None,None
	# read charge and mult from xyz files
	with open(file, "r") as F:
		lines = F.readlines()
	for line in lines:
		for keyword in line.strip().split():
			if keyword.lower().find('charge') > -1:
				charge_xyz = int(keyword.split('=')[1])
			elif keyword.lower().find('mult') > -1:
				mult_xyz = int(keyword.split('=')[1])
			elif charge_xyz is not None and mult_xyz is not None:
				break

	if charge_xyz is None:
		charge_xyz = 0
	if mult_xyz is None:
		mult_xyz = 1

	return charge_xyz,mult_xyz


def mol_from_sdf_or_mol_or_mol2(input_file,module):
	"""
	mol object from SDF, MOL or MOL2 files
	"""

	if module == 'qprep':
		# using sanitize=False to avoid reading problems
		mols = Chem.SDMolSupplier(input_file, removeHs=False, sanitize=False)
		return mols

	if module == 'csearch':
		
		# using sanitize=True in this case, which is recommended for RDKit calculations
		filename = os.path.splitext(input_file)[0]
		extension = os.path.splitext(input_file)[1]

		if extension.lower() == ".pdb":
			input_file = f'{input_file.split(".")[0]}.sdf'
			extension = ".sdf"

		if extension.lower() == ".sdf":
			mols = Chem.SDMolSupplier(input_file, removeHs=False)
		elif extension.lower() == ".mol":
			mols = [Chem.MolFromMolFile(input_file, removeHs=False)]
		elif extension.lower() == ".mol2":
			mols = [Chem.MolFromMol2File(input_file, removeHs=False)]

		suppl = []
		for i, mol in enumerate(mols):
			suppl.append(mol)

		IDs, charges = [], []

		with open(input_file, "r") as F:
			lines = F.readlines()

		molecule_count = 0
		for i, line in enumerate(lines):
			if line.find(">  <ID>") > -1:
				ID = lines[i + 1].split()[0]
				IDs.append(ID)
			if line.find("M  CHG") > -1:
				charge_line = line.split("  ")
				charge = 0
				for j in range(4, len(charge_line)):
					if (j % 2) == 0:
						if j == len(charge_line) - 1:
							charge_line[j] = charge_line[j].split("\n")[0]
						charge += int(charge_line[j])
				charges.append(charge)
			if line.find("$$$$") > -1:
				molecule_count += 1
				if molecule_count != len(charges):
					charges.append(0)

		if len(IDs) == 0:
			if len(suppl) > 1:
				for i in range(len(suppl)):
					IDs.append(f"{filename}_{i+1}")
			else:
				IDs.append(filename)

		if len(charges) == 0:
			if len(suppl) > 1:
				for _ in suppl:
					charges.append(0)
			else:
				charges.append(0)

		return suppl, IDs, charges