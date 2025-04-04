#!/bin/bash
WORKDIR=/runner/repo
test -d ${WORKDIR} && rm -rfv ${WORKDIR}/

echo
echo "git clone the ${GIT_REPO_URL} into ${WORKDIR}"
git clone ${GIT_REPO_URL} ${WORKDIR}
cd ${WORKDIR}

if [ -z ${GIT_REPO_REF} ]; then
  echo "No GIT_REPO_REF specified. Using default branch"
else
  echo "Checking out ref ${GIT_REPO_REF}"
  git checkout ${GIT_REPO_REF}
fi
python /app/main.py
