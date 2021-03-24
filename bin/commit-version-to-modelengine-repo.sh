#!/bin/bash

# Shell script to update the version in the model_engine repo

set -e

DIR=${PWD}
REPO_VERSION=$(tail -1 VERSION)

cd /

export PIPELINE_RUNNER_KEY=$MODEL_PIPELINE_RUNNER_KEY
setup-ssh.sh

git clone git@gitlab.com:nginfra/movici/model_engine.git
cd model_engine
git config user.email "${PIPELINE_RUNNER_EMAIL}"
git config user.name "${PIPELINE_RUNNER_NAME}"

SELF_AS_REQUIREMENT="${CI_PROJECT_NAME}[models]>=${REPO_VERSION}"
# if already in version file, replace
if grep -q $CI_PROJECT_NAME $REQUIREMENTS_FILE_NAME; then
  sed -i "s/.*$CI_PROJECT_NAME.*/${SELF_AS_REQUIREMENT}/g" $REQUIREMENTS_FILE_NAME
else # else add
  echo "${SELF_AS_REQUIREMENT}" >> $REQUIREMENTS_FILE_NAME
fi

# Git commit without any changes returns exit status 1
# So we check if there are differences
if ! git diff-index --quiet HEAD --; then
  # Need to update all the versions in the model-engine
  make bump-version
  git add --all
  git commit -m "Update requirements of ${CI_PROJECT_NAME}:${REPO_VERSION} in model_engine"
  git push
fi
