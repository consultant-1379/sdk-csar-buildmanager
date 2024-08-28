#!/bin/bash

BASENAME=basename
CAT=cat
CP=cp
CURL=curl
DATE=date
DOCKER=docker
ECHO=echo
GETOPT=getopt
GREP=grep
HELM=helm
LS=ls
MKDIR=mkdir
MV=mv
NUMFMT=numfmt
RM=rm
RSYNC=rsync
SED=sed
TAR=tar
TOUCH=touch
WGET=wget

PROJECT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

ENM_PROP_FILE="${PROJECT_DIR}/enm_artifact.properties"
if [ -f ${ENM_PROP_FILE} ] ; then
    $ECHO "Source $ENM_PROP_FILE."
    source $ENM_PROP_FILE
fi

[[ -z "${ERIC_ENM_FMSDK_IMAGE_TAG}" ]] && FMSDK_TAG='latest' || FMSDK_TAG="${ERIC_ENM_FMSDK_IMAGE_TAG}"
[[ -z "${ERIC_ENM_FMSDK_TEMPLATES}" ]] && FMSDK_TEMPLATES='latest' || FMSDK_TEMPLATES="${ERIC_ENM_FMSDK_TEMPLATES}"

[[ -z "${ERIC_ENM_PMSDK_IMAGE_TAG}" ]] && PMSDK_TAG='latest' || PMSDK_TAG="${ERIC_ENM_PMSDK_IMAGE_TAG}"
[[ -z "${ERIC_ENM_PMSDK_TEMPLATES}" ]] && PMSDK_TEMPLATES='latest' || PMSDK_TEMPLATES="${ERIC_ENM_PMSDK_TEMPLATES}"

IMAGE_REPO_PATH="proj-cenm-sdk/proj-cenm-sdk-released"

FMSDK_IMAGE_REPO="armdocker.rnd.ericsson.se/${IMAGE_REPO_PATH}"
PMSDK_IMAGE_REPO="armdocker.rnd.ericsson.se/${IMAGE_REPO_PATH}"


FMSDK_IMAGE_NAME="eric-enm-fmsdk"
PMSDK_IMAGE_NAME="eric-enm-pmsdk"

FM_SDK_TEMPLATES="fm-sdk-templates"
PM_SDK_TEMPLATES="pm-sdk-templates"

INTEGRATION_CHART="eric-enm-sdk-integration-template"

TEMPLATES_RELEASES=https://arm2s11-eiffel004.eiffel.gic.ericsson.se:8443/nexus/content/repositories/cloud-native-enm-sdk/templates/releases
FMSDK_TEMPLATES_RELEASES="${TEMPLATES_RELEASES}/${FM_SDK_TEMPLATES}/"
PMSDK_TEMPLATES_RELEASES="${TEMPLATES_RELEASES}/${PM_SDK_TEMPLATES}/"

SDK_SRC="${PROJECT_DIR}/src"
SDK_BUILD_IMAGES="${SDK_SRC}/sdk_builld_images.txt"

CSAR_SOURCE_DIR="${PROJECT_DIR}/fmsdk_bm_csar_source"
BUILD_DIR="${PROJECT_DIR}/build"

BUILD_DIR_TEMPLATES="${BUILD_DIR}/templates"
BUILD_DIR_TEMPLATES_CHART="${BUILD_DIR_TEMPLATES}/charts"
BUILD_DIR_TEMPLATES_CSAR="${BUILD_DIR_TEMPLATES}/csar"
BUILD_DIR_DOCKER="${BUILD_DIR}/docker"
BUILD_DIR_SCRIPTS="${BUILD_DIR}/scripts"

SDK_DOCKER_IMAGES_FILE="${BUILD_DIR_DOCKER}/images.txt"
SDK_DOCKER_TAR="${BUILD_DIR_DOCKER}/docker.tar"

CSAR_DESCRIPTOR="vnfd/fmsdk_descriptor.yaml"
CSAR_MANIFEST="manifest/fmsdk_descriptor.mf"

info() {
    local _msg_="${1}"
    ${ECHO} -e "INFO - ${_msg_}"
}

error() {
    local _msg_="${1}"
    ${ECHO} -e "ERROR - ${_msg_}" >&2
}

clean(){
    info "Cleaning previous builds ..."
    if [[ ! -f ${BUILD_DIR} ]] ; then
        ${RM} -rf ${RM_OPTS} ${BUILD_DIR}
    fi
}

setup() {
    info "Setting up build ..."
    ${MKDIR} -p ${MKDIR_OPTS} ${BUILD_DIR} || exit 1
    ${MKDIR} -p ${MKDIR_OPTS} ${BUILD_DIR_TEMPLATES_CSAR} || exit 1
    ${MKDIR} -p ${MKDIR_OPTS} ${BUILD_DIR_TEMPLATES_CHART} || exit 1
    ${MKDIR} -p ${MKDIR_OPTS} ${BUILD_DIR_DOCKER} || exit 1
    ${MKDIR} -p ${MKDIR_OPTS} ${BUILD_DIR_SCRIPTS} || exit 1
}

get_oneflow_templates(){
    local _templates_=${1}
    local _releases_=${2}
    
    if [[ -f ${_templates_} ]] ; then
        info "Using local templates archive ${_templates_}"
        ${CP} ${_templates_} ${BUILD_DIR_TEMPLATES_CHART}
        elif [[ "${_templates_}" =~ ^http[s]?:.* ]]; then
        info "Using remote templates archive ${_templates_}"
        ${WGET} ${WGET_OPTS} ${_templates_} -O ${BUILD_DIR_TEMPLATES_CHART}/$(${BASENAME} ${_templates_})
    else
        if [[ "${_templates_}" == "latest" ]] ; then
            info "Looking up latest version of templates on ${_releases_}"
            _regex_="<release>(.*)</release>"
            _released_=$( ${WGET} ${WGET_OPTS} -O - "${_releases_}/maven-metadata.xml" | ${GREP} -E ${_regex_} )
            if [[ ${_released_} =~ ${_regex_} ]] ; then
                _templates_="${BASH_REMATCH[1]}"
            else
                error "Could not look up latest templates version in ${_releases_}"
                exit 7
            fi
        fi
            info "Getting versioned templates file: $(basename ${_releases_})/${_templates_}"
            _ofile_="$(basename ${_releases_})-${_templates_}.tar.gz"
            _url_="${_releases_}/${_templates_}/${_ofile_}"
            ${WGET} ${WGET_OPTS} ${_url_} -O ${BUILD_DIR_TEMPLATES_CHART}/${_ofile_}
    fi
}

pull_image(){
    local _image_=${1}
    local _log_=${2}
    ${DOCKER} ${DOCKER_OPTS} pull ${_image_} > ${_log_} 2>&1
    ${ECHO} "exit:$?" >> ${_log_}
}

pull_save_images(){
    local _dev_images_=($*)
    ${RM} -f /tmp/*.pull > /dev/null 2>&1
    
    for _image_ in "${_dev_images_[@]}" ; do
        info "Pulling image ${_image_} ..."
        _lfile_="/tmp/$( ${BASENAME} ${_image_} ).pull"
        pull_image ${_image_} ${_lfile_} &
    done

    # wait for all the pull_image jobs to finish
    wait
    
    _pull_failed_=false
    ${RM} -f ${SDK_DOCKER_IMAGES_FILE}
    ${TOUCH} ${SDK_DOCKER_IMAGES_FILE}
    for _image_ in "${_dev_images_[@]}" ; do
        _lfile_="/tmp/$( ${BASENAME} ${_image_} ).pull"
        if ! ${GREP} -q "exit:0" ${_lfile_} ; then
            ${CAT} ${_lfile_} | ${GREP} -vE "exit:"
            _pull_failed_=true
        fi
        ${ECHO} "${_image_}" >> ${SDK_DOCKER_IMAGES_FILE}
    done
    
    if ${_pull_failed_} ; then
        exit 4
    fi

    info "Creating ${SDK_DOCKER_TAR} for ${#_dev_images_[@]} images ..."
    ${DOCKER} ${DOCKER_OPTS} save -o ${SDK_DOCKER_TAR} "${_dev_images_[@]}" || exit 1
}

check_images(){
    local _dev_images_=("$@")
    export DOCKER_CLI_EXPERIMENTAL=enabled
    _check_failed_=false
    for _image_ in "${_dev_images_[@]}" ; do
        ${DOCKER} manifest inspect ${_image_} > /dev/null 2>&1
        if [[ $? -eq 0 ]] ; then
            info "Image ${_image_} found"
            ${ECHO} ${_image_} >> ${SDK_DOCKER_IMAGES_FILE}
        else
            error "No such manifest: ${_image_}"
            _check_failed_=true
        fi
    done
    if ${_check_failed_} ; then
        exit 4
    fi
    info "Creating empty ${SDK_DOCKER_TAR} "
    ${TAR} -cf ${SDK_DOCKER_TAR} --files-from /dev/null
}

# generic docker images method in case if they want to override repo
get_docker_images() {
    local _light_=$1
    shift
    local _images_=("$@")

    IFS=$'\n' read -d '' -r -a _tool_images_ < ${SDK_BUILD_IMAGES}
    _all_images_=( "${_images_[@]}" "${_tool_images_[@]}")

    if ${_light_} ; then
        check_images "${_all_images_[@]}"
    else
        pull_save_images "${_all_images_[@]}"
    fi
}

create_integration_template(){
  ${CP} -R ${CP_OPTS} ${CSAR_SOURCE_DIR}/charts/${INTEGRATION_CHART} ${BUILD_DIR_TEMPLATES_CHART} || exit 1
  info "Packaging integration template chart ${INTEGRATION_CHART}-0.0.0.tgz"
  ${TAR} cfz ${BUILD_DIR_TEMPLATES_CHART}/${INTEGRATION_CHART}-0.0.0.tgz \
    -C ${BUILD_DIR_TEMPLATES_CHART} ${INTEGRATION_CHART}  || exit 1
  ${RM} -rf ${RM_OPTS} ${BUILD_DIR_TEMPLATES_CHART}/${INTEGRATION_CHART}
}

get_csar_templates() {
    local _version_=${1}
    info "Copying CSAR templates"
    ${CP} -R ${CP_OPTS} ${CSAR_SOURCE_DIR}/* ${BUILD_DIR_TEMPLATES_CSAR} || exit 1
    ${RM} -rf ${BUILD_DIR_TEMPLATES_CSAR}/charts/eric-enm-sdk-integration-template > /dev/null 2>&1
}

get_scripts() {
    ${CP} ${CP_OPTS} ${SDK_SRC}/*.py ${BUILD_DIR_SCRIPTS}
}

create_sdk_archive() {
    local _version_=${1}
    local _build_dir_=${2}
    local _archive_dest_=${3}
    
    pushd ${BUILD_DIR} > /dev/null 2>&1
    _archive_name_="cloud-native-enm-sdk-${_version_}.tar.gz"
    ${RM} -f cloud-native-enm-sdk-*.tar.gz
    ${TAR} --create --gzip --file=${_archive_name_} ${TAR_OPTS} *
    popd ${BUILD_DIR} > /dev/null 2>&1
    
    local _ofile_=${BUILD_DIR}/${_archive_name_}
    if [[ "${BUILD_DIR}" != "${_archive_dest_}" ]] ; then
        ${MV} -f ${_ofile_} ${_archive_dest_}
        local _ofile_=${_archive_dest_}/${_archive_name_}
    fi
    info "Generated ${_ofile_}"
    ${TAR} --list --verbose --file=${_ofile_} | ${GREP} -e "[^/]$" | ${NUMFMT} --field=3 --to=iec-i --suffix=B
}

usage() {
    info "Usage: $0 OPTIONS"
    info "Options:"
    info "\t-c\t\tClean build environment"
    info "\t-p\t\tPrepare files for archive build"
    info "\t--version\tIf preparing/generating the archive, use this version for the archive"
    info "\t-g\t\tGenerate FM SDK BuildManager archive (prepare should be executed first)"
    info "\t--dest\tArchive generation destination"
    info "\t--fmsdk\tPath (or url) to the eric-enmsg-custom-fm-oneflow template chart"
    info "\t--fmsdk_tag\tUse provided FM SDK image tag in the docker tar create (defaults to ${FMSDK_TAG})"
    info "\t--fmsdk_repo\tUse provided FM SDK image repo path (defaults to ${IMAGE_REPO_PATH})"
    info "\t--pmsdk\tPath (or url) to the eric-enmsg-custom-pm-oneflow template chart"
    info "\t--pmsdk_tag\tUse provided PM SDK image tag in the docker tar create (defaults to ${PMSDK_TAG})"
    info "\t--pmsdk_repo\tUse provided PM SDK image repo path (defaults to ${IMAGE_REPO_PATH})"
    info "\t--light\tIf generating the archive, use an empty docker.tar"
    info "\t-v\t\tEnable debug mode"
    info "\t-h/--help\t\tPrint help"
}

if [[ $# -eq 0 ]] ; then
    usage
    exit 2
fi

OPTS=$(${GETOPT} -o 'vpgc' -a --longoptions 'h,help,version:,dest:,fmsdk_tag:,fmsdk_repo:,fmsdk:,pmsdk_tag:,pmsdk_repo:,pmsdk:,light' -n "$0" -- "$@")
eval set --${OPTS}


VERBOSE=
CLEAN=
GENERATE=
PREPARE=
_version_=
_fmsdk_tag_=${FMSDK_TAG}
_pmsdk_tag_=${PMSDK_TAG}
_fmsdk_repo_=${IMAGE_REPO_PATH}
_pmsdk_repo_=${IMAGE_REPO_PATH}
_light_=false
_dest_=${BUILD_DIR}
_fmsdk_=${FMSDK_TEMPLATES}
_pmsdk_=${PMSDK_TEMPLATES}

while :; do
    case "${1}" in
        -h|--help)
          usage
          exit 2
        ;;
        --version)
            _version_=${2}
            shift 2
        ;;
        --light)
            _light_=true
            shift
        ;;
        --dest)
            _dest_=$(realpath ${2})
            shift 2
        ;;
        --fmsdk)
            _fmsdk_=${2}
            shift 2
        ;;
        --pmsdk)
            _pmsdk_=${2}
            shift 2
        ;;
        --fmsdk_tag)
          _fmsdk_tag_=${2}
            shift 2
        ;;
        --pmsdk_tag)
            _pmsdk_tag_=${2}
            shift 2
        ;;
        --fmsdk_repo)
            _fmsdk_repo_=${2}
            shift 2
        ;;
        --pmsdk_repo)
            _pmsdk_repo_=${2}
            shift 2
        ;;
        -g)
            GENERATE=true
            shift
        ;;
        -p)
            PREPARE=true
            shift
        ;;
        -c)
            CLEAN=true
            shift
        ;;
        -v)
            VERBOSE=true
            shift
        ;;
        --)
            shift
            break
        ;;
        *)
            error "Unknown argument ${1}"
            exit 1
    esac
done

RM_OPTS=
DOCKER_OPTS=
MKDIR_OPTS=
CP_OPTS=
WGET_OPTS="--quiet"
TAR_OPTS=
if [[ ${VERBOSE} ]] ; then
    set -x
    DOCKER_OPTS="--debug"
    RM_OPTS="--verbose"
    MKDIR_OPTS="--verbose"
    CP_OPTS="--verbose"
    WGET_OPTS="--verbose"
    TAR_OPTS="--verbose"
fi


if [[ ${CLEAN} ]] ; then
    clean
fi

if [[ ${PREPARE} ]] ; then
    if [[ -z ${_version_} ]] ; then
        error "No VERSION specified!"
        exit 2
    fi
    clean
    setup
    get_oneflow_templates ${_fmsdk_} ${FMSDK_TEMPLATES_RELEASES}
    get_oneflow_templates ${_pmsdk_} ${PMSDK_TEMPLATES_RELEASES}
    get_csar_templates ${_version_}
    create_integration_template ${_version_}
    _fm_image_="armdocker.rnd.ericsson.se/${_fmsdk_repo_}/${FMSDK_IMAGE_NAME}:${_fmsdk_tag_}"
    _pm_image_="armdocker.rnd.ericsson.se/${_pmsdk_repo_}/${PMSDK_IMAGE_NAME}:${_pmsdk_tag_}"
    _images_=(${_fm_image_} ${_pm_image_})
    get_docker_images ${_light_} "${_images_[@]}"

    get_scripts
fi

if [[ ${GENERATE} ]] ; then
    if [[ -z ${_version_} ]] ; then
        error "No VERSION specified!"
        exit 2
    fi
    
    _dirs_=(${BUILD_DIR_SCRIPTS} ${BUILD_DIR_DOCKER} ${BUILD_DIR_TEMPLATES_CHART} ${BUILD_DIR_TEMPLATES_CSAR})
    _missing_=false
    for _dir_ in "${_dirs_[@]}" ; do
        if [[ ! -d ${_dir_} || -z "$( ${LS} -A ${_dir_} )" ]] ; then
            echo "${_dir_} is empty, was the prepare step executed?"
            _missing_=true
        fi
    done
    
    if ${_missing_} ; then
        exit 6
    fi
    
    create_sdk_archive "${_version_}" "${BUILD_DIR}" "${_dest_}"
fi
