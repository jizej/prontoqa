import fol
from theory import *
import numpy as np
from enum import Enum
from random import choice, random, shuffle
import itertools

class ProofStepType(Enum):
	AXIOM = 0
	UNIVERSAL_INSTANTIATION = 1 # given ![x]:(f(x) -> g(x)) and f(a), conclude g(a)
	CONJUNCTION_INTRODUCTION = 2 # given A_1, ..., A_n, conclude A_1 & ... & A_n
	CONJUNCTION_ELIMINATION = 3 # given A_1 & ... & A_n, conclude A_i
	DISJUNCTION_INTRODUCTION = 4 # given A_i, conclude A_1 | ... | A_n
	DISJUNCTION_ELIMINATION = 5 # given A or B, A proves C, B proves C, conclude C
	PROOF_BY_CONTRADICTION = 6 # given A, B proves ~A, conclude ~B

class ProofStep(object):
	def __init__(self, step_type, premises, conclusion):
		self.step_type = step_type
		self.premises = premises
		self.conclusion = conclusion

def get_nodes(theory, level=0):
	nodes = [(theory, level)]
	for child in theory.children:
		nodes.extend(get_nodes(child, level + 1))
	return nodes

def generate_membership_question(theories, entity_name, num_deduction_steps=None, generate_questions_about_types=True, generate_questions_about_properties=True, deduction_rule="ModusPonens", use_dfs=True, proof_width=2):
	nodes = get_nodes(theories[0])
	max_level = 0
	for _, level in nodes:
		max_level = max(max_level, level)
	sufficiently_deep_nodes = []
	for node, level in nodes:
		if level + 1 >= num_deduction_steps and (deduction_rule != "AndElim" or len(node.children) != 0):
			sufficiently_deep_nodes.append(node)
	if len(sufficiently_deep_nodes) == 0:
		return (None, None, None, None, None)
	start = choice(sufficiently_deep_nodes)

	if deduction_rule == "AndElim":
		child = choice(start.children)
		properties = [fol.FOLFuncApplication(property, [fol.FOLConstant(entity_name)]) for property in child.properties]
		properties += [fol.FOLNot(fol.FOLFuncApplication(property, [fol.FOLConstant(entity_name)])) for property in child.negated_properties]
		if len(properties) != max(proof_width, 2) - 2:
			raise ValueError("Expected exactly {} defining propert{}.".format(max(proof_width, 2) - 2, "y" if proof_width == 2 else "ies"))
		other_conjuncts = [fol.FOLFuncApplication(parent.name, [fol.FOLConstant(entity_name)]) for parent in start.parents[1:]] + [fol.FOLFuncApplication(start.name, [fol.FOLConstant(entity_name)])]
		shuffle(other_conjuncts)
		start_formula = fol.FOLAnd(properties + other_conjuncts)

		distractor_child = choice(theories[1].children)
		distractor_properties = [fol.FOLFuncApplication(property, [fol.FOLConstant(entity_name)]) for property in distractor_child.properties]
		distractor_properties += [fol.FOLNot(fol.FOLFuncApplication(property, [fol.FOLConstant(entity_name)])) for property in distractor_child.negated_properties]
		other_conjuncts = [fol.FOLFuncApplication(parent.name, [fol.FOLConstant(entity_name)]) for parent in distractor_child.parents]
		shuffle(other_conjuncts)
		if len(distractor_properties) != max(proof_width, 2) - 2:
			raise ValueError("Expected exactly {} defining propert{}.".format(max(proof_width, 2) - 2, "y" if proof_width == 2 else "ies"))
		distractor_formula = fol.FOLAnd(distractor_properties + other_conjuncts)
	else:
		start_formula = fol.FOLFuncApplication(start.name, [fol.FOLConstant(entity_name)])
		distractor_child = choice(theories[1].children)
		distractor_formula = fol.FOLFuncApplication(distractor_child.name, [fol.FOLConstant(entity_name)])
	premises = [start_formula, distractor_formula]
	start_axiom = ProofStep(ProofStepType.AXIOM, [], start_formula)
	current_node = start
	current_step = start_axiom
	current_num_steps = 1

	branch_points = []
	while True:
		if deduction_rule == "ModusPonens" and len(current_node.parents) == 1:
			# make sure there is at least one distractor at each hop
			return (None, None, None, None, None)
		elif deduction_rule == "AndElim" and not any([len(parent.parents) > 1 for parent in current_node.parents[1:]]):
			# make sure there is at least one distractor at each hop
			return (None, None, None, None, None)
		if len(current_node.parents) == 0:
			true_parent = None
		else:
			true_parent = current_node.parents[0]

		if deduction_rule == "AndIntro":
			if true_parent == None:
				if not generate_questions_about_types:
					return (None, None, None, None, None)
				break
			subsumption_formulas = get_subsumption_formula(current_node, deduction_rule)
			other_axioms = []
			other_axiom_steps = []
			for operand in subsumption_formulas[0].operand.antecedent.operands:
				other_axiom = fol.substitute(operand, fol.FOLVariable(1), fol.FOLConstant(entity_name))
				if other_axiom == current_step.conclusion:
					continue
				other_axiom_step = ProofStep(ProofStepType.AXIOM, [], other_axiom)
				other_axioms.append(other_axiom)
				other_axiom_steps.append(other_axiom_step)
				if other_axiom not in premises:
					premises.append(other_axiom)
			intro_step_conclusion = fol.substitute(subsumption_formulas[0].operand.antecedent, fol.FOLVariable(1), fol.FOLConstant(entity_name))
			current_step = ProofStep(ProofStepType.CONJUNCTION_INTRODUCTION, other_axiom_steps + [current_step], intro_step_conclusion)

			current_num_steps += 1
			if generate_questions_about_types and ((num_deduction_steps != None and current_num_steps == num_deduction_steps) or (num_deduction_steps == None and random() < 0.3)):
				break

			subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formulas[0])
			conclusion = fol.FOLFuncApplication(true_parent.name, [fol.FOLConstant(entity_name)])
			next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, current_step], conclusion)

			current_node = true_parent
			current_step = next_step

			# make sure to add distractor axioms for the distractor subsumption formulas (so they are not so easily identifiable)
			for distractor_formula in subsumption_formulas[1:]:
				for operand in distractor_formula.operand.antecedent.operands:
					other_axiom = fol.substitute(operand, fol.FOLVariable(1), fol.FOLConstant(entity_name))
					if other_axiom not in premises:
						premises.append(other_axiom)

		elif deduction_rule == "AndElim":
			if true_parent == None:
				if not generate_questions_about_types:
					return (None, None, None, None, None)
				break
			elim_step_conclusion = fol.FOLFuncApplication(current_node.name, [fol.FOLConstant(entity_name)])
			current_step = ProofStep(ProofStepType.CONJUNCTION_ELIMINATION, [current_step], elim_step_conclusion)

			current_num_steps += 1
			if generate_questions_about_types and ((num_deduction_steps != None and current_num_steps == num_deduction_steps) or (num_deduction_steps == None and random() < 0.3)):
				break

			subsumption_formula = get_subsumption_formula(current_node, deduction_rule)[0]
			subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formula)
			conclusion = fol.substitute(subsumption_formula.operand.consequent, fol.FOLVariable(1), fol.FOLConstant(entity_name))
			next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, current_step], conclusion)

			current_node = true_parent
			current_step = next_step

		elif deduction_rule == "OrIntro":
			if true_parent == None:
				if not generate_questions_about_types:
					return (None, None, None, None, None)
				break
			subsumption_formulas = get_subsumption_formula(current_node, deduction_rule)
			other_axioms = []
			for operand in subsumption_formulas[0].operand.antecedent.operands:
				other_axiom = fol.substitute(operand, fol.FOLVariable(1), fol.FOLConstant(entity_name))
				if other_axiom == current_step.conclusion:
					continue
				other_axioms.append(other_axiom)
			intro_step_conclusion = fol.FOLOr(other_axioms + [current_step.conclusion])
			current_step = ProofStep(ProofStepType.DISJUNCTION_INTRODUCTION, [current_step], intro_step_conclusion)

			current_num_steps += 1
			if generate_questions_about_types and ((num_deduction_steps != None and current_num_steps == num_deduction_steps) or (num_deduction_steps == None and random() < 0.3)):
				break

			subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formulas[0])
			conclusion = fol.FOLFuncApplication(true_parent.name, [fol.FOLConstant(entity_name)])
			next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, current_step], conclusion)

			current_node = true_parent
			current_step = next_step

		else:
			property_question_weight = 0.3 if generate_questions_about_properties else 0.0
			negated_property_question_weight = 0.7 if generate_questions_about_properties else 0.0
			probabilities = [1] + [property_question_weight] * len(current_node.properties) + [negated_property_question_weight] * len(current_node.negated_properties)
			probabilities = np.array(probabilities) / np.sum(probabilities)
			index = np.random.choice(1 + len(current_node.properties) + len(current_node.negated_properties), p=probabilities)
			if (1 if true_parent != None else 0) + len(current_node.properties) + len(current_node.negated_properties) > 1:
				branch_points.append(current_node)
			if index == 0:
				if true_parent == None:
					if not generate_questions_about_types:
						return (None, None, None, None, None)
					break
				subsumption_formula = get_subsumption_formula(current_node, deduction_rule)[0]
				subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formula)
				conclusion = fol.FOLFuncApplication(true_parent.name, [fol.FOLConstant(entity_name)])
				next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, current_step], conclusion)

				current_node = true_parent
				current_step = next_step
				current_num_steps += 1
				if generate_questions_about_types and ((num_deduction_steps != None and current_num_steps == num_deduction_steps) or (num_deduction_steps == None and random() < 0.3)):
					break

			elif index == 1:
				index -= 1
				properties_formulas = []
				get_properties_formula(properties_formulas, current_node, deduction_rule)
				properties_formula = properties_formulas[0]
				properties_step = ProofStep(ProofStepType.AXIOM, [], properties_formula)
				conclusion = fol.substitute(properties_formula.operand.consequent, fol.FOLVariable(1), fol.FOLConstant(entity_name))
				next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [properties_step, current_step], conclusion)
				current_step = next_step
				current_num_steps += 1

				if type(conclusion) == fol.FOLAnd:
					current_step = ProofStep(ProofStepType.CONJUNCTION_ELIMINATION, [current_step], fol.FOLFuncApplication(current_node.properties[index], [fol.FOLConstant(entity_name)]))
					current_num_steps += 1
				break

			else:
				index -= 1 + len(current_node.properties)
				properties_formulas = []
				get_properties_formula(properties_formulas, current_node, deduction_rule)
				properties_formula = properties_formulas[0]
				properties_step = ProofStep(ProofStepType.AXIOM, [], properties_formula)
				conclusion = fol.substitute(properties_formula.operand.consequent, fol.FOLVariable(1), fol.FOLConstant(entity_name))
				next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [properties_step, current_step], conclusion)
				current_step = next_step
				current_num_steps += 1

				if type(conclusion) == fol.FOLAnd:
					current_step = ProofStep(ProofStepType.CONJUNCTION_ELIMINATION, [current_step], fol.FOLNot(fol.FOLFuncApplication(current_node.properties[index], [fol.FOLConstant(entity_name)])))
					current_num_steps += 1
				break

	linearized_proof = linearize_proof_steps(current_step)
	if use_dfs and len(branch_points) > 0:
		branch_index = 0
		for step in linearized_proof:
			if type(step.conclusion) == fol.FOLFuncApplication and step.conclusion.function == branch_points[-1].name:
				break
			branch_index += 1
		dfs_node = branch_points[-1]
		dfs_step = linearized_proof[branch_index]

		dfs_proof = []
		while True:
			subsumption_formula_count = (len(dfs_node.parents) if deduction_rule == "ModusPonens" else 1)
			probabilities = [subsumption_formula_count] * len(dfs_node.parents) + [1] * len(dfs_node.properties) + [1] * len(dfs_node.negated_properties)
			if np.sum(probabilities) == 0:
				break
			probabilities = np.array(probabilities) / np.sum(probabilities)
			index = np.random.choice(1 + len(dfs_node.properties) + len(dfs_node.negated_properties), p=probabilities)
			if index < subsumption_formula_count:
				subsumption_formula = get_subsumption_formula(dfs_node, deduction_rule)[index]
				subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formula)
				dfs_proof.append(subsumption_step)
				conclusion = fol.FOLFuncApplication(dfs_node.parents[index].name, [fol.FOLConstant(entity_name)])
				next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, dfs_step], conclusion)

				dfs_node = dfs_node.parents[index]
				dfs_step = next_step
				dfs_proof.append(dfs_step)

			elif index < subsumption_formula_count + len(dfs_node.properties):
				index -= subsumption_formula_count
				properties_formulas = []
				get_properties_formula(properties_formulas, dfs_node, deduction_rule)
				properties_formula = properties_formulas[0]
				properties_step = ProofStep(ProofStepType.AXIOM, [], properties_formula)
				dfs_proof.append(properties_step)
				conclusion = fol.substitute(properties_formula.operand.consequent, fol.FOLVariable(1), fol.FOLConstant(entity_name))
				next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [properties_step, dfs_step], conclusion)
				dfs_step = next_step
				dfs_proof.append(dfs_step)

				if type(conclusion) == fol.FOLAnd:
					dfs_step = ProofStep(ProofStepType.CONJUNCTION_ELIMINATION, [dfs_step], fol.FOLFuncApplication(dfs_node.properties[index], [fol.FOLConstant(entity_name)]))
					dfs_proof.append(dfs_step)
				break

			else:
				index -= subsumption_formula_count + len(dfs_node.properties)
				properties_formulas = []
				get_properties_formula(properties_formulas, dfs_node, deduction_rule)
				properties_formula = properties_formulas[0]
				properties_step = ProofStep(ProofStepType.AXIOM, [], properties_formula)
				dfs_proof.append(properties_step)
				conclusion = fol.substitute(properties_formula.operand.consequent, fol.FOLVariable(1), fol.FOLConstant(entity_name))
				next_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [properties_step, dfs_step], conclusion)
				dfs_step = next_step
				dfs_proof.append(dfs_step)

				if type(conclusion) == fol.FOLAnd:
					dfs_step = ProofStep(ProofStepType.CONJUNCTION_ELIMINATION, [dfs_step], fol.FOLNot(fol.FOLFuncApplication(dfs_node.negated_properties[index], [fol.FOLConstant(entity_name)])))
					dfs_proof.append(dfs_step)
				break

		if dfs_proof[0] != linearized_proof[branch_index + 1]:
			linearized_proof[(branch_index + 1):(branch_index + 1)] = dfs_proof

	shuffle(premises)
	return (premises, current_step.conclusion, current_step, current_num_steps, linearized_proof)

def generate_de_morgans_question(theories, entity_name, distractor_concept, num_deduction_steps=None, proof_width=2):
	assert(num_deduction_steps - 1 == 1)

	theory = theories[0]

	premise = fol.FOLNot(fol.FOLFuncApplication(theory.name, [fol.FOLConstant(entity_name)]))
	premise_axiom = ProofStep(ProofStepType.AXIOM, [], premise)
	distractor_premise = fol.FOLNot(fol.FOLFuncApplication(distractor_concept, [fol.FOLConstant(entity_name)]))
	antecedent_formula = fol.FOLOr([fol.FOLFuncApplication(child.name, [fol.FOLVariable(1)]) for child in theory.children[:proof_width]])
	grounded_antecedent_formula = fol.substitute(antecedent_formula, fol.FOLVariable(1), fol.FOLConstant(entity_name))
	subsumption_formula = fol.FOLForAll(1, fol.FOLIfThen(antecedent_formula, fol.FOLFuncApplication(theory.name, [fol.FOLVariable(1)])))
	subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formula)

	subproofs = []
	for i in range(proof_width):
		assumption_formula = fol.FOLFuncApplication(theory.children[i].name, [fol.FOLConstant(entity_name)])
		assumption = ProofStep(ProofStepType.AXIOM, [], fol.FOLFuncApplication("ASSUME", [assumption_formula]))
		disjunction_intro = ProofStep(ProofStepType.DISJUNCTION_INTRODUCTION, [assumption], grounded_antecedent_formula)
		instantiation_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, disjunction_intro], fol.FOLFuncApplication(theory.name, [fol.FOLConstant(entity_name)]))
		contradiction_step = ProofStep(ProofStepType.PROOF_BY_CONTRADICTION, [premise_axiom, instantiation_step], fol.FOLNot(assumption_formula))
		subproofs.append(contradiction_step)

	proof = ProofStep(ProofStepType.CONJUNCTION_INTRODUCTION, subproofs, fol.FOLAnd([subproof.conclusion for subproof in subproofs][::-1]))

	premises = [premise, distractor_premise]
	shuffle(premises)
	return (premises, proof.conclusion, proof, num_deduction_steps, linearize_proof_steps(proof))


def generate_proof_by_cases_question(theories, entity_name, num_deduction_steps=None, proof_width=2):
	assert num_deduction_steps - 1 == 1

	theory = theories[0] # generate the question from the non-distractor ontology
	distractor_theory = theories[1]
	premise = fol.FOLOr([fol.FOLFuncApplication(child.name, [fol.FOLConstant(entity_name)]) for child in theory.children[:proof_width]])
	distractor_premise = fol.FOLOr([fol.FOLFuncApplication(child.name, [fol.FOLConstant(entity_name)]) for child in distractor_theory.children[:proof_width]])
	premise_axiom = ProofStep(ProofStepType.AXIOM, [], premise)
	
	subproofs = []
	for i in range(proof_width):
		assumption_formula = fol.FOLFuncApplication(theory.children[i].name, [fol.FOLConstant(entity_name)])
		assumption = ProofStep(ProofStepType.AXIOM, [], fol.FOLFuncApplication("ASSUME", [assumption_formula]))
		subsumption_formula = fol.FOLForAll(1, fol.FOLIfThen(
			fol.FOLFuncApplication(theory.children[i].name, [fol.FOLVariable(1)]),
			fol.FOLFuncApplication(theory.name, [fol.FOLVariable(1)])
		))
		subsumption_step = ProofStep(ProofStepType.AXIOM, [], subsumption_formula)
		instantiation_step = ProofStep(ProofStepType.UNIVERSAL_INSTANTIATION, [subsumption_step, assumption], fol.FOLFuncApplication(theory.name, [fol.FOLConstant(entity_name)]))
		subproofs.append(instantiation_step)

	proof = ProofStep(ProofStepType.DISJUNCTION_ELIMINATION, subproofs + [premise_axiom], fol.FOLFuncApplication(theory.name, [fol.FOLConstant(entity_name)]))

	premises = [premise, distractor_premise]
	shuffle(premises)
	#premises = [distractor_premise, premise] # uncomment to test what happens if the order of these two sentences is fixed
	return (premises, proof.conclusion, proof, num_deduction_steps, linearize_proof_steps(proof))


def linearize_proof_steps(last_step):
	if last_step.step_type == ProofStepType.AXIOM:
		return [last_step]
	elif last_step.step_type == ProofStepType.UNIVERSAL_INSTANTIATION:
		return linearize_proof_steps(last_step.premises[1]) + linearize_proof_steps(last_step.premises[0]) + [last_step]
	elif last_step.step_type == ProofStepType.CONJUNCTION_INTRODUCTION:
		return list(itertools.chain.from_iterable([linearize_proof_steps(premise) for premise in reversed(last_step.premises)])) + [last_step]
	elif last_step.step_type == ProofStepType.PROOF_BY_CONTRADICTION:
		contradicts_step = ProofStep(ProofStepType.AXIOM, [], fol.FOLFuncApplication("CONTRADICTS", [last_step.premises[0].conclusion]))
		return linearize_proof_steps(last_step.premises[1]) + [contradicts_step, last_step]
	elif last_step.step_type == ProofStepType.DISJUNCTION_ELIMINATION:
		prev_steps = list(itertools.chain.from_iterable([linearize_proof_steps(premise) for premise in last_step.premises[:-1]]))
		elim_step = ProofStep(ProofStepType.DISJUNCTION_ELIMINATION, last_step.premises[:-1], fol.FOLFuncApplication("SINCE", [last_step.premises[-1].conclusion, last_step.conclusion]))
		return prev_steps + [elim_step]
	else:
		return list(itertools.chain.from_iterable([linearize_proof_steps(premise) for premise in last_step.premises])) + [last_step]
