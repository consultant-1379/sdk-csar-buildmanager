#!/usr/bin/env groovy

/* IMPORTANT:
 *
 * In order to make this pipeline work, the following configuration on Jenkins is required:
 * - slave with a specific label (see pipeline.agent.label below)
 * - credentials plugin should be installed and have the secrets with the following names:
 *   + lciadm100credentials (token to access Artifactory)
 */

def defaultBobImage = 'armdocker.rnd.ericsson.se/sandbox/adp-staging/adp-cicd/bob.2.0:1.7.0-55'
def bob = new BobCommand()
        .bobImage(defaultBobImage)
        .envVars([
                HOME:'${HOME}',
                BM_PACKAGE_NAME:'${BM_PACKAGE_NAME}',
                PWD:'${PWD}',
		ISO_VERSION: '${ISO_VERSION}',
                ERIC_ENM_FMSDK_IMAGE_TAG: '${ERIC_ENM_FMSDK_IMAGE_TAG}',
                ERIC_ENM_FMSDK_TEMPLATES: '${ERIC_ENM_FMSDK_TEMPLATES}',
                ERIC_ENM_PMSDK_IMAGE_TAG: '${ERIC_ENM_PMSDK_IMAGE_TAG}',
                ERIC_ENM_PMSDK_TEMPLATES: '${ERIC_ENM_PMSDK_TEMPLATES}',
		PRODUCT_SET_VERSION: '${PRODUCT_SET_VERSION}',
		CHART_REPO: '${CHART_REPO}'
        ])
        .needDockerSocket(true)
        .toString()
def GIT_COMMITTER_NAME = 'enmadm100'
def GIT_COMMITTER_EMAIL = 'enmadm100@ericsson.com'
def failedStage = ''
pipeline {
    agent {
        label 'Cloud-Native'
    }
    environment{
        repositoryUrl = "https://arm2s11-eiffel004.eiffel.gic.ericsson.se:8443/nexus/content/repositories/cloud-native-enm-sdk/buildmanager"
        BM_PACKAGE_NAME = "cloud-native-enm-sdk"
        OPENIDM = "eric-enm-openidm-change-password:latest"
        PASSKEY = "eric-enm-securestorage-regen-passkey:latest"
        OPENIDM_IMAGE_PATH = "armdocker.rnd.ericsson.se/proj-enm"
        PASSKEY_IMAGE_PATH = "armdocker.rnd.ericsson.se/proj-enm"
        PACKAGE_TYPE="buildmanager-csar"
        CENMBUILD_ARM_TOKEN = credentials('cenmbuild_ARM_token')
    }
    parameters {
        string(name: 'ISO_VERSION', defaultValue: '0.0.0', description: 'The ENM ISO version (e.g. 1.65.77)')
        string(name: 'SPRINT_TAG', description: 'Tag for GIT tagging the repository after build')
    }
    stages {
        stage('Inject Credential Files') {
            steps {
			    sh 'printenv'
                withCredentials([file(credentialsId: 'lciadm100-docker-auth', variable: 'dockerConfig')]) {
                    sh "install -m 600 ${dockerConfig} ${HOME}/.docker/config.json"
                }
            }
        }
        stage('Checkout Base Image Git Repository') {
            steps {
                git branch: 'master',
                     credentialsId: 'enmadm100_private_key',
                     url: '${GERRIT_MIRROR}/OSS/ENM-Parent/SQ-Gate/com.ericsson.oss.mediation.sdk/sdk-csar-buildmanager'
                sh '''
                    git remote set-url origin --push ${GERRIT_CENTRAL}/OSS/ENM-Parent/SQ-Gate/com.ericsson.oss.mediation.sdk/sdk-csar-buildmanager
                '''
            }
        }
        stage('Check Stage for version change'){
            steps{
                echo sh(script: 'env', returnStdout:true)
                sh '''
                        echo `date` > timestamp
                        git add timestamp
                        git commit -m "NO JIRA - Time Stamp "
                        git push origin HEAD:master

                '''
            }
        }
        stage('Generate new version') {
            steps {
                sh "${bob} generate-new-version"
                script {
                    env.VERSION = sh(script: "cat .bob/var.version", returnStdout:true).trim()
                    echo "Generated VERSION is: ${VERSION}"
                    env.RSTATE = sh(script: "cat .bob/var.rstate", returnStdout:true).trim()
                    echo "Generated RSTATE is: ${RSTATE}"
                }
            }
            post {
                failure {
                    script {
                        failedStage = env.STAGE_NAME
                    }
                }
            }
        }

        stage('Swap monitoring image version'){
            steps{
                echo sh(script: 'env', returnStdout:true)
                step ([$class: 'CopyArtifact', projectName: 'sync-build-trigger', filter: "*"])
                script {
                    def props = readProperties file: 'enm_artifact.properties'
                    env.ERIC_ENM_MONITORING_EAP7_IMAGE_TAG = props.ERIC_ENM_MONITORING_EAP7_IMAGE_TAG
                }
                sh "sed -i 's|armdocker.rnd.ericsson.se/proj-enm/eric-enm-monitoring-eap7:.*|armdocker.rnd.ericsson.se/proj-enm/eric-enm-monitoring-eap7:${env.ERIC_ENM_MONITORING_EAP7_IMAGE_TAG}|' ${WORKSPACE}/src/sdk_builld_images.txt"
                sh '''
                    if git status | grep '${WORKSPACE}/src/sdk_builld_images.txt' > /dev/null; then
                        git commit -m "NO JIRA - Updating sdk_build_images.txt with  monitoring version"
                        git push origin HEAD:master
                    else
                        echo `date` > timestamp
                        git add timestamp
                        git commit -m "NO JIRA - Time Stamp "
                        git push origin HEAD:master
                    fi
                '''
            }
        }

        stage('Generate Cloud Native ENM SDK BuildManager Archive') {
            steps {
                script {
                    sh "${bob} generate-bm-archive"
                }
            }
            post {
                failure {
                    script {
                        failedStage = env.STAGE_NAME
                    }
                }
            }
        }
        stage('Publish BuildManager Package to Nexus') {
            steps {
              script {
               env.filesize = sh(script: "du -h build/${BM_PACKAGE_NAME}-${VERSION}.tar.gz | cut -f1", returnStdout: true).trim()
               sh "bash upload_to_nexus.sh ${VERSION} build/${BM_PACKAGE_NAME}-${VERSION}.tar.gz ${repositoryUrl} ${BM_PACKAGE_NAME} ${PACKAGE_TYPE}"
               echo "VERSION = ${VERSION}, BM_PACKAGE = ${BM_PACKAGE_NAME}, repository = ${repositoryUrl}, package type = ${PACKAGE_TYPE}"
               env.CSARURL = "${repositoryUrl}/${PACKAGE_TYPE}/${BM_PACKAGE_NAME}/${VERSION}/${BM_PACKAGE_NAME}-${VERSION}.tar.gz"
	       env.CHART_VERSION = "${VERSION}"
	       }
              echo "env CSAR URL = ${CSARURL}"
            }
        }
	stage('Generate ADP Parameters') {
            steps {
                sh "${bob} generate-output-parameters"
                archiveArtifacts 'artifact.properties'
            }
        }
        stage('Tag sdk-csar-buildmanager Repository') {
            steps {
                wrap([$class: 'BuildUser']) {
                    script {
                        def bobWithCommitterInfo = new BobCommand()
                                .bobImage(defaultBobImage)
                                .needDockerSocket(true)
                                .envVars([
                                        'AUTHOR_NAME'        : "\${BUILD_USER:-${GIT_COMMITTER_NAME}}",
                                        'AUTHOR_EMAIL'       : "\${BUILD_USER_EMAIL:-${GIT_COMMITTER_EMAIL}}",
                                        'GIT_COMMITTER_NAME' : "${GIT_COMMITTER_NAME}",
                                        'GIT_COMMITTER_EMAIL': "${GIT_COMMITTER_EMAIL}"
                                ])
                                .toString()
                        sh "${bobWithCommitterInfo} create-git-tag"
                        sh """
                            tag_id=\$(cat .bob/var.version)
                            git push origin \${tag_id}
                        """
                    }
                }
            }
            post {
                failure {
                    script {
                        failedStage = env.STAGE_NAME
                    }
                }
                always {
                    script {
                        sh "${bob} remove-git-tag"
                    }
                }
            }
        }
    }
    post {
        success {
            script {
                sh '''
                    set +x
                    git tag --annotate --message "Tagging latest in sprint" --force $SPRINT_TAG HEAD
                    git push --force origin $SPRINT_TAG
                    git tag --annotate --message "Tagging latest in sprint with ISO version" --force ${SPRINT_TAG}_iso_${ISO_VERSION} HEAD
                    git push --force origin ${SPRINT_TAG}_iso_${ISO_VERSION}
                '''
            }
        }
        failure {
            mail to: '${GERRIT_CHANGE_OWNER_EMAIL},${GERRIT_PATCHSET_UPLOADER_EMAIL}',
                    subject: "Failed Pipeline: ${currentBuild.fullDisplayName}",
                    body: "Failure on ${env.BUILD_URL}"
        }
    }
}

import groovy.transform.builder.Builder
import groovy.transform.builder.SimpleStrategy

@Builder(builderStrategy = SimpleStrategy, prefix = '')
class BobCommand {
    def bobImage = 'bob.2.0:latest'
    def envVars = [:]
    def needDockerSocket = false

    String toString() {
        def env = envVars
                .collect({ entry -> "-e ${entry.key}=\"${entry.value}\"" })
                .join(' ')

        def cmd = """\
            |docker run
            |--init
            |--rm
            |--workdir \${PWD}
            |--user \$(id -u):\$(id -g)
            |-v \${PWD}:\${PWD}
            |-v /etc/group:/etc/group:ro
            |-v /etc/passwd:/etc/passwd:ro
			|-v \${HOME}/.docker:\${HOME}/.docker
            |-v \${HOME}:\${HOME}
            |${needDockerSocket ? '-v /var/run/docker.sock:/var/run/docker.sock' : ''}
            |${env}
            |\$(for group in \$(id -G); do printf ' --group-add %s' "\$group"; done)
            |--group-add \$(stat -c '%g' /var/run/docker.sock)
            |${bobImage}
            |"""
        return cmd
                .stripMargin()           // remove indentation
                .replace('\n', ' ')      // join lines
                .replaceAll(/[ ]+/, ' ') // replace multiple spaces by one
    }
}
