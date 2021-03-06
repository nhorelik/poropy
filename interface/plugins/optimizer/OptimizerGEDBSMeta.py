'''
Created on Feb 17, 2012

@author: robertsj
'''

import sys

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from poropy.coretools.optimizer_gedbs import OptimizerGEDBS

import plugin

class OptimizerGEDBSMeta(plugin.Plugin):
    """  Defines metadata for OptimizerGEDBS
    """
    
    def __init__(self,model,parent=None):
        plugin.Plugin.__init__(self,model,parent=parent)

    def userInputs(self):
        
        # define the user inputs

        inputs =    (
                        ("maximum_iterations",  {'type': "freetext", 'label': "maximum_iterations",
                                                 'default': 123}),
                        ("seed",                {'type': "freetext", 'label': "seed",
                                                 'default': 123}),
                        ("np_seed",             {'type': "freetext", 'label': "np_seed",
                                                 'default': 123}),
                        ("binary_sweep",        {'type': "checkbox", 'label': "np_seed",
                                                 }),                     
                    )
        return inputs

    def runActions(self):

        # define the buttons

        actions =   (
                       ("execute",     {'label': "Execute",
                                        'description': "Optimize the problem."}),
                    )
        return actions

    def title(self):
        return "Greedy Exhaustive Dual Binary Swap"

    def description(self):
        return """Optimize a loading pattern for a given objective using GEDBS."""
    
    def execute(self):
        """  Execute the parent class. 
        """
        
        argv = sys.argv
        reactor = self.model.reactor
        objective = self.model.objective

        opt = OptimizerGEDBS(argv,reactor,objective)

        opt.maximum_generations    = int(self.maximum_iterations)
        opt.seed                   = int(self.seed)
        opt.np_seed                = int(self.np_seed)
        opt.binary_sweep           = self.binary_sweep

        self.connect(opt,SIGNAL("patternUpdated"),self.model.opt_pattern_updated)

        opt.execute()
        
        self.close_plugin_diag()
