#!/bin/bash


function getcmsenvscript {
    if [ -r "$OSGVO_CMSSW_Path"/cmsset_default.sh ]; then
        echo "$OSGVO_CMSSW_Path"/cmsset_default.sh
    elif [ -r "$OSG_APP"/cmssoft/cms/cmsset_default.sh ]; then
        echo "$OSG_APP/cmssoft/cms/cmsset_default.sh"
    elif [ -r /cvmfs/cms.cern.ch/cmsset_default.sh ]; then
        echo "/cvmfs/cms.cern.ch/cmsset_default.sh"
    fi
}
function setupenv {
    if [ -r "$OSGVO_CMSSW_Path"/cmsset_default.sh ]; then
        echo "sourcing environment: source $OSGVO_CMSSW_Path/cmsset_default.sh"
        source "$OSGVO_CMSSW_Path"/cmsset_default.sh
    elif [ -r "$OSG_APP"/cmssoft/cms/cmsset_default.sh ]; then
        echo "sourcing environment: source $OSG_APP/cmssoft/cms/cmsset_default.sh"
        source "$OSG_APP"/cmssoft/cms/cmsset_default.sh
    elif [ -r /cvmfs/cms.cern.ch/cmsset_default.sh ]; then
        echo "sourcing environment: source /cvmfs/cms.cern.ch/cmsset_default.sh"
        source /cvmfs/cms.cern.ch/cmsset_default.sh
    else
        echo "ERROR! Couldn't find $OSGVO_CMSSW_Path/cmsset_default.sh or /cvmfs/cms.cern.ch/cmsset_default.sh or $OSG_APP/cmssoft/cms/cmsset_default.sh"
        exit 1
    fi
}


setupenv
declare -i HAS_CMSSW=$?
if [[ ${HAS_CMSSW} -ne 0 ]]; then
  echo "CMSSW environment script does not exist."
  exit 1
fi

cmsenvdir=$( getcmsenvscript )
echo "CMSSW environment script: ${cmsenvdir}"
cvmfsdirsplit=( ${cmsenvdir//'/'/' '} )
cvmfshead="/${cvmfsdirsplit[0]}"

CURRENTDIR=$(pwd)
RUNDIR=rundir
mkdir -p ${RUNDIR}
mv jobscript.sh ${RUNDIR}/
for f in $(ls ./ | grep -e .tar); do
  mv $f ${RUNDIR}/
done
# Also move any Python fragments
for f in $(ls ./ | grep -e .py); do
  mv $f ${RUNDIR}/
done

echo "Current directory: ${CURRENTDIR}"
ls -la

echo "Run directory: ${CURRENTDIR}/${RUNDIR}"
ls -la ${RUNDIR}


# We need to require SL6 for Run 2 legacy reco. to work.
# If the machine uses SL7, we have to use singularity.
# This is often the case in submissions from lxplus.
MACHINESPECS="$(uname -a)"
echo "Machine specifics: ${MACHINESPECS}"
declare -i FOUND_EL6=0
if [[ "${MACHINESPECS}" == *"el6"* ]]; then
  FOUND_EL6=1
fi

declare -i USE_NATIVE_CALLS=0
if [[ ${FOUND_EL6} -eq 1 ]] && [[ ${HAS_CMSSW} -eq 0 ]]; then
  USE_NATIVE_CALLS=1
  echo "Machine has both CMS environment scripts and runs on SL6 OS. Native calls will be used."
else
  echo "Machine does not have the proper setup to run native calls. Singularity with an SL6 docker container will be used."
fi

# This is for singularity cache to be stored
SINGULARITYARGS="-B ${CURRENTDIR}/${RUNDIR} -B ${cvmfshead} -B /etc/grid-security"
SINGULARITYCONTAINER="docker://cmssw/slc6:latest"

if [[ $USE_NATIVE_CALLS -eq 0 ]]; then
  command -v singularity &> /dev/null
  if [[ $? -ne 0 ]]; then
    echo "ERROR: Singularity was requested, but it is not present."
    exit 1
  fi

  # Singularity cache directory might not be set up.
  if [[ -z ${SINGULARITY_CACHEDIR+x} ]]; then
    if [[ ! -z ${TMPDIR+x} ]]; then
      export SINGULARITY_CACHEDIR="${TMPDIR}/singularity"
    else
      export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"
    fi
  fi

  # Some singularity implementations have older versions, which do not have the no-home option.
  STRRUNNOHOME="$(singularity help exec | grep -e no-home)"
  if [[ ! -z "${STRRUNNOHOME}" ]]; then
    SINGULARITYARGS="${SINGULARITYARGS} --no-home"
  fi

  # Try to execute a very simple command to see if singularity runs correctly
  testcmd="singularity exec ${SINGULARITYARGS} ${SINGULARITYCONTAINER} ls -la"
  echo "Executing singularity test command: ${testcmd}"
  ${testcmd}
  if [[ $? -ne 0 ]]; then
    echo "Test command failed. The machine does not seem to have the correct setup."
    exit 1
  fi
fi

chmod 755 ${RUNDIR}/*

echo "time: $(date +%s)"
if [[ $USE_NATIVE_CALLS -eq 1 ]]; then
  ${RUNDIR}/jobscript.sh "$@" || touch ${RUNDIR}/ERROR
else
  singularity exec ${SINGULARITYARGS} ${SINGULARITYCONTAINER} ${RUNDIR}/jobscript.sh "$@" || touch ${RUNDIR}/ERROR
fi
if [[ -e ${RUNDIR}/ERROR ]]; then
  exit 1
fi

echo "All steps are done."
echo "time: $(date +%s)"
