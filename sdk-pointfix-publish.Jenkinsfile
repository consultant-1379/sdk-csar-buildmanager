#!/usr/bin/env groovy

/*
 * This is the fmsdk overall pointfix build jenkins pipeline script.
 * It will build all 3 fmsdk artifacts for a pointfix of the FMSDK product.
 * Jenkins: https://fem16s11-eiffel004.eiffel.gic.ericsson.se:8443
 * Job: eric-enm-fmsdk-pointfix-publish
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
        string(name: 'BRANCH', description: '')
        string(name: 'ENM_ISO_REPO_VERSION', description: '')
    }
    stages {

        stage ('Initialization of ENM Versions') {
            steps {
                script {
                    if (!params.ISO_VERSION?.trim()) {
                            currentBuild.result = 'ABORTED'
                            error("ISO_VERSION and must be given. Aborting the build. ")
                     }
                     if (!params.BRANCH?.trim()) {
                            currentBuild.result = 'ABORTED'
                            error("BRANCH and must be given. Aborting the build. ")
                     }
                     if (!params.ENM_ISO_REPO_VERSION?.trim()) {
                            currentBuild.result = 'ABORTED'
                            error("ENM_ISO_REPO_VERSION and must be given. Aborting the build. ")
                     }
                    
                    echo "params.ISO_VERSION - $ISO_VERSION"
                    echo "params.BRANCH  - $BRANCH "
                    echo "params.ENM_ISO_REPO_VERSION  - $ENM_ISO_REPO_VERSION "

                    currentBuild.description = "ISO Version: $ISO_VERSION<br/>"
                    currentBuild.description += "Branch: $BRANCH<br/>"

                    environment_list = [[$class:'StringParameterValue', name:"ISO_VERSION", value:String.valueOf("${ISO_VERSION}")],
                                        [$class:'StringParameterValue', name:"BRANCH", value:String.valueOf("${BRANCH}")],
                                        [$class:'StringParameterValue', name:"ENM_ISO_REPO_VERSION", value:String.valueOf("${ENM_ISO_REPO_VERSION}")]]
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
                        def imageFromFmsdk=""
                        def build = build(job: "eric-enm-fmsdk-pointfix", propagate: true, wait: true, parameters: environment_list)
                        imageFromFmsdk = "$build.buildVariables.IMAGE_TAG"
			env.ERIC_ENM_FMSDK_IMAGE_TAG=imageFromFmsdk
			echo "This is the new eric-enm-fmsdk - ${ERIC_ENM_FMSDK_IMAGE_TAG}"
			echo "${build.buildVariables}"
			env.CHART_REPO = "${ENM_ISO_REPO_VERSION}"
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
                                def build = build(job: "eric-enm-pmsdk-pointfix", propagate: true, wait: true, parameters: environment_list)
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
                        def fmTemplatesBuild = build(job: "fm-sdk-templates-pointfix", propagate: true, wait: true, parameters: environment_list)
                        fmVersionFromTemplates = "$fmTemplatesBuild.buildVariables.VERSION"
                        env.ERIC_ENM_FMSDK_TEMPLATES=fmVersionFromTemplates
			echo "This is the new fm-sdk-templates - ${ERIC_ENM_FMSDK_TEMPLATES}"
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
                        def pmTemplatesBuild = build(job: "pm-sdk-templates-pointfix", propagate: true, wait: true, parameters: environment_list)
                        pmVersionFromTemplates = "$pmTemplatesBuild.buildVariables.VERSION"
                        env.ERIC_ENM_PMSDK_TEMPLATES=pmVersionFromTemplates
			            echo "This is the new pm-sdk-templates - ${ERIC_ENM_PMSDK_TEMPLATES}"
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
                        def chartVersion=""
                        def csarURL = ""
                        def build = build(job: "sdk-csar-buildmanager-Pointfix", propagate: true, wait: true, parameters: environment_list)
                        chartVersion = "$build.buildVariables.VERSION"
                        csarURL = "$build.buildVariables.CSARURL"
                        env.ERIC_ENM_CSAR_URL = csarURL
                        env.ERIC_ENM_CHART_VERSION=chartVersion
                        echo "This is the chart version - ${ERIC_ENM_CHART_VERSION}"
                        echo "This is the csar url - ${ERIC_ENM_CSAR_URL}"
                }
            }
        }
        stage ('SYNC : chart version') {
            steps {
                        sleep(5)
                        script {
                            build_environment_list()
                  }
            }
        }
        stage('Write Parameters to Artifact File') {
            steps {
                script {
                    def artifactFilename = "parameters.txt"
                    writeFile file: artifactFilename, text: "product_set_version=${ENM_ISO_REPO_VERSION}\nchart_version=${ERIC_ENM_CHART_VERSION}\nsimdep_release=1.5.773\nenvironment_name=flexcenm9571"
                    archiveArtifacts artifacts: artifactFilename, fingerprint: true
                }
            }
        }
        
        stage('Write Parameters to XML Artifact File') {
            steps {
                script {
                    def artifactFilename = "parameters.xml"
                    def xmlContent = generateTestwareItems()
                    xmlContent = xmlContent.stripIndent()
                    writeFile file: artifactFilename, text: xmlContent
                    archiveArtifacts artifacts: artifactFilename, fingerprint: true
                }
            }
        }
    }
    post {
        success {
            mail to: "sean.barrett@ericsson.com",
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
        } else if ("${key}".startsWith("CHART_REPO")){
            echo "${key}=${value}"
            environment_list << [$class:'StringParameterValue', name:"${key}", value:String.valueOf("${value}")]
        }

    }
    //build(job: "sync-build-trigger", propagate: true, wait: true, parameters: environment_list)
}

def init_requirements() {
    outString = 'dependencies:\r\n'
    writeFile file: 'requirements.yaml', text: outString
}

def generateTestwareItems() {
    def itemParts = [
        "<item timeout-in-seconds=\"3600\">",
        "<name>FMSDK - insert_name_here</name>",
        "<component>com.ericsson.oss.mediation.sdk:ERICTAFfmsdk_CXP9042868:98.0.3-SNAPSHOT</component>",
        "<suites>suites.xml</suites>",
        "<env-properties>",
        "<property type=\"system\" key=\"sdkBuildManager\">https://arm2s11-eiffel004.eiffel.gic.ericsson.se:8443/nexus/content/repositories/cloud-native-enm-sdk/buildmanager/buildmanager-csar/cloud-native-enm-sdk/${ERIC_ENM_CHART_VERSION}/cloud-native-enm-sdk-${ERIC_ENM_CHART_VERSION}.tar.gz</property>",
        "<property type=\"system\" key=\"integration_value_type\">eric-enm-single-instance-production-integration-values</property>",
        "<property type=\"system\" key=\"product_set_version\">${ENM_ISO_REPO_VERSION}</property>",
        "<property type=\"system\" key=\"repository-url\">armdocker.rnd.ericsson.se/proj_oss_releases/enm</property>",
        "<property type=\"system\" key=\"helm.values.global.ip_version\">IPv4</property>",
        "<property type=\"system\" key=\"sdkTypes.test\">FM,PM</property>",
        "<property type=\"system\" key=\"skipGeneration\">dup-charts</property>",
        "<property type=\"system\" key=\"taf.fm.ne.sim.name\">LTE11dg2ERBS00001</property>",
        "<property type=\"system\" key=\"host.emp.node.client_machine.user.xkumade.pass\">xkumade</property>",
        "<property type=\"jvm\" key=\"options\">-Xms2G -Xmx4G</property>",
        "<property type=\"system\" key=\"taf.config.dit.deployment.name\">flexcenm9571</property>",
        "</env-properties>",
        "</item>"
    ]

    return itemParts.join("")
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
