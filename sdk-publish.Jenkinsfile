#!/usr/bin/env groovy

/*
 * This is the fmsdk overall build jenkins pipeline script.
 * It will build all 3 fmsdk artifacts for a release of the FMSDK product.
 * Jenkins: https://fem16s11-eiffel004.eiffel.gic.ericsson.se:8443
 * Job: eric-enm-fmsdk-publish
 */

pipeline {
    agent { node { label 'Cloud-Native' } }
    options {
        timestamps()
    }
    environment {
        PIPELINE_LAST_STAGE_STATUS = 'UNKNOWN'
        CENMBUILD_ARM_TOKEN = credentials('cenmbuild_ARM_token')
    }
    parameters {
        string(name: 'ISO_VERSION', description: 'The ENM ISO version (e.g. 1.65.77)')
        string(name: 'SPRINT_TAG', description: 'Tag for GIT tagging the repository after build')
        string(name: 'PRODUCT_SET_VERSION', description: 'The product set version from ENM build')
    }
    stages {
        stage ('Initialization of ENM Versions') {
            steps {
                script {
                    if (!params.ISO_VERSION?.trim()) {
                            currentBuild.result = 'ABORTED'
                            error("ISO_VERSION and must be given. Aborting the build. ")
                     }
                     if (!params.SPRINT_TAG?.trim()) {
                            currentBuild.result = 'ABORTED'
                            error("SPRINT_TAG and must be given. Aborting the build. ")
                     }
                    echo "params.ISO_VERSION - $ISO_VERSION"
                    echo "params.SPRINT_TAG  - $SPRINT_TAG "
                    echo "params.PRODUCT_SET_VERSION  - $PRODUCT_SET_VERSION "

                    currentBuild.description = "ISO Version: $ISO_VERSION<br/>"
                    currentBuild.description += "Sprint Tag: $SPRINT_TAG<br/>"

                    environment_list = [[$class:'StringParameterValue', name:"ISO_VERSION", value:String.valueOf("${ISO_VERSION}")],
                                        [$class:'StringParameterValue', name:"SPRINT_TAG", value:String.valueOf("${SPRINT_TAG}")]]
                    echo "$environment_list"
                }
            }
        }
        stage('Inject Credential Files') {
            steps {
                withCredentials([file(credentialsId: 'lciadm100-docker-auth', variable: 'dockerConfig')]) {
                    sh "install -m 600 ${dockerConfig} ${HOME}/.docker/config.json"
                }
            }
        }
        stage('Build eric-enm-fmsdk') {
                steps {
                    script{
                        env.FMSDK_SUCCESS = true
                        def imageFromFmsdk=""
                        def build = build(job: "eric-enm-fmsdk", propagate: true, wait: true, parameters: environment_list)
                        imageFromFmsdk = "$build.buildVariables.IMAGE_TAG"
                        env.ERIC_ENM_FMSDK_IMAGE_TAG=imageFromFmsdk
                        echo "This is the new eric-enm-fmsdk - ${ERIC_ENM_FMSDK_IMAGE_TAG}"
                        echo "${build.buildVariables}"
			env.CHART_REPO = "${PRODUCT_SET_VERSION}"
                    }
                }
        }
        stage ('SYNC : eric-enm-fmsdk Image') {
            steps {
                        sleep(5)
                        script {
                            build_environment_list()
                  }
            }
        }
        stage('Build eric-enm-pmsdk') {
            steps {
                script{
                    def imageFromPmsdk=""
                    def build = build(job: "eric-enm-pmsdk", propagate: true, wait: true, parameters: environment_list)
                    imageFromPmsdk = "$build.buildVariables.IMAGE_TAG"
                    env.ERIC_ENM_PMSDK_IMAGE_TAG=imageFromPmsdk
                    echo "This is the new eric-enm-pmsdk - ${ERIC_ENM_PMSDK_IMAGE_TAG}"
                    echo "${build.buildVariables}"
                }
            }
        }
        stage ('SYNC : eric-enm-pmsdk Image') {
            steps {
                        sleep(5)
                        script {
                            build_environment_list()
                  }
            }
        }
        stage('Build fm-sdk-templates') {
            steps {
                script{
                    def fmVersionFromTemplates=""
                    def fmTemplatesBuild = build(job: "fm-sdk-templates", propagate: true, wait: true, parameters: environment_list)
                    fmVersionFromTemplates = "$fmTemplatesBuild.buildVariables.VERSION"
                    env.ERIC_ENM_FMSDK_TEMPLATES=fmVersionFromTemplates
                    echo "This is the new fm-sdk-templates - ${ERIC_ENM_FMSDK_TEMPLATES}"

                    fmTemplatesUrl = "$fmTemplatesBuild.buildVariables.TEMPLATESURL"
                }
            }
        }
        stage ('SYNC : fm-sdk-templates Image') {
            steps {
                        sleep(5)
                        script {
                            build_environment_list()
                  }
            }
        }
        stage('Build pm-sdk-templates') {
            steps {
                script{
                    def pmVersionFromTemplates=""
                    def pmTemplatesBuild = build(job: "pm-sdk-templates", propagate: true, wait: true, parameters: environment_list)
                    pmVersionFromTemplates = "$pmTemplatesBuild.buildVariables.VERSION"
                    env.ERIC_ENM_PMSDK_TEMPLATES=pmVersionFromTemplates
                    echo "This is the new pm-sdk-templates - ${ERIC_ENM_PMSDK_TEMPLATES}"

                    pmTemplatesUrl = "$pmTemplatesBuild.buildVariables.TEMPLATESURL"
                }
            }
        }
        stage ('SYNC : pm-sdk-templates Image') {
            steps {
                        sleep(5)
                        script {
                            build_environment_list()
                  }
            }
        }
        stage('Build sdk-csar-buildmanager') {
            steps {
                script{
                    def build = build(job: "sdk-csar-buildmanager", propagate: true, wait: true, parameters: environment_list)
                    env.csarUrl = "$build.buildVariables.CSARURL"
                    env.CHART_VERSION = "$build.buildVariables.CHART_VERSION"
                }
            }
        }
    }
    post {
        success {
            mail to: "Thoms.Johnston@ericsson.com",
                    subject: "Failed Pipeline: ${currentBuild.fullDisplayName}",
                    body: "Failure on ${env.BUILD_URL}"
        }
        failure {
                script {
                        failedStage = env.STAGE_NAME
                }
            }
    }
}
def build_environment_list(){
    env.getEnvironment().each { key, value ->
        if ("${key}".startsWith("ERIC_")){
            echo "Adding new parameter to build_environment_list - ${key} "
            echo "${key}=${value}"
            environment_list << [$class:'StringParameterValue', name:"${key}", value:String.valueOf("${value}")]
        } else if ("${key}".startsWith("IMAGE_")){
            echo "${key}=${value}"
            environment_list << [$class:'StringParameterValue', name:"${key}", value:String.valueOf("${value}")]
        } else if ("${key}" == "PRODUCT_SET_VERSION") {
            echo "${key}=${value}"
            environment_list << [$class:'StringParameterValue', name:"${key}", value:String.valueOf("${value}")]
        } else if ("${key}" == "CHART_REPO") {
            echo "${key}=${value}"
            environment_list << [$class:'StringParameterValue', name:"${key}", value:String.valueOf("${value}")]
        }
    }
}


def init_requirements() {
    outString = 'dependencies:\r\n'
    writeFile file: 'requirements.yaml', text: outString
}

def build_requirements_file(){
    env.getEnvironment().each { key, value ->
        if (key.startsWith("ERIC_ENM") || key.startsWith("ERIC_PM")){
            if (key.endsWith("_REPOSITORY_TAG")){
                return
            }
            else{
                key=key.replace("_IMAGE_TAG","")
                env.repoKey = '${'+key+'_REPOSITORY_TAG}'
                repository=sh(returnStdout: true, script: "echo $repoKey").trim()
            if (repository == ""){
                repoString = '  repository: https://arm.epk.ericsson.se/artifactory/proj-enm-helm/'
            } else {
                repoString = '  repository: ' + repository
            }
                key = key.replace("_POINTFIX","")
                key=key.toLowerCase().replace("_","-")
                nameString = '- name: '+ key
                versionString = '  version: ' + value
            }
        readContent = readFile 'requirements.yaml'
        outString = readContent + nameString + "\r\n" + repoString + "\r\n" + versionString + "\r\n"
        writeFile file: 'requirements.yaml', text: outString
        }
    }
}

