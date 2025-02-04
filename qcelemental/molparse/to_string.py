import collections
from typing import Any, Dict, List, Tuple, Union

import numpy as np

from ..molutil import guess_connectivity
from ..physical_constants import constants


def to_string(
    molrec: Dict,
    dtype: str,
    units: str = None,
    *,
    atom_format: str = None,
    ghost_format: str = None,
    width: int = 17,
    prec: int = 12,
    return_data: bool = False,
) -> Union[str, Tuple[str, Dict]]:
    r"""Format a string representation of QM molecule.

    Parameters
    ----------
    molrec
        Psi4 json Molecule spec.
    dtype
        {"xyz", "cfour", "nwchem", "molpro", "orca", "turbomole", "qchem","madness"}
        Overall string format. Note that it's possible to request variations
        that don't fit the dtype spec so may not be re-readable (e.g., ghost
        and mass in nucleus label with ``'xyz'``).
        'cfour' forces nucleus label, ignoring atom_format, ghost_format
    units
        Units in which to write string. Usually ``Angstrom`` or ``Bohr``
        but may be any length unit.  There is not an option to write in
        intrinsic/input units. For ``dtype='xyz', units='Bohr'`` where the
        format doesn't have a slot to specify units, "au" is added so that
        readable as ``dtype='xyz+'``.
    atom_format
        General format is ``'{elem}'``. A format string that may contain fields
        'elea' (-1 will be ''), 'elez', 'elem', 'mass', 'elbl' in any
        arrangement. For example, if a format naturally uses element symbol
        and you want atomic number instead with mass info, too, pass
        ``'{elez}@{mass}'``. See `ghost_format` for handling field 'real'.
    ghost_format
        General format is ``'@{elem}'``. Like `atom_format`, but this formatter
        is used when `real=False`. To suppress ghost atoms, use `ghost_format=''`.
    width
        Field width for formatting coordinate float.
    prec
        Number of decimal places for formatting coordinate float.
    return_data
        Whether to return dictionary with additional info from the molrec that's
        not expressible in the string but may be of interest to the QC program.
        Note that field names are in QCSchema, not molrec, language.

    Returns
    -------
    str
        String representation of the molecule.
    str, dict
        When ``return_data=True``, return additionally a dictionary

          * keywords: key, value pairs for processing molecule info into options
          * fields: aspects of ``qcelemental.models.Molecule`` expressed into string *or* keywords.
            Model fields *not* listed are lost in QCSchema -> QC DSL translation.

    """

    # funits, fiutau = process_units(molrec)
    # molrec = self.to_dict(force_units=units, np_out=True)

    dtype = dtype.lower()

    default_units = {
        "xyz": "Angstrom",
        "xyz+": "Angstrom",
        "nglview-sdf": "Angstrom",
        "cfour": "Bohr",
        "gamess": "Bohr",
        "molpro": "Bohr",
        "nwchem": "Bohr",
        "orca": "Bohr",
        "psi4": "Bohr",
        "qchem": "Bohr",
        "terachem": "Bohr",
        "turbomole": "Bohr",
        "madness": "Bohr",  # madness by default reads au and optionally can read angs/angstrom
        "mrchem": "Bohr",
    }
    if dtype not in default_units:
        raise KeyError(f"dtype '{dtype}' not understood.")

    # Handle units
    if units is None:
        units = default_units[dtype]

    if molrec["units"] == "Angstrom" and units.capitalize() == "Angstrom":
        factor = 1.0
    elif molrec["units"] == "Angstrom" and units.capitalize() == "Bohr":
        if "input_units_to_au" in molrec:
            factor = molrec["input_units_to_au"]
        else:
            factor = 1.0 / constants.bohr2angstroms
    elif molrec["units"] == "Bohr" and units.capitalize() == "Angstrom":
        factor = constants.bohr2angstroms
    elif molrec["units"] == "Bohr" and units.capitalize() == "Bohr":
        factor = 1.0
    else:
        factor = constants.conversion_factor(molrec["units"], units)
    geom = np.asarray(molrec["geom"]).reshape((-1, 3)) * factor

    name = molrec.get("name", formula_generator(molrec["elem"]))
    tagline = """auto-generated by QCElemental from molecule {}""".format(name)

    class Data:
        fields: List[str] = ["atomic_numbers", "geometry", "symbols"]
        keywords: Dict[str, Any] = {}

        _dict_attrs: List[str] = ["fields", "keywords"]

        def to_dict(self) -> Dict:
            return {attr: getattr(self, attr) for attr in self._dict_attrs}

    data = Data()

    if dtype in ["xyz", "xyz+"]:
        # Notes
        # * if units not in umap (e.g., nm), can't be read back in by from_string()

        atom_format = "{elem}" if atom_format is None else atom_format
        ghost_format = "@{elem}" if ghost_format is None else ghost_format
        umap = {"bohr": "au", "angstrom": ""}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)
        nat = len(atoms)

        first_line = """{} {}""".format(str(nat), umap.get(units.lower(), units.lower()))
        smol = [first_line.rstrip()]
        smol.append(f"{int(molrec['molecular_charge'])} {molrec['molecular_multiplicity']} {name}")

        smol.extend(atoms)

    elif dtype == "orca":
        atom_format = "{elem}"
        ghost_format = "{elem}:"
        umap = {"bohr": "! Bohrs", "angstrom": "!"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        smol = []
        smol.append(umap[units.lower()])
        smol.append("")
        smol.append(f"*xyz {int(molrec['molecular_charge'])} {molrec['molecular_multiplicity']}")
        smol.extend(atoms)
        smol.append("*")

    elif dtype == "cfour":
        # Notes
        # * losing identity of ghost atoms. picked up again in basis formatting
        # * casting 'molecular_charge' to int
        # * no spaces at the beginning of 1st/comment line is important

        atom_format = "{elem}"
        ghost_format = "GH"
        # TODO handle which units valid
        umap = {"bohr": "bohr", "angstrom": "angstrom"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        smol = [tagline]
        smol.extend(atoms)

        data.fields.extend(["molecular_charge", "molecular_multiplicity", "real"])
        data.keywords = {
            "charge": int(molrec["molecular_charge"]),
            "multiplicity": molrec["molecular_multiplicity"],
            "units": umap.get(units.lower()),
            "coordinates": "cartesian",
        }

    elif dtype == "molpro":
        atom_format = "{elem}"
        ghost_format = "{elem}"
        umap = {"bohr": "bohr", "angstrom": "angstrom"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        smol = []

        # Don't orient the molecule if asked to fix_com or fix_orientation
        if molrec["fix_orientation"] or molrec["fix_com"]:
            smol.append("{orient,noorient}")

        # Have no symmetry if asked to fix_symmetry
        if "fix_symmetry" in molrec.keys() and molrec["fix_symmetry"] == "c1":
            smol.append("{symmetry,nosym}")
        elif "fix_symmetry" not in molrec.keys():
            smol.append("{symmetry,auto}")

        smol.append("")

        units_line = f"""{{{umap.get(units.lower())}}}"""
        geom_line = """geometry={"""
        end_bracket = """}"""
        smol.append(units_line)
        smol.append(geom_line)
        smol.extend(atoms)
        smol.append(end_bracket)

        # Write ghost atom declarations in Molpro (using dummy card)
        if False in molrec["real"]:
            ghost_line = "dummy," + ",".join([str(idx + 1) for idx, real in enumerate(molrec["real"]) if not real])
            smol.append(ghost_line)

        smol.append(f"set,charge={molrec['molecular_charge']}")
        # The Molpro "spin" is the multiplicity minus one
        smol.append(f"set,spin={molrec['molecular_multiplicity']-1}")

    elif dtype == "nwchem":
        atom_format = "{elem}{elbl}"
        ghost_format = "bq{elem}{elbl}"
        # TODO handle which units valid
        umap = {"bohr": "bohr", "angstrom": "angstroms", "nm": "nanometers", "pm": "picometers"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        first_line = f"""geometry units {umap.get(units.lower())}"""
        # noautosym nocenter  # no reorienting input geometry
        fix_symm = molrec.get("fix_symmetry", None)
        symm_line = ""
        if fix_symm:
            symm_line = "symmetry {}".format(fix_symm)  # not quite what Jiyoung had
        last_line = """end"""
        smol = [first_line]
        smol.extend(atoms)
        smol.append(symm_line)
        smol.append(last_line)

        data.fields.extend(["molecular_charge", "molecular_multiplicity", "real"])
        data.keywords = {"charge": int(molrec["molecular_charge"])}
        if molrec["molecular_multiplicity"] != 1:
            data.keywords["scf__nopen"] = molrec["molecular_multiplicity"] - 1
            data.keywords["dft__mult"] = molrec["molecular_multiplicity"]
            data.keywords["mcscf__multiplicity"] = molrec["molecular_multiplicity"]
    elif dtype == "madness":

        atom_format = "{elem}"
        ghost_format = "GH"
        # TODO handle which units valid
        umap = {"bohr": "au", "angstrom": "angstrom"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        first_line = f"""geometry"""
        second_line = f"""units {umap.get(units.lower())}"""
        last_line = """end"""
        # noautosym nocenter  # no reorienting input geometry
        smol = [first_line]
        smol.append(second_line)
        eprec = molrec.get("eprec", None)
        if eprec is not None:
            smol.append(f"eprec {eprec}")

        smol.extend(atoms)
        smol.append(last_line)

        symbols = molrec["elem"]
        geometry = geom

        class geometry_parameters:
            def __init__(
                self,
                eprec=None,
                field=None,
                no_orient=None,
                psp_calc=None,
                pure_ae=None,
                symtol=None,
                core_type=None,
                units=None,
            ):

                self.eprec = 1e-4
                self.field = [0.0, 0.0, 0.0]
                self.no_orient = False
                self.psp_calc = False
                self.pure_ae = True
                self.symtol = -1e-2
                self.core_type = "none"
                self.units = "atomic"

                if eprec is not None:
                    self.eprec = float(eprec)
                if field is not None:
                    self.field = field
                if no_orient is not None:
                    self.no_orient = no_orient
                if psp_calc is not None:
                    self.psp_calc = psp_calc
                if pure_ae is not None:
                    self.pure_ae = pure_ae
                if symtol is not None:
                    self.symtol = symtol
                if core_type is not None:
                    self.core_type = core_type
                if units is not None:
                    self.units = umap.get(units.lower())

            def __repr__(self):
                return f"eprec: {self.eprec}, field: {self.field}, no_orient: {self.no_orient}, psp_calc: {self.psp_calc}, pure_ae: {self.pure_ae}, symtol: {self.symtol}, core_type: {self.core_type}, units: {self.units}"

            def to_dict(self):
                return {
                    "eprec": float(self.eprec),
                    "field": self.field,
                    "no_orient": self.no_orient,
                    "psp_calc": self.psp_calc,
                    "pure_ae": self.pure_ae,
                    "symtol": self.symtol,
                    "core_type": self.core_type,
                    "units": self.units,
                }

        parameters = geometry_parameters(
            eprec=molrec.get("eprec", None),
            field=[0.0, 0.0, 0.0],
            no_orient=molrec.get("no_orient", None),
            psp_calc=molrec.get("psp_calc", False),
            pure_ae=molrec.get("pure_ae", True),
            symtol=molrec.get("symtol", None),
            core_type=molrec.get("core_type", None),
            units=umap.get(units.lower()),
        )

        data.fields.extend(["molecular_charge", "molecular_multiplicity"])
        data.keywords = {
            "charge": int(molrec["molecular_charge"]),
            "madqc_json": {
                "name": name,
                "symbols": symbols.tolist(),
                "geometry": geometry.tolist(),
                "parameters": parameters.to_dict(),
            },
        }
        if molrec["molecular_multiplicity"] != 1:
            data.keywords["spin_restricted"] = "false"

    elif dtype == "gamess":
        # * GAMESS can't detect or run in symmetry w/o explicit notation
        # * symm detection is out-of-scope for qcel -- hence the explicit C1 default
        # * symm provisionally hackable by passing both point group and naxis (if needed)
        #   through ``fix_symmetry``. newline encoded here if needed.
        # * coord=prinaxis, as set up here, can't handle ghost atoms

        atom_format = " {elem}{elbl} {elez}"
        ghost_format = " {elem} -{elez}"
        umap = {"bohr": "bohr", "angstrom": "angs"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        first_line = """ $data"""
        second_line = f""" {tagline}"""  # card -1-
        fix_symm = molrec.get("fix_symmetry", "C1").strip()
        symm_line = f" {fix_symm}"  # card -2-
        if fix_symm.upper() != "C1":
            symm_line += "\n"  # blank card replaces -3- & -4-
        last_line = """ $end"""

        smol = [first_line, second_line, symm_line]
        smol.extend(atoms)  # card -5C-
        smol.append(last_line)

        data.fields.extend(["molecular_charge", "molecular_multiplicity", "real"])
        data.keywords = {
            "contrl__icharg": int(molrec["molecular_charge"]),
            "contrl__mult": molrec["molecular_multiplicity"],
            "contrl__units": umap.get(units.lower()),
            "contrl__coord": "prinaxis",
        }

    elif dtype == "terachem":
        atom_format = "{elem}"
        ghost_format = "X{elem}"
        umap = {"bohr": "au", "angstrom": ""}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        first_line = f"""{len(atoms)} {umap[units.lower()]}"""
        smol = [first_line.rstrip(), name]
        smol.extend(atoms)

    elif dtype == "psi4":
        atom_format = "{elem}{elbl}"
        ghost_format = "Gh({elem}{elbl})"
        umap = {"bohr": "bohr", "angstrom": "angstrom"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        smol = [f"""{int(molrec['molecular_charge'])} {molrec['molecular_multiplicity']}"""]
        split_atoms = np.split(atoms, molrec["fragment_separators"])
        for ifr, fr in enumerate(split_atoms):
            if len(split_atoms) > 1:  # harmless to include but tidier to exclude
                smol.extend(["--", f"{int(molrec['fragment_charges'][ifr])} {molrec['fragment_multiplicities'][ifr]}"])
            smol.extend(fr.tolist())

        # append units and any other non-default molecule keywords
        smol.append(f"units {umap[units.lower()]}")
        if molrec["fix_com"]:
            smol.append("no_com")
        if molrec["fix_orientation"]:
            smol.append("no_reorient")

        data.fields.extend(
            [
                "molecular_charge",
                "molecular_multiplicity",
                "fragments",
                "fragment_charges",
                "fragment_multiplicities",
                "fix_com",
                "fix_orientation",
                "real",
            ]
        )
        data.keywords = {}

    elif dtype == "turbomole":
        # In Turbomole coord files the coordinates come first, and the atomic
        # symbol comes afterwards.
        # Handling of ghost atoms is done in the basis section of the control
        # file by setting the nuclear charge of certain atoms to zero.
        atom_format = "{elem}"
        ghost_format = "{elem}"
        umap = {"bohr": "bohr"}
        umap[units.lower()]  # trigger error if downstream can't handle

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2, xyze=True)
        atoms = [at.lower() for at in atoms]

        smol = ["$coord"] + atoms + ["$end"]

    elif dtype == "nglview-sdf":
        # SDF is pretty special, handle it manually

        if units.capitalize() != "Angstrom":
            raise ValueError("SDF Format must be in Angstroms")

        ghost_format = ghost_format or "Gh"

        connectivity = molrec.get("connectivity", None)
        if connectivity is None:
            bohr_geom = geom * constants.conversion_factor("Angstrom", "Bohr")
            connectivity = guess_connectivity(molrec["elem"], bohr_geom, default_connectivity=1)

        smol = []
        smol.append("")
        smol.append("QCElemental\n")
        smol.append(f"{len(molrec['real']):3d} {len(connectivity):2d}  0  0  0  0  0  0  0  0  0")
        for real, sym, xyz in zip(molrec["real"], molrec["elem"], geom):
            if bool(real) is False:
                sym = ghost_format
            smol.append(f"{xyz[0]:10.4f}{xyz[1]:10.4f}{xyz[2]:10.4f}{sym:>3s}  0  0     0  0  0  0  0  0")

        for a1, a2, b in connectivity:
            smol.append(f" {(a1 + 1):2d} {(a2 + 1):2d}  {int(b):1d}  0  0  0  0")

    elif dtype == "qchem":
        atom_format = "{elem}"
        ghost_format = "@{elem}"
        umap = {"bohr": "True", "angstrom": "False"}

        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        first_line = "$molecule"
        chgmult_line = f"""{int(molrec['molecular_charge'])} {molrec['molecular_multiplicity']}"""
        last_line = "$end"

        smol = [first_line, chgmult_line]
        split_atoms = np.split(atoms, molrec["fragment_separators"])
        for ifr, fr in enumerate(split_atoms):
            if len(split_atoms) > 1:
                smol.extend(
                    ["--", f"""{int(molrec['fragment_charges'][ifr])} {molrec['fragment_multiplicities'][ifr]}"""]
                )
            smol.extend(fr.tolist())
        smol.append(last_line)

        data.fields.extend(
            [
                "fix_com",
                "fix_orientation",
                "fragment_charges",
                "fragment_multiplicities",
                "molecular_charge",
                "molecular_multiplicity",
                "real",
                "units",
            ]
        )

        data.keywords = {
            "no_reorient": molrec["fix_orientation"] or molrec["fix_com"],
            "input_bohr": umap[units.lower()],
        }

        if "fix_symmetry" in molrec.keys() and molrec["fix_symmetry"] == "c1":
            data.keywords["sym_ignore"] = True
            data.keywords["symmetry"] = False

    elif dtype == "mrchem":
        atom_format = "{elem}"
        ghost_format = "{elem}"
        atoms = _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, 2)

        smol = (
            [
                "Molecule {",
                f"charge = {int(molrec['molecular_charge'])}",
                f"multiplicity = {molrec['molecular_multiplicity']}",
                f"translate = {molrec['fix_com']}",
                "$coords",
            ]
            + atoms
            + ["$end\n}"]
        )

        # this is what we are actually interested in:
        # when dtype="mrchem", we always want to set return_data=True
        data.keywords = {
            "charge": int(molrec["molecular_charge"]),
            "multiplicity": molrec["molecular_multiplicity"],
            "translate": molrec["fix_com"],
            "coords": "\n".join(atoms),
        }

    else:
        raise KeyError(f"dtype '{dtype}' not understood.")

    smol_ret = "\n".join(smol) + "\n"
    if return_data:
        return smol_ret, data.to_dict()
    else:
        return smol_ret


def _atoms_formatter(molrec, geom, atom_format, ghost_format, width, prec, sp, xyze=False):
    """Format a list of strings, one per atom from `molrec`."""

    nat = geom.shape[0]
    fxyz = """{:>{width}.{prec}f}"""
    sp = """{:{sp}}""".format("", sp=sp)

    atoms = []
    for iat in range(nat):
        atom = []
        atominfo = {
            "elea": "" if molrec["elea"][iat] == -1 else molrec["elea"][iat],
            "elez": molrec["elez"][iat],
            "elem": molrec["elem"][iat],
            "mass": molrec["mass"][iat],
            "elbl": molrec["elbl"][iat],
        }

        if molrec["real"][iat]:
            nuc = """{:{width}}""".format(atom_format.format(**atominfo), width=width)
            atom.append(nuc)
        else:
            if ghost_format in ["", None]:
                continue
            else:
                nuc = """{:{width}}""".format(ghost_format.format(**atominfo), width=width)
                atom.append(nuc)

        atom.extend([fxyz.format(x, width=width, prec=prec) for x in geom[iat]])
        if xyze:
            atom.append(atom.pop(0).rstrip())
        atoms.append(sp.join(atom))

    return atoms


def formula_generator(elem):
    """Return simple chemical formula from element list `elem`.

    >>> formula_generator(['C', 'Ca', 'O', 'O', 'Ag']
    AgCCaO2

    """
    counted = collections.Counter(elem)
    return "".join((el if cnt == 1 else (el + str(cnt))) for el, cnt in sorted(counted.items()))
