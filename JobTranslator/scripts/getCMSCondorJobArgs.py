#!/bin/env python

import sys
import imp
import copy
import os
import socket
import filecmp
import shutil
import pickle
import math
import pprint
import subprocess
from datetime import date
from optparse import OptionParser


class BatchManager:
   def __init__(self):
      # define options and arguments ====================================
      self.parser = OptionParser()

      self.parser.add_option("--constraints", type="string", default=None, help="Constraint string to condor_q")
      self.parser.add_option("--outfile", type="string", help="Name of the output file")
      self.parser.add_option("--veto_running", action="store_true", default=False, help="Do not consider running jobs")
      self.parser.add_option("--only_running", action="store_true", default=False, help="Only consider running jobs")

      (self.opt,self.args) = self.parser.parse_args()
      optchecks=[
         "outfile",
      ]
      for theOpt in optchecks:
         if not hasattr(self.opt, theOpt) or getattr(self.opt, theOpt) is None:
            sys.exit("Need to set --{} option".format(theOpt))

      if self.opt.only_running and self.opt.veto_running:
         sys.exit("Cannot specify --veto_running and --only_running at the same time")

      self.outfile = os.path.abspath(self.opt.outfile)

      self.condorqargs = []
      if not self.opt.veto_running:
         if self.opt.constraints is not None and self.opt.constraints:
            self.condorqargs.append("-constraint \"{}\"".format(self.opt.constraints))
      else:
         constraintargs = "(JobStatus==1 || JobStatus==5)"
         if self.opt.constraints is not None and self.opt.constraints:
            constraintargs = constraintargs + " && (" + self.opt.constraints + ")"
         self.condorqargs.append("-constraint \"" + constraintargs + "\"")

      if self.opt.only_running:
         self.condorqargs.append("-run")

      self.run()


   def run(self):
      runCmd = "condor_q -af 'Args' {} &> {}".format(" ".join(self.condorqargs), self.outfile)
      os.system(runCmd)


if __name__ == '__main__':
   batchManager = BatchManager()
