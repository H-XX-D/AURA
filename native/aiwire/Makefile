.PHONY: all clean install

CXX ?= c++
BUILD_DIR ?= build
OUT_DIR ?= ../../src/aura_compression/native

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	LIB_EXT ?= dylib
	SHARED_FLAG ?= -dynamiclib
else
	LIB_EXT ?= so
	SHARED_FLAG ?= -shared
endif

LIB_NAME ?= libaura_aiwire.$(LIB_EXT)
CXXFLAGS ?= -O3 -std=c++17 -fPIC -Wall -Wextra -pedantic
LDFLAGS ?= $(SHARED_FLAG) -lz

SRC := aura_aiwire.cpp
TARGET := $(BUILD_DIR)/$(LIB_NAME)
INSTALL_TARGET := $(OUT_DIR)/$(LIB_NAME)

all: $(TARGET)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(TARGET): $(SRC) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(SHARED_FLAG) $< -o $@ -lz

install: $(TARGET)
	mkdir -p $(OUT_DIR)
	cp $(TARGET) $(INSTALL_TARGET)

clean:
	rm -rf $(BUILD_DIR)
