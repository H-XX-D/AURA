{
  "targets": [
    {
      "target_name": "aura_native",
      "sources": [
        "native/src/aura_binding.cc",
        "native/src/compressor.cc",
        "native/src/decompressor.cc",
        "native/src/template_library.cc",
        "native/src/binary_semantic.cc",
        "native/src/auralite.cc",
        "native/src/brio.cc",
        "native/src/metadata.cc"
      ],
      "include_dirs": [
        "<!@(node -p \"require('node-addon-api').include\")",
        "native/include"
      ],
      "dependencies": [
        "<!(node -p \"require('node-addon-api').gyp\")"
      ],
      "cflags!": ["-fno-exceptions"],
      "cflags_cc!": ["-fno-exceptions"],
      "cflags_cc": ["-std=c++17", "-O3"],
      "defines": ["NAPI_DISABLE_CPP_EXCEPTIONS"],
      "xcode_settings": {
        "GCC_ENABLE_CPP_EXCEPTIONS": "YES",
        "CLANG_CXX_LIBRARY": "libc++",
        "MACOSX_DEPLOYMENT_TARGET": "10.15",
        "OTHER_CPLUSPLUSFLAGS": ["-std=c++17", "-O3"]
      },
      "msvs_settings": {
        "VCCLCompilerTool": {
          "ExceptionHandling": 1,
          "AdditionalOptions": ["/std:c++17", "/O2"]
        }
      }
    }
  ]
}
