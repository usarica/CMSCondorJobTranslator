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

      self.parser.add_option("--batchqueue", type="string", help="Batch queue")
      self.parser.add_option("--batchscript", type="string", help="Name of the HTCondor script that runs the job script")
      self.parser.add_option("--sites", type="string", help="Name of the HTCondor run sites")

      self.parser.add_option("--jobscript", type="string", help="Name of the actual job script")
      self.parser.add_option("--jobargs", type="string", help="Arguments to the job script")

      self.parser.add_option("--upload", type="string", action="append", default=[], help="Uploads to the job (can specify multiple inputs)")
      self.parser.add_option("--outdir", type="string", help="Name of the output directory")

      self.parser.add_option("--required_memory", type="string", default="2048M", help="Required RAM for the job")
      self.parser.add_option("--required_disk", type="string", default="5G", help="Required disk for the job")
      self.parser.add_option("--required_ncpus", type="int", default=2, help="Required number of CPUs for the job")
      self.parser.add_option("--job_flavor", type="string", default="tomorrow", help="Time limit for job (tomorrow = 1 day, workday = 8 hours, see https://batchdocs.web.cern.ch/local/submit.html#job-flavours for more)")

      self.parser.add_option("--forceSL6", action="store_true", default=False, help="Force running on SL6 architecture")

      self.parser.add_option("--dry", dest="dryRun", action="store_true", default=False, help="Do not submit jobs, just set up the files")

      (self.opt,self.args) = self.parser.parse_args()
      optchecks=[
         "batchqueue",
         "batchscript",
         "outdir",
         "sites",
         "jobscript",
         "jobargs",
      ]
      for theOpt in optchecks:
         if not hasattr(self.opt, theOpt) or getattr(self.opt, theOpt) is None:
            sys.exit("Need to set --{} option".format(theOpt))

      if not os.path.isdir(self.opt.outdir):
         os.makedirs(self.opt.outdir+"/Logs")
      self.opt.outdir = os.path.abspath(self.opt.outdir)

      if not os.path.isfile(self.opt.batchscript):
         print("Batch script does not exist in current directory, will search for CMSSW_BASE/bin")
         if os.path.isfile(os.getenv("CMSSW_BASE")+"/bin/"+os.getenv("SCRAM_ARCH")+"/"+self.opt.batchscript):
            self.opt.batchscript = os.getenv("CMSSW_BASE")+"/bin/"+os.getenv("SCRAM_ARCH")+"/"+self.opt.batchscript
            print("\t- Found the batch script")
         else:
            sys.exit("Batch script {} does not exist. Exiting...".format(self.opt.batchscript))

      self.opt.batchscript = os.path.abspath(self.opt.batchscript)

      if not os.path.isfile(self.opt.jobscript):
         sys.exit("Job script {} does not exist. Exiting...".format(self.opt.jobscript))

      self.jobscript = os.path.abspath(self.opt.jobscript)
      if os.path.exists(self.opt.outdir+"/jobscript.sh"):
         os.unlink(self.opt.outdir+"/jobscript.sh")
      os.symlink(self.jobscript, self.opt.outdir+"/jobscript.sh")

      uploadslist = []
      for fname in self.opt.upload:
         if not os.path.isfile(fname):
            sys.exit("Uploaded file {} does not exist. Exiting...".format(fname))
         else:
            uploadslist.append(os.path.abspath(fname))
      self.uploads = ",".join(uploadslist)
      if not self.uploads:
         sys.exit("You must specify extra uploads.")

      self.submitJobs()


   def getVOMSProxy(self):
      gridproxy = None
      if os.getenv("X509_USER_PROXY") is None or not os.getenv("X509_USER_PROXY"):
         currentCMSSWBASESRC = os.getenv("CMSSW_BASE")+"/src"
         gridproxycheckfiles = [
            "{home}/x509up_u{uid}".format(home=os.path.expanduser("~"), uid=os.getuid())
            ]
         for gridproxycheckfile in gridproxycheckfiles:
            if os.path.exists(gridproxycheckfile):
               gridproxy = gridproxycheckfile
               break
      else:
         gridproxy = os.getenv("X509_USER_PROXY")
      if gridproxy is None or not os.path.exists(gridproxy):
         sys.exit("Cannot find a valid grid proxy")
      return gridproxy


   def produceCondorScript(self):
      currentdir = os.getcwd()
      currentCMSSWBASESRC = os.getenv("CMSSW_BASE")+"/src/" # Need the trailing '/'
      currendir_noCMSSWsrc = currentdir.replace(currentCMSSWBASESRC,'')

      scramver = os.getenv("SCRAM_ARCH")
      singularityver = "cms:rhel6-m202006"
      if "slc7" in scramver and not self.opt.forceSL6:
         singularityver = "cms:rhel7-m202006"

      gridproxy = self.getVOMSProxy()
      hostname = socket.gethostname()
      strrequirements = 'Requirements            = (HAS_SINGULARITY=?=True && HAS_CVMFS_cms_cern_ch =?= true)'
      strsingularity = ""
      strproject = ""
      if "t2.ucsd.edu" in hostname:
         strrequirements = 'Requirements            = (HAS_SINGULARITY=?=True && HAS_CVMFS_cms_cern_ch =?= true) || (regexp("(uaf-[0-9]{{1,2}}|uafino)\.", TARGET.Machine) && !(TARGET.SlotID>(TotalSlots<14 ? 3:7) && regexp("uaf-[0-9]", TARGET.machine)))'
         strsingularity = '+SingularityImage = "/cvmfs/singularity.opensciencegrid.org/cmssw/{SINGULARITYVERSION}"'.format(SINGULARITYVERSION = singularityver)
         strproject = '+project_Name = "cmssurfandturf"'
      else:
         strrequirements = 'Requirements            = (HAS_SINGULARITY=?=True && HAS_CVMFS_cms_cern_ch =?= true) || (!isUndefined(NODE_MOUNTS_CVMFS) && NODE_MOUNTS_CVMFS)'

      scriptargs = {
         "batchScript" : self.opt.batchscript,
         "GRIDPROXY" : gridproxy,
         "PROJECTNAME" : strproject,
         "SITES" : self.opt.sites,
         "outDir" : self.opt.outdir,
         "QUEUE" : self.opt.batchqueue,
         "SINGULARITY" : strsingularity,
         "JOBSCRIPT" : "jobscript.sh", # Linked
         "JOBARGS" : self.opt.jobargs,
         "UPLOADS" : self.uploads,
         "NCPUS" : self.opt.required_ncpus,
         "REQMEM" : self.opt.required_memory,
         "REQDISK" : self.opt.required_disk,
         "JOBFLAVOR" : self.opt.job_flavor,
         "REQUIREMENTS" : strrequirements
      }

      scriptcontents = """
universe                = {QUEUE}
+DESIRED_Sites          = "{SITES}"
executable              = {batchScript}
arguments               = {JOBARGS}
Initialdir              = {outDir}
output                  = Logs/log_job.$(ClusterId).$(ProcId).txt
error                   = Logs/err_job.$(ClusterId).$(ProcId).err
log                     = $(ClusterId).$(ProcId).log
request_memory          = {REQMEM}
request_cpus            = {NCPUS}
request_disk            = {REQDISK}
+JobFlavour             = "{JOBFLAVOR}"
x509userproxy           = {GRIDPROXY}
#https://www-auth.cs.wisc.edu/lists/htcondor-users/2010-September/msg00009.shtml
periodic_remove         = JobStatus == 5
transfer_executable     = True
transfer_input_files    = {JOBSCRIPT},{UPLOADS}
transfer_output_files   = ""
+Owner                  = undefined
notification            = Never
should_transfer_files   = YES
when_to_transfer_output = ON_EXIT_OR_EVICT
+WantRemoteIO           = false
{REQUIREMENTS}
{SINGULARITY}
{PROJECTNAME}


queue

"""
      scriptcontents = scriptcontents.format(**scriptargs)

      self.condorScriptName = "condor.sub"
      condorScriptFile = open(self.opt.outdir+"/"+self.condorScriptName,'w')
      condorScriptFile.write(scriptcontents)
      condorScriptFile.close()


   def submitJobs(self):
      self.produceCondorScript()

      jobcmd = "cd {}; condor_submit {}; cd -".format(self.opt.outdir, self.condorScriptName)
      if self.opt.dryRun:
         print("Job command: '{}'".format(jobcmd))
      else:
         ret = os.system(jobcmd)



if __name__ == '__main__':
   batchManager = BatchManager()
