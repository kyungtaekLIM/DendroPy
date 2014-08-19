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
Tests for NeXML tree writing.
"""

import collections
import unittest
import dendropy
import re
from dendropy.test.support import pathmap
from dendropy.test.support import compare_and_validate
from dendropy.test.support import dendropytest
from dendropy.test.support import curated_test_tree
from dendropy.test.support import standard_file_test_trees

class NexmlTreeWriterTests(
        curated_test_tree.CuratedTestTree,
        compare_and_validate.ValidateWriteable,
        unittest.TestCase):

    def test_simple(self):
        tree1, all_nodes, leaf_nodes, internal_nodes = self.get_tree(
                    suppress_internal_node_taxa=False,
                    suppress_leaf_node_taxa=False
                )
        s = tree1.as_string("nexml")
        tree2 = dendropy.Tree.get_from_string(
                s, "nexml",
                )
        self.verify_curated_tree(tree2)

class NexmlTreeWriterDefaultTest(
        standard_file_test_trees.NexmlTestTreesChecker,
        compare_and_validate.ValidateWriteable,
        dendropytest.ExtendedTestCase):

    @classmethod
    def setUpClass(cls):
        standard_file_test_trees.NexmlTestTreesChecker.create_class_fixtures(cls)

    def test_roundtrip_full(self):
        tree_file_title = 'dendropy-test-trees-n33-unrooted-annotated-x10a'
        tree_filepath = standard_file_test_trees._TREE_FILEPATHS["nexml"][tree_file_title]
        tree1 = dendropy.Tree.get_from_path(
                tree_filepath,
                "nexml",
        )
        s = tree1.as_string("nexml")
        tree2 = dendropy.Tree.get_from_string(
                s,
                "nexml",
        )
        self.compare_to_reference_tree(
            tree=tree2,
            tree_file_title=tree_file_title,
            reference_tree_idx=0)

if __name__ == "__main__":
    unittest.main()
