#! /usr/bin/env python

##############################################################################
##  DendroPy Phylogenetic Computing Library.
##
##  Copyright 2010-2014 Jeet Sukumaran and Mark T. Holder.
##  All rights reserved.
##
##  See "LICENSE.txt" for terms and conditions of usage.
##
##  If you use this work or any portion thereof in published work,
##  please cite it as:
##
##     Sukumaran, J. and M. T. Holder. 2010. DendroPy: a Python library
##     for phylogenetic computing. Bioinformatics 26: 1569-1571.
##
##############################################################################

"""
Models, modeling and model-fitting of the Protracted Speciation Process.
"""

import itertools
import dendropy
from dendropy.utility import GLOBAL_RNG
from dendropy.utility.error import TreeSimTotalExtinctionException
from dendropy.calculate import probability

class ProtractedSpeciationModel(object):

    class ProcessFailedException(TreeSimTotalExtinctionException):
        pass

    class ProtractedSpeciationModelLineage(object):

        def __init__(self,
                index,
                parent_lineage,
                speciation_initiation_time,
                is_full_species):
            self._index = index
            self.is_full_species = is_full_species
            self.parent_lineage = parent_lineage
            self.speciation_initiation_time = speciation_initiation_time
            self.speciation_completion_time = None
            self.extinction_time = None
            self.psm_tree_node_history = []
            self._label = "L{}".format(self._index)

        def _get_node(self):
            return self.psm_tree_node_history[-1]
        def _set_node(self, node):
            self.psm_tree_node_history.append(node)
        node = property(_get_node, _set_node)

        def _get_index(self):
            return self._index
        index = property(_get_index)

        def _get_label(self):
            return self._label
        label = property(_get_label)

    def __init__(self,
            full_species_birth_rate,
            full_species_extinction_rate,
            incipient_species_birth_rate,
            incipient_species_conversion_rate,
            incipient_species_extinction_rate,
            rng=None,
            ):
        self.full_species_birth_rate = full_species_birth_rate
        self.full_species_extinction_rate = full_species_extinction_rate
        self.incipient_species_birth_rate = incipient_species_birth_rate
        self.incipient_species_conversion_rate = incipient_species_conversion_rate
        self.incipient_species_extinction_rate = incipient_species_extinction_rate
        if rng is None:
            self.rng = GLOBAL_RNG
        else:
            self.rng = rng
        self.tree_factory = dendropy.Tree
        self.node_factory = dendropy.Node
        self.reset()

    def reset(self):
        self.current_time = 0.0
        self.current_lineage_index = 0
        self.current_node_index = 0
        self.current_full_species_lineages = []
        self.current_incipient_species_lineages = []
        self._all_lineages = []

    def generate_sample(self, **kwargs):
        """

        Samples from the Protracted Speciation Model process, returning a tuple of trees.

        -   The unpruned PSM tree: this tree has all nodes/lineages, i.e. both
            full species as well as incipient species. Nodes on the tree which
            represent full/good/true speciation events will have the attribute
            ``is_full_speciation_event`` set to `True`, while this attribute will
            be set to `False` otherwise. Each node has an attribute added,
            ``protracted_speciation_model_lineage``, which is a reference to a
            :class:`~dendropy.model.birthdeath.ProtractedSpeciationModel.ProtractedSpeciationModelLineage`
            instance which represents the lineage associated with this node
            (note that each node can only be associated with a single lineage,
            but a lineage might span several nodes).

        -   The pruned tree: the tree only has full species. Each node has an
            ``protracted_speciation_model_lineage`` attribute, as above, and
            also a ``protracted_speciation_model_tree_node`` attribute, which
            points to the corresponding node on the unpruned protracted
            speciation tree, anove.

        Parameters
        ----------

        max_time : float or `None`
            Terminate and return results when this time is reached. If `None`,
            then do not terminated based on run time.
        max_full_species_tree_leaf_nodes : int or `None`
            Terminate and return results when this number of tips are found in
            the full-species tree (i.e., the pruned tree consisting of only
            "full" or "good" species). If `None`, then do not terminate
            based on the number of tipes on the full-species tree.
        max_protracted_speciation_tree_leaf_nodes : int or `None`
            Terminate and return results when this number of tips are found in
            the incipient tree (i.e. the tree with both incipient and full
            species). If `None`, then do not terminate based on the
            number of tipes on the incipient species tree.
        is_initial_species_incipient : bool
            Whether the first lineage that initialies the process is an
            incipient or full species. Defaults to `False`: first species on
            the tree is a full species.
        is_retry_on_total_extinction : bool
            If ``False``, then a TreeSimTotalExtinctionException will be raised
            if all lineages go extinct before the termination conditions are
            met. Defaults to ``True``: if all lineages go extinct before the
            termination conditions are met, then the simulation is rerun, up to
            a maximum of ``max_retries``.
        max_retries : int
            Maximum number of runs to execute in the event of
            prematurely-terminated simulations due to all lineages going
            extinct. Once this number or re-runs is exceed, then
            TreeSimTotalExtinctionException is raised. Defaults to 1000. Set to
            ``None`` to never quit trying.

        Returns
        -------
        protracted_speciation_tree : |Tree| instance
            A tree from the protracted speciation process, with all lineages
            (full species as well as incipient species).
        pruned_tree : |Tree| instance
            A tree from the protracted speciation process with only full species.

        """
        is_retry_on_total_extinction = kwargs.pop("is_retry_on_total_extinction", True)
        max_retries = kwargs.pop("max_retries", 1000)
        num_retries = 0
        psm_tree = None
        pruned_tree = None
        while True:
            try:
                psm_tree, pruned_tree = self._run_protracted_speciation_process(**kwargs)
                break
            except TreeSimTotalExtinctionException:
                if not is_retry_on_total_extinction:
                    raise
                num_retries += 1
                if max_retries is not None and num_retries > max_retries:
                    raise
        assert psm_tree is not None
        return psm_tree, pruned_tree

    def _run_protracted_speciation_process(self, **kwargs):
        self.reset()
        max_time = kwargs.get("max_time", None)
        max_protracted_speciation_tree_leaf_nodes = kwargs.get("max_protracted_speciation_tree_leaf_nodes", None)
        max_full_species_tree_leaf_nodes = kwargs.get("max_full_species_tree_leaf_nodes", None)
        taxon_namespace = kwargs.get("taxon_namespace", None)

        is_full_species = not kwargs.get("is_initial_species_incipient", False)
        if is_full_species:
            initial_lineage = self._new_lineage(parent_lineage=None, is_full_species=True)
        else:
            initial_lineage = self._new_lineage(parent_lineage=None, is_full_species=False)
        seed_node = self._new_node(lineage=initial_lineage)
        psm_tree = self.tree_factory( taxon_namespace=taxon_namespace, seed_node=seed_node)
        psm_tree.is_rooted = True

        while True:

            ## Draw time to next event
            event_rates = []
            num_full_species = len(self.current_full_species_lineages)
            if max_full_species_tree_leaf_nodes is not None:
                ## note: expensive operation to count leaves!
                try:
                    pruned_tree = self._assemble_pruned_tree(taxon_namespace=taxon_namespace)
                    num_leaves = len(pruned_tree.leaf_nodes())
                    if num_leaves >= max_full_species_tree_leaf_nodes:
                        return self._postprocess_pruned_and_psm_trees(
                                pruned_tree=pruned_tree,
                                psm_tree=psm_tree)
                except ProtractedSpeciationModel.ProcessFailedException:
                    pass

            num_incipient_species = len(self.current_incipient_species_lineages)
            if max_protracted_speciation_tree_leaf_nodes is not None and (num_incipient_species + num_full_species) >= max_protracted_speciation_tree_leaf_nodes:
                break

            # Event type 0
            event_rates.append(self.full_species_birth_rate * num_full_species)

            # Event type 1
            event_rates.append(self.full_species_extinction_rate * num_full_species)

            # Event type 2
            event_rates.append(self.incipient_species_birth_rate * num_incipient_species)

            # Event type 3
            event_rates.append(self.incipient_species_conversion_rate * num_incipient_species)

            # Event type 4
            event_rates.append(self.incipient_species_extinction_rate * num_incipient_species)

            # All events
            rate_of_any_event = sum(event_rates)

            # Waiting time
            waiting_time = self.rng.expovariate(rate_of_any_event)
            if max_time and (self.current_time + waiting_time) > max_time:
                t = max_time - self.current_time
                for lineage in itertools.chain(self.current_full_species_lineages, self.current_incipient_species_lineages):
                    lineage.node.edge.length += t
                self.current_time = max_time
                break
            self.current_time += waiting_time
            for lineage in itertools.chain(self.current_full_species_lineages, self.current_incipient_species_lineages):
                lineage.node.edge.length += waiting_time

            # Select event
            event_type_idx = probability.weighted_index_choice(weights=event_rates, rng=self.rng)
            assert (event_type_idx >= 0 and event_type_idx <= 4)
            # print("time {}: {}, selected = {}".format(self.current_time, event_rates, event_type_idx))

            if event_type_idx == 0:
                self._process_full_species_birth(psm_tree)
            elif event_type_idx == 1:
                self._process_full_species_extinction(psm_tree)
            elif event_type_idx == 2:
                self._process_incipient_species_birth(psm_tree)
            elif event_type_idx == 3:
                self._process_incipient_species_conversion(psm_tree)
            elif event_type_idx == 4:
                self._process_incipient_species_extinction(psm_tree)
            else:
                raise Exception("Unexpected event type index: {}".format(event_type_idx))

            if len(self.current_full_species_lineages) + len(self.current_incipient_species_lineages) == 0:
                raise TreeSimTotalExtinctionException()

        pruned_tree = self._assemble_pruned_tree(taxon_namespace=taxon_namespace)
        return self._postprocess_pruned_and_psm_trees(
                pruned_tree=pruned_tree,
                psm_tree=psm_tree)

    def _process_full_species_birth(self, tree):
        parent_lineage = self.rng.choice(self.current_full_species_lineages)
        parent_node = parent_lineage.node
        new_lineage = self._new_lineage(parent_lineage=parent_lineage, is_full_species=False)
        c1 = self._new_node(lineage=parent_lineage)
        c2 = self._new_node(lineage=new_lineage)
        parent_node.add_child(c1)
        parent_node.add_child(c2)

    def _process_full_species_extinction(self, tree):
        sp = self.rng.choice(self.current_full_species_lineages)
        sp.extinction_time = self.current_time
        self.current_full_species_lineages.remove(sp)
        self._make_lineage_extinct_on_phylogeny(tree, sp.node)

    def _process_incipient_species_birth(self, tree):
        parent_lineage = self.rng.choice(self.current_incipient_species_lineages)
        parent_node = parent_lineage.node
        new_lineage = self._new_lineage(parent_lineage=parent_lineage, is_full_species=False)
        c1 = self._new_node(lineage=parent_lineage)
        c2 = self._new_node(lineage=new_lineage)
        parent_node.add_child(c1)
        parent_node.add_child(c2)

    def _process_incipient_species_conversion(self, tree):
        lineage = self.rng.choice(self.current_incipient_species_lineages)
        self.current_incipient_species_lineages.remove(lineage)
        self.current_full_species_lineages.append(lineage)
        lineage.is_full_species = True
        lineage.speciation_completion_time = self.current_time

    def _process_incipient_species_extinction(self, tree):
        sp = self.rng.choice(self.current_incipient_species_lineages)
        sp.extinction_time = self.current_time
        self.current_incipient_species_lineages.remove(sp)
        self._make_lineage_extinct_on_phylogeny(tree, sp.node)

    def _make_lineage_extinct_on_phylogeny(self, tree, sp):
        if len(self.current_full_species_lineages) == 0 and len(self.current_incipient_species_lineages) == 0:
            raise TreeSimTotalExtinctionException()
        tree.prune_subtree(sp)

    def _new_lineage(self, parent_lineage, is_full_species):
        self.current_lineage_index += 1
        lineage_index = self.current_lineage_index
        speciation_initiation_time = self.current_time
        new_lineage = ProtractedSpeciationModel.ProtractedSpeciationModelLineage(
                index=lineage_index,
                parent_lineage=parent_lineage,
                speciation_initiation_time=speciation_initiation_time,
                is_full_species=is_full_species)
        self._all_lineages.append(new_lineage)
        if is_full_species:
            self.current_full_species_lineages.append(new_lineage)
        else:
            self.current_incipient_species_lineages.append(new_lineage)
        return new_lineage

    def _new_node(self,
            lineage,
            ):
        node = self.node_factory()
        node.edge.length = 0.0
        node.protracted_speciation_model_lineage = lineage
        node.is_full_speciation_event = False
        node.annotations.add_bound_attribute("is_full_speciation_event")
        self.current_node_index += 1
        node.label = "{}.n{}".format(lineage.label, self.current_node_index)
        node.annotations.add_new(name="lineage_index", value=lineage.index)
        node.annotations.add_new(name="lineage_label", value=lineage.label)
        lineage.node = node
        return node

    def _assemble_pruned_tree(self, taxon_namespace=None):
        lineage_set = set(self.current_incipient_species_lineages + self.current_full_species_lineages)
        sorted_lineages = sorted(lineage_set,
                key = lambda x: -x.speciation_initiation_time)
        # sys.stderr.write("\n--- full ---\n")
        # self._debug_dump_lineages(self._all_lineages)
        # sys.stderr.write("\n\n--- operational ---\n")
        # self._debug_dump_lineages(sorted_lineages)
        branching_points = {}
        while sorted_lineages:
            lineage = sorted_lineages.pop(0)
            lineage_set.remove(lineage)
            parent_lineage = lineage.parent_lineage
            if parent_lineage is None:
                break
            if lineage.is_full_species:
                full_species_tree_node = self._require_pruned_tree_node(
                        lineage_pruned_tree_node_map=branching_points,
                        lineage=lineage)
                # try:
                #     full_species_tree_node = branching_points[lineage]
                # except KeyError:
                #     full_species_tree_node = dendropy.Node()
                #     full_species_tree_node.label = "L{}".format(lineage.index)
                #     full_species_tree_node.protracted_speciation_model_lineage = lineage
                #     branching_points[lineage] = full_species_tree_node
                if lineage.is_full_species:
                    parent_lineage.is_full_species = True
                # try:
                #     full_species_tree_parent_node = branching_points[parent_lineage]
                # except KeyError:
                #     full_species_tree_parent_node = dendropy.Node()
                #     full_species_tree_parent_node.label = "L{}".format(parent_lineage.index)
                #     full_species_tree_parent_node.protracted_speciation_model_lineage = parent_lineage
                #     branching_points[parent_lineage] = full_species_tree_parent_node
                full_species_tree_parent_node = self._require_pruned_tree_node(
                        lineage_pruned_tree_node_map=branching_points,
                        lineage=parent_lineage)
                full_species_tree_parent_node.add_child(full_species_tree_node)
                if parent_lineage not in lineage_set:
                    lineage_set.add(parent_lineage)
                    sorted_lineages = sorted(lineage_set,
                            key = lambda x: -x.speciation_initiation_time)
        seed_node = None
        for nd in branching_points.values():
            if nd.parent_node is None:
                seed_node = nd
                break
        if seed_node is None:
            raise ProtractedSpeciationModel.ProcessFailedException()
        pruned_tree = dendropy.Tree(taxon_namespace=taxon_namespace, seed_node=seed_node)
        pruned_tree.is_rooted = True
        # pruned_tree.suppress_unifurcations()
        # pruned_tree.set_edge_lengths_from_node_ages()

        for nd in pruned_tree.postorder_node_iter():
            if nd.is_leaf():
                nd.age = 0
            else:
                nd.age = self.current_time - min(ch.protracted_speciation_model_lineage.speciation_initiation_time for ch in nd.child_node_iter())
        pruned_tree.set_edge_lengths_from_node_ages()
        pruned_tree.suppress_unifurcations()
        return pruned_tree

    def _require_pruned_tree_node(self,
            lineage_pruned_tree_node_map,
            lineage):
        try:
            return lineage_pruned_tree_node_map[lineage]
        except KeyError:
            node = self.node_factory()
            node.label = lineage.label
            node.protracted_speciation_model_lineage = lineage
            node.annotations.add_new(name="lineage_index", value=lineage.index)
            node.annotations.add_new(name="lineage_label", value=lineage.label)
            lineage_pruned_tree_node_map[lineage] = node
            return node

    def _postprocess_pruned_and_psm_trees(self, pruned_tree, psm_tree):
        psm_tree.calc_node_ages()
        for pruned_tree_nd in pruned_tree:
            if pruned_tree_nd.is_leaf():
                continue
            # sys.stderr.write("{}: {}\n".format(pruned_tree_nd.age, list(nd.age for nd in pruned_tree_nd.protracted_speciation_model_lineage.psm_tree_node_history)))
            psm_tree_node = pruned_tree_nd.protracted_speciation_model_lineage.psm_tree_node_history[0]
            for nd in pruned_tree_nd.protracted_speciation_model_lineage.psm_tree_node_history:
                if nd.age is not None and nd.age > psm_tree_node.age:
                    psm_tree_node = nd
                # nd.is_full_speciation_event = True
            psm_tree_node.is_full_speciation_event = True
            pruned_tree_nd.protracted_speciation_model_tree_node = psm_tree_node

        return psm_tree, pruned_tree

    def _debug_dump_lineages(self, lineages):
        sorted_lineages = sorted(lineages,
                key = lambda x: -x.speciation_initiation_time)
        for k in sorted_lineages:
            if k.parent_lineage is None:
                pi = "NA"
                pt = "NA"
            else:
                pi = k.parent_lineage.index
                pt = k.parent_lineage.is_full_species
            sys.stderr.write("{:10.5f} : {:4} ({}) => {} ({})\n".format(
                    k.speciation_initiation_time,
                    k.index,
                    k.is_full_species,
                    pi,
                    pt))
        sys.stderr.write("\n")
