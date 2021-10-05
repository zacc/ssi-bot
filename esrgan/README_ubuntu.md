# RealESRGAN

We have provided three models:

1. realesrgan-x4plus  (default)
2. realesrnet-x4plus
3. esrgan-x4

Command:

You may need to change the file mode:

chmod u+x realesrgan-ncnn-vulkan

1. ./realesrgan-ncnn-vulkan -i input.jpg -o output.png
2. ./realesrgan-ncnn-vulkan -i input.jpg -o output.png -n realesrnet-x4plus
3. ./realesrgan-ncnn-vulkan -i input.jpg -o output.png -n esrgan-x4

------------------------

GitHub: https://github.com/xinntao/Real-ESRGAN/
Paper: https://arxiv.org/abs/2107.10833

------------------------

This executable file is **portable** and includes all the binaries and models required. No CUDA or PyTorch environment is needed.

Note that it may introduce block inconsistency (and also generate slightly different results from the PyTorch implementation), because this executable file first crops the input image into several tiles, and then processes them separately, finally stitches together.

This executable file is based on the wonderful [Tencent/ncnn](https://github.com/Tencent/ncnn) and [realsr-ncnn-vulkan](https://github.com/nihui/realsr-ncnn-vulkan) by [nihui](https://github.com/nihui).
