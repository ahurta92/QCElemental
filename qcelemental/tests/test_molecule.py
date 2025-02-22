"""
Tests the imports and exports of the Molecule object.
"""


import numpy as np
import pytest

import qcelemental as qcel
from qcelemental.exceptions import NotAnElementError
from qcelemental.models import Molecule
from qcelemental.testing import compare, compare_values

from .addons import serialize_extensions, using_msgpack, using_nglview

water_molecule = Molecule.from_data(
    """
    0 1
    O  -1.551007  -0.114520   0.000000
    H  -1.934259   0.762503   0.000000
    H  -0.599677   0.040712   0.000000
    """
)

water_dimer_minima = Molecule.from_data(
    """
    0 1
    O  -1.551007  -0.114520   0.000000
    H  -1.934259   0.762503   0.000000
    H  -0.599677   0.040712   0.000000
    --
    O   1.350625   0.111469   0.000000
    H   1.680398  -0.373741  -0.758561
    H   1.680398  -0.373741   0.758561
    """,
    dtype="psi4",
    orient=True,
)


def test_molecule_data_constructor_numpy():
    water_psi = water_dimer_minima.copy()
    ele = np.array(water_psi.atomic_numbers).reshape(-1, 1)
    npwater = np.hstack((ele, water_psi.geometry * qcel.constants.conversion_factor("Bohr", "angstrom")))

    water_from_np = Molecule.from_data(npwater, name="water dimer", dtype="numpy", frags=[3])
    assert water_psi == water_from_np

    water_from_np = Molecule.from_data(npwater, name="water dimer", frags=[3])
    assert water_psi == water_from_np
    assert water_psi.get_molecular_formula() == "H4O2"
    assert water_psi.get_molecular_formula(order="alphabetical") == "H4O2"
    assert water_psi.get_molecular_formula(order="hill") == "H4O2"


def test_molecule_data_constructor_dict():
    water_psi = water_dimer_minima.copy()

    # Check the JSON construct/deconstruct
    water_from_json = Molecule.from_data(water_psi.dict())
    assert water_psi == water_from_json

    water_from_json = Molecule.from_data(water_psi.json(), "json")
    assert water_psi == water_from_json
    assert water_psi == Molecule.from_data(water_psi.to_string("psi4"), dtype="psi4")

    assert (
        water_psi.get_hash() == "3c4b98f515d64d1adc1648fe1fe1d6789e978d34"  # pragma: allowlist secret
    )  # copied from schema_version=1
    assert water_psi.schema_version == 2
    assert water_psi.schema_name == "qcschema_molecule"


def test_molecule_data_constructor_error():
    with pytest.raises(TypeError):
        Molecule.from_data([])

    with pytest.raises(KeyError):
        Molecule.from_data({}, dtype="bad")


def test_hash_canary():
    water_dimer_minima = Molecule.from_data(
        """
    0 1
    O  -1.551007  -0.114520   0.000000
    H  -1.934259   0.762503   0.000000
    H  -0.599677   0.040712   0.000000
    --
    O   1.350625   0.111469   0.000000
    H   1.680398  -0.373741  -0.758561
    H   1.680398  -0.373741   0.758561
    """,
        dtype="psi4",
    )
    assert water_dimer_minima.get_hash() == "42f3ac52af52cf2105c252031334a2ad92aa911c"  # pragma: allowlist secret

    # Check orientation
    mol = water_dimer_minima.orient_molecule()
    assert mol.get_hash() == "632490a0601500bfc677e9277275f82fbc45affe"  # pragma: allowlist secret

    frag_0 = mol.get_fragment(0, orient=True)
    frag_1 = mol.get_fragment(1, orient=True)
    assert frag_0.get_hash() == "d0b499739f763e8d3a5556b4ddaeded6a148e4d5"  # pragma: allowlist secret
    assert frag_1.get_hash() == "bdc1f75bd1b7b999ff24783d7c1673452b91beb9"  # pragma: allowlist secret


def test_molecule_np_constructors():
    """
    Neon tetramer fun
    """
    ### Neon Tetramer
    neon_from_psi = Molecule.from_data(
        """
        Ne 0.000000 0.000000 0.000000
        --
        Ne 3.100000 0.000000 0.000000
        --
        Ne 0.000000 3.200000 0.000000
        --
        Ne 0.000000 0.000000 3.300000
        units bohr""",
        dtype="psi4",
    )
    ele = np.array([10, 10, 10, 10]).reshape(-1, 1)
    npneon = np.hstack((ele, neon_from_psi.geometry))
    neon_from_np = Molecule.from_data(npneon, name="neon tetramer", dtype="numpy", frags=[1, 2, 3], units="bohr")

    assert neon_from_psi == neon_from_np

    # Check the JSON construct/deconstruct
    neon_from_json = Molecule.from_data(neon_from_psi.json(), dtype="json")
    assert neon_from_psi == neon_from_json
    assert neon_from_json.get_molecular_formula() == "Ne4"


def test_molecule_compare():
    water_molecule2 = water_molecule.copy()
    assert water_molecule2 == water_molecule

    water_molecule3 = water_molecule.copy(update={"geometry": (water_molecule.geometry + np.array([0.1, 0, 0]))})
    assert water_molecule != water_molecule3


def test_molecule_repr_chgmult():
    wat1 = water_molecule.copy()
    assert "formula='H2O'," in wat1.__repr__(), "charge/mult wrongly present in Molecule repr"

    wat2 = water_dimer_minima.dict()
    wat2["fragment_charges"] = [1, 0]
    for field in ["molecular_charge", "molecular_multiplicity", "fragment_multiplicities", "validated"]:
        wat2.pop(field)
    wat2 = Molecule(**wat2)
    assert "formula='2^H4O2+'," in wat2.__repr__(), "charge/mult missing from Molecule repr"

    two_pentanol_radcat = Molecule.from_data(
        """
        1 2
        C         -4.43914        1.67538       -0.14135
        C         -2.91385        1.70652       -0.10603
        H         -4.82523        2.67391       -0.43607
        H         -4.84330        1.41950        0.86129
        H         -4.79340        0.92520       -0.88015
        H         -2.59305        2.48187        0.62264
        H         -2.53750        1.98573       -1.11429
        C         -2.34173        0.34025        0.29616
        H         -2.72306        0.06156        1.30365
        C         -0.80326        0.34498        0.31454
        H         -2.68994       -0.42103       -0.43686
        O         -0.32958        1.26295        1.26740
        H         -0.42012        0.59993       -0.70288
        C         -0.26341       -1.04173        0.66218
        H         -0.61130       -1.35318        1.67053
        H          0.84725       -1.02539        0.65807
        H         -0.60666       -1.78872       -0.08521
        H         -0.13614        2.11102        0.78881
    """
    )
    assert "formula='2^C5H12O+'," in two_pentanol_radcat.__repr__(), "charge/mult missing from Molecule repr"

    Oanion = Molecule.from_data(
        """
        -2 1
        O 0 0 0
    """
    )
    assert "formula='O--'," in Oanion.__repr__(), "charge/mult missing from Molecule repr"


def test_water_minima_data():
    # Give it a name
    mol_dict = water_dimer_minima.dict()
    mol_dict["name"] = "water dimer"
    mol = Molecule(orient=True, **mol_dict)

    assert len(mol.pretty_print()) == 661
    assert len(mol.to_string("psi4")) == 479

    assert sum(x == y for x, y in zip(mol.symbols, ["O", "H", "H", "O", "H", "H"])) == mol.geometry.shape[0]
    assert mol.name == "water dimer"
    assert mol.molecular_charge == 0
    assert mol.molecular_multiplicity == 1
    assert np.sum(mol.real) == mol.geometry.shape[0]
    assert np.allclose(mol.fragments, [[0, 1, 2], [3, 4, 5]])
    assert np.allclose(mol.fragment_charges, [0, 0])
    assert np.allclose(mol.fragment_multiplicities, [1, 1])
    assert hasattr(mol, "provenance")
    assert np.allclose(
        mol.geometry,
        [
            [2.81211080, 0.1255717, 0.0],
            [3.48216664, -1.55439981, 0.0],
            [1.00578203, -0.1092573, 0.0],
            [-2.6821528, -0.12325075, 0.0],
            [-3.27523824, 0.81341093, 1.43347255],
            [-3.27523824, 0.81341093, -1.43347255],
        ],
    )
    assert mol.get_hash() == "3c4b98f515d64d1adc1648fe1fe1d6789e978d34"  # pragma: allowlist secret


def test_water_minima_fragment():
    mol = water_dimer_minima.copy()
    frag_0 = mol.get_fragment(0, orient=True)
    frag_1 = mol.get_fragment(1, orient=True)
    assert frag_0.get_hash() == "5f31757232a9a594c46073082534ca8a6806d367"  # pragma: allowlist secret
    assert frag_1.get_hash() == "bdc1f75bd1b7b999ff24783d7c1673452b91beb9"  # pragma: allowlist secret

    frag_0_1 = mol.get_fragment(0, 1)
    frag_1_0 = mol.get_fragment(1, 0)

    assert np.array_equal(mol.symbols[:3], frag_0.symbols)
    assert np.allclose(mol.masses[:3], frag_0.masses)

    assert np.array_equal(mol.symbols, frag_0_1.symbols)
    assert np.allclose(mol.geometry, frag_0_1.geometry)

    assert np.array_equal(np.hstack((mol.symbols[3:], mol.symbols[:3])), frag_1_0.symbols)
    assert np.allclose(np.hstack((mol.masses[3:], mol.masses[:3])), frag_1_0.masses)


def test_pretty_print():
    mol = water_dimer_minima.copy()
    assert isinstance(mol.pretty_print(), str)


def test_to_string():
    mol = water_dimer_minima.copy()
    assert isinstance(mol.to_string("psi4"), str)


@pytest.mark.parametrize(
    "dtype, filext",
    [("json", "json"), ("xyz", "xyz"), ("numpy", "npy"), pytest.param("msgpack", "msgpack", marks=using_msgpack)],
)
def test_to_from_file_simple(tmp_path, dtype, filext):
    benchmol = Molecule.from_data(
        """
    O 0 0 0
    H 0 1.5 0
    H 0 0 1.5
    """
    )

    p = tmp_path / ("water." + filext)
    benchmol.to_file(p, dtype=dtype)

    mol = Molecule.from_file(p)

    assert mol == benchmol


@pytest.mark.parametrize("dtype", ["json", "psi4"])
def test_to_from_file_complex(tmp_path, dtype):
    p = tmp_path / ("water." + dtype)
    water_dimer_minima.to_file(p)

    mol = Molecule.from_file(p)
    assert mol == water_dimer_minima


@pytest.mark.parametrize(
    "dtype, filext", [("json", "json"), ("xyz+", "xyz"), pytest.param("msgpack", "msgpack", marks=using_msgpack)]
)
def test_to_from_file_charge_spin(tmp_path, dtype, filext):
    benchmol = Molecule.from_data(
        """
    1 2
    O 0 0 0
    H 0 1.5 0
    H 0 0 1.5
    """
    )

    p = tmp_path / ("water." + filext)
    benchmol.to_file(p, dtype=dtype)

    mol = Molecule.from_file(p, dtype=dtype)

    assert mol.molecular_charge == 1
    assert mol.molecular_multiplicity == 2
    assert mol.fragment_charges[0] == 1
    assert mol.fragment_multiplicities[0] == 2
    assert mol == benchmol


def test_from_data_kwargs():
    mol = Molecule.from_data(
        """
        O 0 0 0
        H 0 1.5 0
        H 0 0 1.5
        """,
        molecular_charge=1,
        molecular_multiplicity=2,
        fragment_charges=[1],
        fragment_multiplicities=[2],
    )
    assert mol.molecular_charge == 1
    assert mol.molecular_multiplicity == 2
    assert mol.fragment_charges[0] == 1
    assert mol.fragment_multiplicities[0] == 2

    mol = Molecule.from_data(
        """
            O 0 0 0
            H 0 1.5 0
            H 0 0 1.5
            """,
        molecular_charge=1,
        molecular_multiplicity=2,
    )
    assert mol.molecular_charge == 1
    assert mol.molecular_multiplicity == 2
    assert mol.fragment_charges[0] == 1
    assert mol.fragment_multiplicities[0] == 2

    with pytest.raises(qcel.ValidationError) as e:
        mol = Molecule.from_data(
            """
            O 0 0 0
            H 0 1.5 0
            H 0 0 1.5
            """,
            molecular_charge=1,
            molecular_multiplicity=2,
            fragment_charges=[2],
        )
    assert "Inconsistent or unspecified chg/mult" in str(e.value)


def test_water_orient():
    # These are identical molecules, should find the correct results
    mol = Molecule.from_data(
        """
        O  -1.551007  -0.114520   0.000000
        H  -1.934259   0.762503   0.000000
        H  -0.599677   0.040712   0.000000
        --
        O  -0.114520  -1.551007  10.000000
        H   0.762503  -1.934259  10.000000
        H   0.040712  -0.599677  10.000000
        """
    )

    frag_0 = mol.get_fragment(0, orient=True)
    frag_1 = mol.get_fragment(1, orient=True)

    # Make sure the fragments match
    assert frag_0.get_hash() == frag_1.get_hash()
    assert frag_0.get_hash() == "d0b499739f763e8d3a5556b4ddaeded6a148e4d5"

    # Make sure the complexes match
    frag_0_1 = mol.get_fragment(0, 1, orient=True, group_fragments=True)
    frag_1_0 = mol.get_fragment(1, 0, orient=True, group_fragments=True)
    assert frag_0_1.get_hash() == frag_1_0.get_hash()
    assert frag_0_1.get_hash() == "bd23a8a5e48a3a6a32011559fdddc958bb70343b"

    # Fragments not reordered, should be different molecules.
    frag_0_1 = mol.get_fragment(0, 1, orient=True, group_fragments=False)
    frag_1_0 = mol.get_fragment(1, 0, orient=True, group_fragments=False)
    assert frag_0_1.get_hash() != frag_1_0.get_hash()
    assert frag_0_1.get_hash() == "bd23a8a5e48a3a6a32011559fdddc958bb70343b"
    assert frag_1_0.get_hash() == "9ed8bdc4ae559c20816d65225fdb1ae3c29d149f"

    # These are identical molecules, but should be different with ghost
    mol = Molecule.from_data(
        """
        O  -1.551007  -0.114520   0.000000
        H  -1.934259   0.762503   0.000000
        H  -0.599677   0.040712   0.000000
        --
        O  -11.551007  -0.114520   0.000000
        H  -11.934259   0.762503   0.000000
        H  -10.599677   0.040712   0.000000
        """,
        dtype="psi4",
        orient=True,
    )

    frag_0 = mol.get_fragment(0, orient=True)
    frag_1 = mol.get_fragment(1, orient=True)

    # Make sure the fragments match
    assert frag_0.molecular_multiplicity == 1
    assert frag_0.get_hash() == frag_1.get_hash()
    assert frag_0.get_hash() == "77b272802d61b578b1c65bb87747a89e53e015a7"

    # Make sure the complexes match
    frag_0_1 = mol.get_fragment(0, 1, orient=True)
    frag_1_0 = mol.get_fragment(1, 0, orient=True)

    # Ghost fragments should prevent overlap
    assert frag_0_1.molecular_multiplicity == 1
    assert frag_0_1.get_hash() != frag_1_0.get_hash()
    assert frag_0_1.get_hash() == "4a4cd4d0ab0eef8fed2221fb692c3b1fbf4834de"
    assert frag_1_0.get_hash() == "4cc0b30f9f50dd85f4f2036a683865bf17ded803"


def test_molecule_errors_extra():
    data = water_dimer_minima.dict(exclude_unset=True)
    data["whatever"] = 5
    with pytest.raises(Exception):
        Molecule(**data, validate=False)


def test_molecule_errors_connectivity():
    data = water_molecule.dict()
    data["connectivity"] = [(-1, 5, 5)]
    with pytest.raises(Exception):
        Molecule(**data)


def test_molecule_errors_shape():
    data = water_molecule.dict()
    data["geometry"] = list(range(8))
    with pytest.raises(Exception):
        Molecule(**data)


def test_molecule_json_serialization():
    assert isinstance(water_dimer_minima.json(), str)

    assert isinstance(water_dimer_minima.dict(encoding="json")["geometry"], list)

    assert water_dimer_minima == Molecule.from_data(water_dimer_minima.json(), dtype="json")


@pytest.mark.parametrize("encoding", serialize_extensions)
def test_molecule_serialization(encoding):
    blob = water_dimer_minima.serialize(encoding)
    assert water_dimer_minima == Molecule.parse_raw(blob, encoding=encoding)


def test_charged_fragment():
    mol = Molecule(
        symbols=["Li", "Li"],
        geometry=[0, 0, 0, 0, 0, 5],
        fragment_charges=[0.0, 0.0],
        fragment_multiplicities=[2, 2],
        fragments=[[0], [1]],
    )
    assert mol.molecular_multiplicity == 3
    assert mol.molecular_charge == 0
    f1 = mol.get_fragment(0)
    assert f1.molecular_multiplicity == 2
    assert f1.fragment_multiplicities == [2]
    assert pytest.approx(f1.molecular_charge) == 0
    assert pytest.approx(f1.fragment_charges) == [0]


# someday, when we can have noncontig frags
#    mol = Molecule(**{
#        'fragments': [[1, 5, 6], [0], [2, 3, 4]],
#        'symbols': ["he", "o", "o", "h", "h", "h", "h"],
#        # same geom as test_water_orient but with He at origin
#        'geometry': [
#        0.0, 0.0, 0.0,
#        -1.551007,  -0.114520,   0.000000,
#        -0.114520,  -1.551007,  10.000000,
#         0.762503,  -1.934259,  10.000000,
#         0.040712,  -0.599677,  10.000000,
#        -1.934259,   0.762503,   0.000000,
#        -0.599677,   0.040712,   0.000000],
#    })


@pytest.mark.parametrize("group_fragments, orient", [(True, True), (False, False)])  # original  # Psi4-like
def test_get_fragment(group_fragments, orient):
    mol = Molecule(
        **{
            "fragments": [[0], [1, 2, 3], [4, 5, 6]],
            "symbols": ["he", "o", "h", "h", "o", "h", "h"],
            # same geom as test_water_orient but with He at origin
            "geometry": np.array(
                [
                    [0.0, 0.0, 0.0],
                    [-1.551007, -0.114520, 0.000000],
                    [-1.934259, 0.762503, 0.000000],
                    [-0.599677, 0.040712, 0.000000],
                    [-0.114520, -1.551007, 10.000000],
                    [0.762503, -1.934259, 10.000000],
                    [0.040712, -0.599677, 10.000000],
                ]
            )
            / qcel.constants.bohr2angstroms,
        }
    )

    assert mol.nelectrons() == 22
    assert compare_values(32.25894779318589, mol.nuclear_repulsion_energy(), atol=1.0e-5)
    assert mol.symbols[0] == "He"

    monomers_nelectrons = [2, 10, 10]
    monomers_nre = [0.0, 9.163830150548483, 9.163830150548483]
    monomers = [mol.get_fragment(ifr, group_fragments=group_fragments, orient=orient) for ifr in range(3)]
    for fr in range(3):
        assert monomers[fr].nelectrons() == monomers_nelectrons[fr]
        assert compare_values(monomers[fr].nuclear_repulsion_energy(), monomers_nre[fr], "monomer nre", atol=1.0e-5)

    idimers = [(0, 1), (0, 2), (1, 2), (1, 0), (2, 0), (2, 1)]
    dimers_nelectrons = [12, 12, 20, 12, 12, 20]
    dimers_nre = [16.8777971, 10.2097206, 23.4990904, 16.8777971, 10.2097206, 23.4990904]
    dimers = [mol.get_fragment(rl, group_fragments=group_fragments, orient=orient) for rl in idimers]
    for ifr in range(len(idimers)):
        # print('dd', ifr, idimers[ifr], dimers[ifr].nuclear_repulsion_energy(), dimers[ifr].get_hash())
        assert dimers[ifr].nelectrons() == dimers_nelectrons[ifr], "dimer nelec"
        assert compare_values(dimers[ifr].nuclear_repulsion_energy(), dimers_nre[ifr], "dimer nre", atol=1.0e-5)
    if group_fragments and orient:
        assert dimers[0].get_hash() != dimers[3].get_hash()  # atoms out of order
        assert dimers[1].get_hash() != dimers[4].get_hash()  # atoms out of order
        assert dimers[2].get_hash() == dimers[5].get_hash()
        assert dimers[5].get_hash() == "f1d6551f95ce9467dbcce7c48e11bb98d0f1fb98"
    elif not group_fragments and not orient:
        assert dimers[0].get_hash() == dimers[3].get_hash()
        assert dimers[1].get_hash() == dimers[4].get_hash()
        assert dimers[2].get_hash() == dimers[5].get_hash()
        assert dimers[5].get_hash() == "1bd9100e99748a0c34b01cef558ea5cf4ae6ab85"
    else:
        assert 0

    ghdimers_nelectrons = [2, 2, 10, 10, 10, 10]
    ghdimers_nre = [0.0, 0.0, 9.163830150548483, 9.163830150548483, 9.163830150548483, 9.163830150548483]
    ghdimers = [mol.get_fragment(rl, gh, group_fragments=group_fragments, orient=orient) for rl, gh in idimers]
    for ifr in range(len(idimers)):
        # print('gh', ifr, idimers[ifr], ghdimers[ifr].nuclear_repulsion_energy(), ghdimers[ifr].get_hash())
        assert ghdimers[ifr].nelectrons() == ghdimers_nelectrons[ifr], "gh dimer nelec"
        assert compare_values(ghdimers[ifr].nuclear_repulsion_energy(), ghdimers_nre[ifr], "gh dimer nre", atol=1.0e-5)

    if group_fragments and orient:
        assert ghdimers[0].get_hash() != ghdimers[3].get_hash()  # diff atoms ghosted
        assert ghdimers[1].get_hash() != ghdimers[4].get_hash()  # diff atoms ghosted
        assert ghdimers[2].get_hash() == ghdimers[5].get_hash()
        assert ghdimers[5].get_hash() == "bd23a8a5e48a3a6a32011559fdddc958bb70343b"
    elif not group_fragments and not orient:
        assert ghdimers[0].get_hash() != ghdimers[3].get_hash()  # diff atoms ghosted
        assert ghdimers[1].get_hash() != ghdimers[4].get_hash()  # diff atoms ghosted
        assert ghdimers[2].get_hash() != ghdimers[5].get_hash()  # real pattern different
        assert not np.allclose(ghdimers[2].real, ghdimers[5].real)
        assert ghdimers[5].get_hash() == "9d1fd57e90735a47af4156e1d72b7e8e78fb44eb"
    else:
        assert 0


def test_molecule_repeated_hashing():
    mol = Molecule(
        **{
            "symbols": ["H", "O", "O", "H"],
            "geometry": [
                [1.7317, 1.2909, 1.037100000000001],
                [1.3156, -0.0074, -0.2807],
                [-1.3143, 0.0084, -0.2741],
                [-1.7241, -1.3079, 1.0277],
            ],
        }
    )

    h1 = mol.get_hash()
    assert h1 == "7e604937e8a0c8e4c6426906e25b3002f785b1fc"
    assert mol.get_molecular_formula() == "H2O2"

    mol2 = Molecule(orient=False, **mol.dict())
    assert h1 == mol2.get_hash()

    mol3 = Molecule(orient=False, **mol2.dict())
    assert h1 == mol3.get_hash()


@pytest.mark.parametrize(
    "measure,result",
    [
        ([0, 1], 1.8086677572537304),
        ([0, 1, 2], 37.98890673587713),
        ([0, 1, 2, 3], 180.0),
        ([[0, 1, 2, 3]], [180.0]),
        ([[1, 3], [3, 1], [1, 2, 3]], [6.3282716, 6.3282716, 149.51606694803903]),
        ([[0, 1, 2, 3], [3, 2, 1, 0]], [180.0, 180.0]),
    ],
)
def test_measurements(measure, result):
    Molecule(
        **{
            "symbols": ["H", "O", "O", "H"],
            "geometry": [
                [1.7317, 1.2909, 1.0371],
                [1.3156, -0.0074, -0.2807],
                [-1.3143, 0.0084, -0.2741],
                [-1.7241, -1.3079, 1.0277],
            ],
        }
    )

    assert pytest.approx(water_dimer_minima.measure(measure)) == result


@pytest.mark.parametrize(
    "f1c,f1m,f2c,f2m,tc,tm",
    [
        (0, 2, 0, 2, 0.0, 3),
        (0, 4, 0, 2, 0.0, 5),
        (1, 1, 1, 1, 2.0, 1),
        (1, 1, 0, 2, 1.0, 2),
        (0, 2, 1, 1, 1.0, 2),
        (-1, 1, 1, 1, 0.0, 1),
    ],
)
def test_fragment_charge_configurations(f1c, f1m, f2c, f2m, tc, tm):
    mol = Molecule.from_data(
        """
    {f1c} {f1m}
    Li 0 0 0
    --
    {f2c} {f2m}
    Li 0 0 5
    """.format(
            f1c=f1c, f1m=f1m, f2c=f2c, f2m=f2m
        )
    )

    assert pytest.approx(mol.molecular_charge) == tc
    assert mol.molecular_multiplicity == tm

    # Test fragment1
    assert pytest.approx(mol.get_fragment(0).molecular_charge) == f1c
    assert mol.get_fragment(0).molecular_multiplicity == f1m

    assert pytest.approx(mol.get_fragment(0, 1).molecular_charge) == f1c
    assert mol.get_fragment(0, 1).molecular_multiplicity == f1m

    # Test fragment2
    assert pytest.approx(mol.get_fragment(1).molecular_charge) == f2c
    assert mol.get_fragment(1).molecular_multiplicity == f2m

    assert pytest.approx(mol.get_fragment([1], 0).molecular_charge) == f2c
    assert mol.get_fragment(1, [0]).molecular_multiplicity == f2m


def test_nuclearrepulsionenergy_nelectrons():
    mol = Molecule.from_data(
        """
    0 1
    --
    O          0.75119       -0.61395        0.00271
    H          1.70471       -0.34686        0.00009
    --
    1 1
    N         -2.77793        0.00179       -0.00054
    H         -2.10136        0.51768        0.60424
    H         -3.45559       -0.51904        0.60067
    H         -2.26004       -0.67356       -0.60592
    H         -3.29652        0.68076       -0.60124
    units ang
    """
    )

    assert compare_values(34.60370459, mol.nuclear_repulsion_energy(), "D", atol=1.0e-5)
    assert compare_values(4.275210518, mol.nuclear_repulsion_energy(ifr=0), "M1", atol=1.0e-5)
    assert compare_values(16.04859029, mol.nuclear_repulsion_energy(ifr=1), "M2", atol=1.0e-5)

    assert compare(20, mol.nelectrons(), "D")
    assert compare(10, mol.nelectrons(ifr=0), "M1")
    assert compare(10, mol.nelectrons(ifr=1), "M2")

    mol = mol.get_fragment([1], 0, group_fragments=False)
    # Notice the 0th/1st fragments change if default group_fragments=True.
    ifr0 = 0
    ifr1 = 1
    assert compare_values(16.04859029, mol.nuclear_repulsion_energy(), "D", atol=1.0e-5)
    assert compare_values(0.0, mol.nuclear_repulsion_energy(ifr=ifr0), "M1", atol=1.0e-5)
    assert compare_values(16.04859029, mol.nuclear_repulsion_energy(ifr=ifr1), "M2", atol=1.0e-5)

    assert compare(10, mol.nelectrons(), "D")
    assert compare(0, mol.nelectrons(ifr=ifr0), "M1")
    assert compare(10, mol.nelectrons(ifr=ifr1), "M2")


@using_nglview
def test_show():
    water_dimer_minima.show()


def test_molecule_connectivity():
    data = {"geometry": np.random.rand(5, 3), "symbols": ["he"] * 5, "validate": False}
    Molecule(**data, connectivity=None)

    connectivity = [[n, n + 1, 1] for n in range(4)]
    Molecule(**data, connectivity=connectivity)

    connectivity[0][0] = -1
    with pytest.raises(ValueError):
        Molecule(**data, connectivity=connectivity)


def test_orient_nomasses():
    """
    Masses must be auto generated on the fly
    """

    mol = Molecule(symbols=["He", "He"], geometry=[0, 0, -2, 0, 0, 2], orient=True, validated=True)

    assert mol.__dict__["masses_"] is None
    assert compare_values([[2, 0, 0], [-2, 0, 0]], mol.geometry)


@pytest.mark.parametrize(
    "mol_string, extra_keys",
    [
        ("He 0 0 0", None),
        ("He 0 0 0\n--\nHe 0 0 5", {"fragments", "fragment_charges", "fragment_multiplicities"}),
        ("He 0 0 0\n--\n@He 0 0 5", {"fragments", "fragment_charges", "fragment_multiplicities", "real"}),
        ("He4 0 0 0", {"atom_labels"}),
        ("He@3.14 0 0 0", {"masses", "mass_numbers"}),
    ],
)
def test_sparse_molecule_fields(mol_string, extra_keys):
    expected_keys = {
        "schema_name",
        "schema_version",
        "validated",
        "symbols",
        "geometry",
        "name",
        "molecular_charge",
        "molecular_multiplicity",
        "fix_com",
        "fix_orientation",
        "provenance",
        "extras",
    }
    mol = Molecule.from_data(mol_string)

    if extra_keys is not None:
        expected_keys |= extra_keys

    diff_keys = mol.dict().keys() ^ expected_keys
    assert len(diff_keys) == 0, f"Diff Keys {diff_keys}"


def test_sparse_molecule_connectivity():
    """
    A bit of a weird test, but because we set connectivity it should carry through.
    """
    mol = Molecule(symbols=["He", "He"], geometry=[0, 0, -2, 0, 0, 2], connectivity=None)
    assert "connectivity" in mol.dict()
    assert mol.dict()["connectivity"] is None

    mol = Molecule(symbols=["He", "He"], geometry=[0, 0, -2, 0, 0, 2])
    assert "connectivity" not in mol.dict()


def test_bad_isotope_spec():
    with pytest.raises(NotAnElementError):
        qcel.models.Molecule(symbols=["He3"], geometry=[0, 0, 0])


def test_good_isotope_spec():
    assert compare_values(
        [3.01602932], qcel.models.Molecule(symbols=["He"], mass_numbers=[3], geometry=[0, 0, 0]).masses, "nonstd mass"
    )


def test_nonphysical_spec():
    mol = qcel.models.Molecule(symbols=["He"], masses=[100], geometry=[0, 0, 0], nonphysical=True)
    assert compare_values([100.0], mol.masses, "nonphysical mass")

    print(mol.to_string(dtype="psi4"))


def test_extras():
    mol = qcel.models.Molecule(symbols=["He"], geometry=[0, 0, 0])
    assert mol.extras is not None

    mol = qcel.models.Molecule(symbols=["He"], geometry=[0, 0, 0], extras={"foo": "bar"})
    assert mol.extras["foo"] == "bar"


_ref_mol_multiplicity_hash = {
    "singlet": "b3855c64",
    "triplet": "7caca87a",
    "disinglet": "83a85546",
    "ditriplet": "71d6ba82",
    # float mult
    "singlet_point1": "4e9e2587",
    "singlet_epsilon": "ad3f5fab",
    "triplet_point1": "ad35cc28",
    "triplet_point1_minus": "b63d6983",
    "triplet_point00001": "7107b7ac",
    "disinglet_epsilon": "fb0aaaca",
    "ditriplet_point1": "33d47d5f",
    "ditriplet_point00001": "7f0ac640",
}


@pytest.mark.parametrize(
    "mult_in,mult_store,validate,exp_hash",
    [
        pytest.param(3, 3, False, "triplet"),
        pytest.param(3, 3, True, "triplet"),
        # before float multiplicity was allowed, 3.1 (below) was coerced into 3 with validate=False,
        #   and validate=True threw a type-mentioning error. Now, 2.9 is allowed for both validate=T/F
        pytest.param(3.1, 3.1, False, "triplet_point1"),
        # validate=True counterpart fails b/c insufficient electrons in He for more than triplet
        pytest.param(2.9, 2.9, False, "triplet_point1_minus"),
        pytest.param(2.9, 2.9, True, "triplet_point1_minus"),
        pytest.param(3.00001, 3.00001, False, "triplet_point00001"),
        # validate=True counterpart fails like 3.1 above
        pytest.param(2.99999, 2.99999, False, "triplet_point00001"),  # hash agrees w/3.00001 above b/c <CHARGE_NOISE
        pytest.param(2.99999, 2.99999, True, "triplet_point00001"),
        pytest.param(3.0, 3, False, "triplet"),
        pytest.param(3.0, 3, True, "triplet"),
        pytest.param(1, 1, False, "singlet"),
        pytest.param(1, 1, True, "singlet"),
        pytest.param(1.000000000000000000002, 1, False, "singlet"),
        pytest.param(1.000000000000000000002, 1, True, "singlet"),
        pytest.param(1.000000000000002, 1.000000000000002, False, "singlet_epsilon"),
        pytest.param(1.000000000000002, 1.000000000000002, True, "singlet_epsilon"),
        pytest.param(1.1, 1.1, False, "singlet_point1"),
        pytest.param(1.1, 1.1, True, "singlet_point1"),
        pytest.param(None, 1, False, "singlet"),
        pytest.param(None, 1, True, "singlet"),
        # fmt: off
        pytest.param(3., 3, False, "triplet"),
        pytest.param(3., 3, True, "triplet"),
        # fmt: on
    ],
)
def test_mol_multiplicity_types(mult_in, mult_store, validate, exp_hash):
    # validate=False passes through pydantic validators. =True passes through molparse.

    mol_args = {"symbols": ["He"], "geometry": [0, 0, 0], "validate": validate}
    if mult_in is not None:
        mol_args["molecular_multiplicity"] = mult_in

    mol = qcel.models.Molecule(**mol_args)

    assert mult_store == mol.molecular_multiplicity
    assert type(mult_store) is type(mol.molecular_multiplicity)
    assert mol.get_hash()[:8] == _ref_mol_multiplicity_hash[exp_hash]


@pytest.mark.parametrize(
    "mult_in,validate,error",
    [
        pytest.param(-3, False, "Multiplicity must be positive"),
        pytest.param(-3, True, "Multiplicity must be positive"),
        pytest.param(0.9, False, "Multiplicity must be positive"),
        pytest.param(0.9, True, "Multiplicity must be positive"),
        pytest.param(3.1, True, "Inconsistent or unspecified chg/mult"),  # insufficient electrons in He
    ],
)
def test_mol_multiplicity_types_errors(mult_in, validate, error):
    mol_args = {"symbols": ["He"], "geometry": [0, 0, 0], "validate": validate}
    if mult_in is not None:
        mol_args["molecular_multiplicity"] = mult_in

    with pytest.raises((ValueError, qcel.ValidationError)) as e:
        qcel.models.Molecule(**mol_args)

    assert error in str(e.value)


@pytest.mark.parametrize(
    "mol_mult_in,mult_in,mult_store,validate,exp_hash",
    [
        pytest.param(5, [3, 3], [3, 3], False, "ditriplet"),
        pytest.param(5, [3, 3], [3, 3], True, "ditriplet"),
        # before float multiplicity was allowed, [3.1, 3.4] (below) were coerced into [3, 3] with validate=False.
        #   Now, [2.9, 2.9] is allowed for both validate=T/F.
        pytest.param(5, [3.1, 3.4], [3.1, 3.4], False, "ditriplet_point1"),
        pytest.param(5, [2.99999, 3.00001], [2.99999, 3.00001], False, "ditriplet_point00001"),
        pytest.param(5, [2.99999, 3.00001], [2.99999, 3.00001], True, "ditriplet_point00001"),
        # fmt: off
        pytest.param(5, [3.0, 3.], [3, 3], False, "ditriplet"),
        pytest.param(5, [3.0, 3.], [3, 3], True, "ditriplet"),
        # fmt: on
        pytest.param(1, [1, 1], [1, 1], False, "disinglet"),
        pytest.param(1, [1, 1], [1, 1], True, "disinglet"),
        # None in frag_mult not allowed for validate=False
        pytest.param(1, [None, None], [1, 1], True, "disinglet"),
        pytest.param(1, [1.000000000000000000002, 0.999999999999999999998], [1, 1], False, "disinglet"),
        pytest.param(1, [1.000000000000000000002, 0.999999999999999999998], [1, 1], True, "disinglet"),
        pytest.param(
            1,
            [1.000000000000002, 1.000000000000004],
            [1.000000000000002, 1.000000000000004],
            False,
            "disinglet_epsilon",
        ),
        pytest.param(
            1, [1.000000000000002, 1.000000000000004], [1.000000000000002, 1.000000000000004], True, "disinglet_epsilon"
        ),
    ],
)
def test_frag_multiplicity_types(mol_mult_in, mult_in, mult_store, validate, exp_hash):
    # validate=False passes through pydantic validators. =True passes through molparse.

    mol_args = {
        "symbols": ["He", "Ne"],
        "geometry": [0, 0, 0, 2, 0, 0],
        "fragments": [[0], [1]],
        "validate": validate,
        # below three passed in so hashes match btwn validate=T/F. otherwise, validate=False never
        #   populates these fields
        "molecular_charge": 0,
        "fragment_charges": [0, 0],
        "molecular_multiplicity": mol_mult_in,
    }
    if mult_in is not None:
        mol_args["fragment_multiplicities"] = mult_in

    mol = qcel.models.Molecule(**mol_args)

    assert mult_store == mol.fragment_multiplicities
    assert type(mult_store) is type(mol.fragment_multiplicities)
    assert mol.get_hash()[:8] == _ref_mol_multiplicity_hash[exp_hash]


@pytest.mark.parametrize(
    "mult_in,validate,error",
    [
        pytest.param([-3, 1], False, "Multiplicity must be positive"),
        pytest.param([-3, 1], True, "Multiplicity must be positive"),
        pytest.param(
            [3.1, 3.4], True, "Inconsistent or unspecified chg/mult"
        ),  # insufficient e- for triplet+ on He in frag 1
    ],
)
def test_frag_multiplicity_types_errors(mult_in, validate, error):
    mol_args = {"symbols": ["He", "Ne"], "geometry": [0, 0, 0, 2, 0, 0], "fragments": [[0], [1]], "validate": validate}
    if mult_in is not None:
        mol_args["fragment_multiplicities"] = mult_in

    with pytest.raises((ValueError, qcel.ValidationError)) as e:
        qcel.models.Molecule(**mol_args)

    assert error in str(e.value)


_one_helium_mass = 4.00260325413


@pytest.mark.parametrize(
    "mol_string,args,formula,formula_dict,molecular_weight,nelec,nre",
    [
        ("He 0 0 0", {}, "He", {"He": 1}, _one_helium_mass, 2, 0.0),
        ("He 0 0 0\n--\nHe 0 0 5", {}, "He2", {"He": 2}, 2 * _one_helium_mass, 4, 0.4233417684),
        ("He 0 0 0\n--\n@He 0 0 5", {}, "He2", {"He": 1}, _one_helium_mass, 2, 0.0),
        ("He 0 0 0\n--\n@He 0 0 5", {"ifr": 0}, "He2", {"He": 1}, _one_helium_mass, 2, 0.0),
        ("He 0 0 0\n--\n@He 0 0 5", {"ifr": 1}, "He2", {}, 0.0, 0, 0.0),
        ("He 0 0 0\n--\n@He 0 0 5", {"real_only": False}, "He2", {"He": 2}, 2 * _one_helium_mass, 4, 0.4233417684),
        ("He 0 0 0\n--\n@He 0 0 5", {"real_only": False, "ifr": 0}, "He2", {"He": 1}, _one_helium_mass, 2, 0.0),
        ("He 0 0 0\n--\n@He 0 0 5", {"real_only": False, "ifr": 1}, "He2", {"He": 1}, _one_helium_mass, 2, 0.0),
        ("4He 0 0 0", {}, "He", {"He": 1}, _one_helium_mass, 2, 0.0),
        ("5He4 0 0 0", {}, "He", {"He": 1}, 5.012057, 2, 0.0),  # suffix-4 is label
        ("He@3.14 0 0 0", {}, "He", {"He": 1}, 3.14, 2, 0.0),
    ],
)
def test_molecular_weight(mol_string, args, formula, formula_dict, molecular_weight, nelec, nre):
    mol = Molecule.from_data(mol_string)

    assert mol.molecular_weight(**args) == molecular_weight, f"molecular_weight: ret != {molecular_weight}"
    assert mol.nelectrons(**args) == nelec, f"nelectrons: ret != {nelec}"
    assert abs(mol.nuclear_repulsion_energy(**args) - nre) < 1.0e-5, f"nre: ret != {nre}"
    assert mol.element_composition(**args) == formula_dict, f"element_composition: ret != {formula_dict}"
    assert mol.get_molecular_formula() == formula, f"get_molecular_formula: ret != {formula}"

    # after py38
    # assert (ret := mol.molecular_weight(**args)) == molecular_weight, f"molecular_weight: {ret} != {molecular_weight}"
    # assert (ret := mol.nelectrons(**args)) == nelec, f"nelectrons: {ret} != {nelec}"
    # assert (abs(ret := mol.nuclear_repulsion_energy(**args)) - nre) < 1.0e-5, f"nre: {ret} != {nre}"
    # assert (ret := mol.element_composition(**args)) == formula_dict, f"element_composition: {ret} != {formula_dict}"
    # assert (ret := mol.get_molecular_formula()) == formula, f"get_molecular_formula: {ret} != {formula}"
