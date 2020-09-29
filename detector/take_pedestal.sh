#!/bin/bash

#Bernina 1p5M, 16M, Vakuum:
#DETECTORS="1 7 13"
#DETECTORS="1 13"
#DETECTORS="1"

#Alvra 4.5M, 16M(also 4M mode)
#DETECTORS="2 6"
DETECTORS="6"

export PATH=/home/dbe/miniconda3/bin:$PATH
source /home/dbe/miniconda3/etc/profile.d/conda.sh
conda activate detector

echo reset bits
for d in ${DETECTORS}
do
    sls_detector_put ${d}-clearbit 0x5d 0
    sls_detector_put ${d}-clearbit 0x5d 12
    sls_detector_put ${d}-clearbit 0x5d 13
done

sleep 1

echo HG0
for d in ${DETECTORS}
do
    sls_detector_put ${d}-setbit 0x5d 0
done
sleep 10

echo G0
for d in ${DETECTORS}
do
    sls_detector_put ${d}-clearbit 0x5d 0
done
sleep 10

echo G1
for d in ${DETECTORS}
do
    sls_detector_put ${d}-setbit 0x5d 12
done
sleep 10

echo G2
for d in ${DETECTORS}
do
    sls_detector_put ${d}-setbit 0x5d 13
done
sleep 10

echo reset bits
for d in ${DETECTORS}
do
    sls_detector_put ${d}-clearbit 0x5d 0
    sls_detector_put ${d}-clearbit 0x5d 12
    sls_detector_put ${d}-clearbit 0x5d 13
done


