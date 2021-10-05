#!/bin/bash
cd VQGAN-CLIP
python generate.py -p "$1"
cd ..
./esrgan/realesrgan-ncnn-vulkan -i VQGAN-CLIP/output.png -o esrgan/output.png
