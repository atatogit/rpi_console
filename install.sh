#!/bin/bash

DIR=/usr/local/bin/rpi_console

rm -rf $DIR/*

cp *py $DIR/
cp -r resources $DIR/ 