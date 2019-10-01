#!/bin/bash
if [ "$TRAVIS_PULL_REQUEST" == "false"  && "TRAVIS_REPO_SLUG " != "initc3/HoneyBadgerMPC"]; then
 docker pull dsluiuc/honeybadger-prod:$TRAVIS_COMMIT
else 
 docker pull dsluiuc/honeybadger-prod:latest
fi