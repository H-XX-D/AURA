.PHONY: all clean install

NVCC ?= /usr/local/cuda/bin/nvcc
CUDA_ARCH ?= native
BUILD_DIR ?= build
OUT_DIR ?= ../../src/aura_compression/native
LIB_NAME ?= libaura_cuda.so

NVCCFLAGS ?= -O3 -std=c++17 -Xcompiler -fPIC
LDFLAGS ?= -shared

SRC := aura_cuda.cu
TARGET := $(BUILD_DIR)/$(LIB_NAME)
INSTALL_TARGET := $(OUT_DIR)/$(LIB_NAME)

all: $(TARGET)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(TARGET): $(SRC) | $(BUILD_DIR)
	$(NVCC) $(NVCCFLAGS) -arch=$(CUDA_ARCH) $(LDFLAGS) $< -o $@

install: $(TARGET)
	mkdir -p $(OUT_DIR)
	cp $(TARGET) $(INSTALL_TARGET)

clean:
	rm -rf $(BUILD_DIR)
