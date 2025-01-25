#!/bin/bash

# If you wish to remove the poetry python env uncomment this
pe=$(poetry env info -p)
if [ -n "$pe" ]; then
  echo "Removing $pe"
  rm -rf $pe
fi

# Date just used to show how long the env takes to create
date
poetry lock
poetry install
date