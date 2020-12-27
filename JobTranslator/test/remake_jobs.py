import os
import sys
import socket
import csv
import glob
import re
import subprocess
from pprint import pprint
import argparse



class BatchManager:
   def __init__(self):
      parser = argparse.ArgumentParser()
      parser.add_argument("argfiles", help="condor_q Args output lists", nargs="+")
      parser.add_argument("--outdir", help="Output directory", type=str, required=True)
      parser.add_argument("--jobscript", help="Job script to receive the arguments", type=str, required=True)
      parser.add_argument("--upload", help="List of uploads", action="append", required=True)
      parser.add_argument("--batchscript", help="Batch script to run the actual jobs", type=str, default="condor_executable.sh", required=False)
      parser.add_argument("--required_memory", type=str, default="2048M", required=False, help="Required RAM for the job")
      parser.add_argument("--required_disk", type=str, default="5G", required=False, help="Required disk for the job")
      parser.add_argument("--required_ncpus", type=int, default=1, required=False, help="Required number of CPUs for the job")
      parser.add_argument("--job_flavor", type=str, default="tomorrow", required=False, help="Time limit for job (tomorrow = 1 day, workday = 8 hours, see https://batchdocs.web.cern.ch/local/submit.html#job-flavours for more)")


      self.args = parser.parse_args()

      self.run()


   def run(self):
      batchqueue = "vanilla"

      allowed_sites = None
      if "t2.ucsd.edu" in socket.gethostname():
         allowed_sites = "T2_US_UCSD,T2_US_Caltech,T2_US_MIT,T2_US_Purdue,T2_US_Wisconsin,T2_US_Nebraska,T3_US_UCR,T3_US_Baylor,T3_US_Colorado,T3_US_NotreDame,T3_US_Cornell,T3_US_Rice,T3_US_Rutgers,T3_US_UCD,T3_US_TAMU,T3_US_TTU,T3_US_FIU,T3_US_FIT,T3_US_UMD,T3_US_OSU,T3_US_OSG,T3_US_UMiss,T3_US_PuertoRico"
      else:
         allowed_sites = "T2_CH_CERN,T2_BE_IIHE,T2_CN_Beijing,T2_RU_IHEP,T2_BE_UCL,T2_AT_Vienna,T2_BR_SPRACE,T2_BR_UERJ,T2_CH_CSCS,T2_DE_DESY,T2_DE_RWTH,T2_EE_Estonia,T2_ES_CIEMAT,T2_ES_IFCA,T2_FI_HIP,T2_FR_CCIN2P3,T2_FR_GRIF_IRFU,T2_FR_GRIF_LLR,T2_FR_IPHC,T2_GR_Ioannina,T2_HU_Budapest,T2_IN_TIFR,T2_IT_Bari,T2_IT_Legnaro,T2_IT_Pisa,T2_IT_Rome,T2_KR_KNU,T2_PK_NCP,T2_PL_Swierk,T2_PL_Warsaw,T2_PT_NCG_Lisbon,T2_RU_INR,T2_RU_ITEP,T2_RU_JINR,T2_RU_PNPI,T2_RU_RRC_KI,T2_RU_SINP,T2_TH_CUNSTDA,T2_TR_METU,T2_UA_KIPT,T2_UK_London_Brunel,T2_UK_London_IC,T2_UK_SGrid_Bristol,T2_UK_SGrid_RALPP,T3_CO_Uniandes,T3_FR_IPNL,T3_GR_IASA,T3_HU_Debrecen,T3_IT_Bologna,T3_IT_Napoli,T3_IT_Perugia,T3_IT_Trieste,T3_KR_KNU,T3_MX_Cinvestav,T3_RU_FIAN,T3_TW_NCU,T3_TW_NTU_HEP,T3_UK_London_QMUL,T3_UK_SGrid_Oxford,T3_CN_PKU"

      uploadsarg = ""
      for uploadfile in self.args.upload:
         uploadsarg = uploadsarg + "--upload {} ".format(uploadfile)

      idx_job=0
      for fname in self.args.argfiles:
         with open(fname) as argfile:
            for jobargs in argfile:
               runargs = {
                  "BATCHQUEUE" : batchqueue,
                  "BATCHSCRIPT" : self.args.batchscript,
                  "UPLOADSARG" : uploadsarg,
                  "OUTDIR" : "{}/subjob_{}".format(self.args.outdir, idx_job),
                  "REQMEM" : self.args.required_memory,
                  "REQDISK" : self.args.required_disk,
                  "REQNCPUS" : self.args.required_ncpus,
                  "JOBFLAVOR" : self.args.job_flavor,
                  "JOBSCRIPT" : self.args.jobscript,
                  "JOBARGS" : jobargs.strip(),
                  "SITES" : allowed_sites
                  }
               runCmd = str(
                  "reconfigureCMSCondorJobs.py --dry --batchqueue={BATCHQUEUE} --batchscript={BATCHSCRIPT} --forceSL6" \
                  " --jobscript {JOBSCRIPT} --jobargs '{JOBARGS}' {UPLOADSARG}" \
                  " --outdir={OUTDIR} --required_memory={REQMEM} --required_ncpus={REQNCPUS} --required_disk={REQDISK} --job_flavor={JOBFLAVOR} --sites={SITES}"
                  ).format(**runargs)
               os.system(runCmd)

               idx_job = idx_job + 1


if __name__ == "__main__":
   batchManager = BatchManager()

