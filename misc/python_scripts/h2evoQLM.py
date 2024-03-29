#!/usr/bin/env python
import os
os.environ["TMPDIR"] = "/tmp"  # set the folder for temporary files
import numpy as np

import warnings
warnings.simplefilter('ignore', category=FutureWarning)


from qiskit_nature.drivers import Molecule, UnitsType
from qiskit_nature.drivers.second_quantization import PySCFDriver, GaussianForcesDriver

from qiskit_nature.problems.second_quantization import ElectronicStructureProblem
from qiskit_nature.converters.second_quantization import QubitConverter
from qiskit_nature.mappers.second_quantization import JordanWignerMapper, ParityMapper, DirectMapper



#### MODIFICATION TO USE MYQLM
from qat.qpus import PyLinalg
from qiskit_mod.wrapper2myqlm import run_QLM_stack
from qiskit_mod.my_junction import IterativeExplorationEvoVQE,get_energy_evaluation_QLM
from qiskit.algorithms import VQE
VQE.get_energy_evaluation = get_energy_evaluation_QLM #override the function, class-wide

use_remote = True

if use_remote:
    from qlmaas.qpus import LinAlg
    from qlmaas.plugins import IterativeExplorationEvoVQE as IterativeExplorationEvoVQEremote
    qlm_qpu = LinAlg() #remote
    plugin_in_use = IterativeExplorationEvoVQEremote
else:
    qlm_qpu = PyLinalg() #local
    plugin_in_use = IterativeExplorationEvoVQE
####

driver = PySCFDriver(atom="H .0 .0 .0; H .0 .0 0.735", charge=0, spin=0, unit=UnitsType.ANGSTROM, basis='sto3g')
problem = ElectronicStructureProblem(driver)

# generate the second-quantized operators
elop = problem.second_q_ops()

converter = QubitConverter(mapper=JordanWignerMapper())
q_elop = converter.convert(elop[0])

# setup the initial state for the ansatz
from qiskit_nature.circuit.library import HartreeFock

# PARTICLE NUMBER
particle_number = problem.properties_transformed.get_property("ParticleNumber")
num_particles = (particle_number.num_alpha, particle_number.num_beta)
num_spin_orbitals = particle_number.num_spin_orbitals

init_state = HartreeFock(num_spin_orbitals, num_particles, converter)

# setup the ansatz for VQE
from qiskit.circuit.library import TwoLocal

ansatz = TwoLocal(num_spin_orbitals, ['ry', 'rz'], 'cz',reps=2)

# add the initial state
ansatz.compose(init_state, front=True)

# setup the classical optimizer for VQE
from qiskit.algorithms.optimizers import L_BFGS_B, CG
optimizer = L_BFGS_B()

# setup and run VQE
from qiskit_mod.qiskit_ter import LinCombFullmod,LinCombMod, EvoVQE

# set the backend for the quantum computation
from qiskit.utils import QuantumInstance
from qiskit import Aer, BasicAer
be_options = {"max_parallel_threads":8,"max_parallel_experiments":0, "statevector_parallel_threshold":4}
qinstance = QuantumInstance(Aer.get_backend('statevector_simulator'), shots=1, seed_simulator=2, 
                                                 seed_transpiler=2, backend_options = be_options)

vqe = EvoVQE(ansatz, optimizer=optimizer, quantum_instance=qinstance)

#MYQLM addition to create the stack
stack = plugin_in_use(method=vqe,
                      execute_function='compute_evolve',
                      operator=q_elop,
                      shots=0
                      ) | qlm_qpu

result = run_QLM_stack(stack)

# result = vqe.compute_evolve(q_elop)

electronic_structure_result = problem.interpret(result)
print(electronic_structure_result)
