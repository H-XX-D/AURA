#include <cuda_runtime.h>

#include <cmath>
#include <cstdio>
#include <cstring>

namespace {

thread_local char g_last_error[512] = "ok";

void set_error(const char *context, cudaError_t err) {
    std::snprintf(
        g_last_error,
        sizeof(g_last_error),
        "%s: %s",
        context,
        cudaGetErrorString(err));
}

void set_error_message(const char *message) {
    std::snprintf(g_last_error, sizeof(g_last_error), "%s", message);
}

int finish_cuda_call(const char *context, cudaError_t err) {
    if (err != cudaSuccess) {
        set_error(context, err);
        return static_cast<int>(err);
    }
    set_error_message("ok");
    return 0;
}

__global__ void histogram_kernel(
    const unsigned char *data,
    size_t size,
    unsigned int *histogram) {
    __shared__ unsigned int local_histogram[256];

    for (int bin = threadIdx.x; bin < 256; bin += blockDim.x) {
        local_histogram[bin] = 0;
    }
    __syncthreads();

    const size_t global_thread = blockIdx.x * blockDim.x + threadIdx.x;
    const size_t stride = static_cast<size_t>(blockDim.x) * gridDim.x;

    for (size_t index = global_thread; index < size; index += stride) {
        atomicAdd(&local_histogram[data[index]], 1U);
    }
    __syncthreads();

    for (int bin = threadIdx.x; bin < 256; bin += blockDim.x) {
        const unsigned int value = local_histogram[bin];
        if (value != 0U) {
            atomicAdd(&histogram[bin], value);
        }
    }
}

__global__ void entropy_kernel(
    const unsigned int *histogram,
    size_t size,
    double *entropy_out) {
    __shared__ double partials[256];
    const int tid = threadIdx.x;

    double term = 0.0;
    if (tid < 256 && size > 0) {
        const unsigned int count = histogram[tid];
        if (count > 0U) {
            const double probability = static_cast<double>(count) / static_cast<double>(size);
            term = -probability * log2(probability);
        }
    }

    partials[tid] = term;
    __syncthreads();

    for (int stride = 128; stride > 0; stride >>= 1) {
        if (tid < stride) {
            partials[tid] += partials[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        *entropy_out = partials[0];
    }
}

    __global__ void rolling_hash3_kernel(
        const unsigned char *data,
        size_t size,
        unsigned int *hashes) {
        const size_t index = blockIdx.x * blockDim.x + threadIdx.x;
        if (index + 2 >= size) {
            return;
        }

        unsigned int hash = 2166136261U;
        hash = (hash ^ static_cast<unsigned int>(data[index])) * 16777619U;
        hash = (hash ^ static_cast<unsigned int>(data[index + 1])) * 16777619U;
        hash = (hash ^ static_cast<unsigned int>(data[index + 2])) * 16777619U;
        hashes[index] = hash;
    }

    __global__ void lz_match_candidates_kernel(
        const unsigned char *data,
        size_t size,
        unsigned int window_size,
        unsigned int min_match,
        unsigned int max_match,
        unsigned int *distances,
        unsigned char *lengths) {
        const size_t pos = blockIdx.x * blockDim.x + threadIdx.x;
        if (pos >= size) {
            return;
        }

        const size_t remaining = size - pos;
        unsigned int allowed = max_match;
        if (allowed > remaining) {
            allowed = static_cast<unsigned int>(remaining);
        }
        if (allowed < min_match) {
            return;
        }

        unsigned int lookback = window_size;
        if (lookback > pos) {
            lookback = static_cast<unsigned int>(pos);
        }

        unsigned int best_distance = 0U;
        unsigned int best_length = 0U;

        for (unsigned int distance = 1U; distance <= lookback; ++distance) {
            unsigned int candidate_limit = allowed;
            if (candidate_limit > distance) {
                candidate_limit = distance;
            }
            if (candidate_limit < min_match) {
                continue;
            }

            const size_t candidate = pos - distance;
            unsigned int length = 0U;
            while (length < candidate_limit &&
                   data[candidate + length] == data[pos + length]) {
                ++length;
            }

            if (length >= min_match && length > best_length) {
                best_distance = distance;
                best_length = length;
                if (best_length == allowed) {
                    break;
                }
            }
        }

        if (best_length >= min_match) {
            distances[pos] = best_distance;
            lengths[pos] = static_cast<unsigned char>(best_length);
        }
    }

    int choose_grid_size(size_t work_items, int block_size) {
        int grid_size = static_cast<int>((work_items + block_size - 1) / block_size);
        if (grid_size < 1) {
            grid_size = 1;
        }

        int device = 0;
        cudaDeviceProp properties{};
        if (cudaGetDevice(&device) == cudaSuccess &&
            cudaGetDeviceProperties(&properties, device) == cudaSuccess &&
            properties.multiProcessorCount > 0) {
            const int desired_blocks = properties.multiProcessorCount * 8;
            if (grid_size > desired_blocks) {
                grid_size = desired_blocks;
            }
        }
        return grid_size;
    }

int compute_histogram_device(
    const unsigned char *host_data,
    size_t size,
    unsigned int *host_histogram) {
    if (host_histogram == nullptr) {
        set_error_message("histogram output pointer is null");
        return -1;
    }

    std::memset(host_histogram, 0, sizeof(unsigned int) * 256);
    if (size == 0) {
        set_error_message("ok");
        return 0;
    }
    if (host_data == nullptr) {
        set_error_message("input pointer is null");
        return -2;
    }

    unsigned char *device_data = nullptr;
    unsigned int *device_histogram = nullptr;

    cudaError_t err = cudaMalloc(reinterpret_cast<void **>(&device_data), size);
    if (err != cudaSuccess) {
        return finish_cuda_call("cudaMalloc(data)", err);
    }

    err = cudaMalloc(reinterpret_cast<void **>(&device_histogram), sizeof(unsigned int) * 256);
    if (err != cudaSuccess) {
        cudaFree(device_data);
        return finish_cuda_call("cudaMalloc(histogram)", err);
    }

    err = cudaMemcpy(device_data, host_data, size, cudaMemcpyHostToDevice);
    if (err != cudaSuccess) {
        cudaFree(device_histogram);
        cudaFree(device_data);
        return finish_cuda_call("cudaMemcpy(input)", err);
    }

    err = cudaMemset(device_histogram, 0, sizeof(unsigned int) * 256);
    if (err != cudaSuccess) {
        cudaFree(device_histogram);
        cudaFree(device_data);
        return finish_cuda_call("cudaMemset(histogram)", err);
    }

    const int block_size = 256;
    int grid_size = static_cast<int>((size + block_size - 1) / block_size);
    if (grid_size < 1) {
        grid_size = 1;
    }

    int device = 0;
    cudaDeviceProp properties{};
    if (cudaGetDevice(&device) == cudaSuccess &&
        cudaGetDeviceProperties(&properties, device) == cudaSuccess &&
        properties.multiProcessorCount > 0) {
        const int desired_blocks = properties.multiProcessorCount * 8;
        if (grid_size > desired_blocks) {
            grid_size = desired_blocks;
        }
    }

    histogram_kernel<<<grid_size, block_size>>>(device_data, size, device_histogram);

    err = cudaGetLastError();
    if (err != cudaSuccess) {
        cudaFree(device_histogram);
        cudaFree(device_data);
        return finish_cuda_call("histogram_kernel", err);
    }

    err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {
        cudaFree(device_histogram);
        cudaFree(device_data);
        return finish_cuda_call("cudaDeviceSynchronize(histogram)", err);
    }

    err = cudaMemcpy(host_histogram, device_histogram, sizeof(unsigned int) * 256, cudaMemcpyDeviceToHost);
    cudaFree(device_histogram);
    cudaFree(device_data);
    return finish_cuda_call("cudaMemcpy(histogram)", err);
}

    int compute_rolling_hash3_device(
        const unsigned char *host_data,
        size_t size,
        unsigned int *host_hashes) {
        const size_t hash_count = size >= 3 ? size - 2 : 0;
        if (hash_count == 0) {
            set_error_message("ok");
            return 0;
        }
        if (host_data == nullptr) {
            set_error_message("input pointer is null");
            return -1;
        }
        if (host_hashes == nullptr) {
            set_error_message("rolling hash output pointer is null");
            return -2;
        }

        unsigned char *device_data = nullptr;
        unsigned int *device_hashes = nullptr;

        cudaError_t err = cudaMalloc(reinterpret_cast<void **>(&device_data), size);
        if (err != cudaSuccess) {
            return finish_cuda_call("cudaMalloc(rolling data)", err);
        }

        err = cudaMalloc(reinterpret_cast<void **>(&device_hashes), sizeof(unsigned int) * hash_count);
        if (err != cudaSuccess) {
            cudaFree(device_data);
            return finish_cuda_call("cudaMalloc(rolling hashes)", err);
        }

        err = cudaMemcpy(device_data, host_data, size, cudaMemcpyHostToDevice);
        if (err != cudaSuccess) {
            cudaFree(device_hashes);
            cudaFree(device_data);
            return finish_cuda_call("cudaMemcpy(rolling input)", err);
        }

        const int block_size = 256;
        const int grid_size = choose_grid_size(hash_count, block_size);
        rolling_hash3_kernel<<<grid_size, block_size>>>(device_data, size, device_hashes);

        err = cudaGetLastError();
        if (err != cudaSuccess) {
            cudaFree(device_hashes);
            cudaFree(device_data);
            return finish_cuda_call("rolling_hash3_kernel", err);
        }

        err = cudaDeviceSynchronize();
        if (err != cudaSuccess) {
            cudaFree(device_hashes);
            cudaFree(device_data);
            return finish_cuda_call("cudaDeviceSynchronize(rolling hash)", err);
        }

        err = cudaMemcpy(host_hashes, device_hashes, sizeof(unsigned int) * hash_count, cudaMemcpyDeviceToHost);
        cudaFree(device_hashes);
        cudaFree(device_data);
        return finish_cuda_call("cudaMemcpy(rolling hashes)", err);
    }

    int compute_lz_match_candidates_device(
        const unsigned char *host_data,
        size_t size,
        unsigned int window_size,
        unsigned int min_match,
        unsigned int max_match,
        unsigned int *host_distances,
        unsigned char *host_lengths) {
        if (host_distances == nullptr || host_lengths == nullptr) {
            set_error_message("match candidate output pointer is null");
            return -1;
        }
        if (size == 0) {
            set_error_message("ok");
            return 0;
        }
        if (host_data == nullptr) {
            set_error_message("input pointer is null");
            return -2;
        }
        if (window_size == 0 || min_match == 0 || max_match < min_match || max_match > 255U) {
            set_error_message("invalid match candidate parameters");
            return -3;
        }

        std::memset(host_distances, 0, sizeof(unsigned int) * size);
        std::memset(host_lengths, 0, sizeof(unsigned char) * size);

        unsigned char *device_data = nullptr;
        unsigned int *device_distances = nullptr;
        unsigned char *device_lengths = nullptr;

        cudaError_t err = cudaMalloc(reinterpret_cast<void **>(&device_data), size);
        if (err != cudaSuccess) {
            return finish_cuda_call("cudaMalloc(match data)", err);
        }

        err = cudaMalloc(reinterpret_cast<void **>(&device_distances), sizeof(unsigned int) * size);
        if (err != cudaSuccess) {
            cudaFree(device_data);
            return finish_cuda_call("cudaMalloc(match distances)", err);
        }

        err = cudaMalloc(reinterpret_cast<void **>(&device_lengths), sizeof(unsigned char) * size);
        if (err != cudaSuccess) {
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("cudaMalloc(match lengths)", err);
        }

        err = cudaMemcpy(device_data, host_data, size, cudaMemcpyHostToDevice);
        if (err != cudaSuccess) {
            cudaFree(device_lengths);
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("cudaMemcpy(match input)", err);
        }

        err = cudaMemset(device_distances, 0, sizeof(unsigned int) * size);
        if (err != cudaSuccess) {
            cudaFree(device_lengths);
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("cudaMemset(match distances)", err);
        }

        err = cudaMemset(device_lengths, 0, sizeof(unsigned char) * size);
        if (err != cudaSuccess) {
            cudaFree(device_lengths);
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("cudaMemset(match lengths)", err);
        }

        const int block_size = 256;
        const int grid_size = choose_grid_size(size, block_size);
        lz_match_candidates_kernel<<<grid_size, block_size>>>(
            device_data,
            size,
            window_size,
            min_match,
            max_match,
            device_distances,
            device_lengths);

        err = cudaGetLastError();
        if (err != cudaSuccess) {
            cudaFree(device_lengths);
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("lz_match_candidates_kernel", err);
        }

        err = cudaDeviceSynchronize();
        if (err != cudaSuccess) {
            cudaFree(device_lengths);
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("cudaDeviceSynchronize(match candidates)", err);
        }

        err = cudaMemcpy(host_distances, device_distances, sizeof(unsigned int) * size, cudaMemcpyDeviceToHost);
        if (err != cudaSuccess) {
            cudaFree(device_lengths);
            cudaFree(device_distances);
            cudaFree(device_data);
            return finish_cuda_call("cudaMemcpy(match distances)", err);
        }

        err = cudaMemcpy(host_lengths, device_lengths, sizeof(unsigned char) * size, cudaMemcpyDeviceToHost);
        cudaFree(device_lengths);
        cudaFree(device_distances);
        cudaFree(device_data);
        return finish_cuda_call("cudaMemcpy(match lengths)", err);
    }

    }  // namespace

extern "C" {

const char *aura_cuda_last_error(void) {
    return g_last_error;
}

int aura_cuda_device_count(int *count_out) {
    if (count_out == nullptr) {
        set_error_message("device count output pointer is null");
        return -1;
    }

    int count = 0;
    cudaError_t err = cudaGetDeviceCount(&count);
    if (err != cudaSuccess) {
        *count_out = 0;
        return finish_cuda_call("cudaGetDeviceCount", err);
    }

    *count_out = count;
    set_error_message("ok");
    return 0;
}

int aura_cuda_get_device_name(int device_index, char *name_out, size_t name_out_size) {
    if (name_out == nullptr || name_out_size == 0) {
        set_error_message("device name output buffer is null or empty");
        return -1;
    }

    cudaDeviceProp properties{};
    cudaError_t err = cudaGetDeviceProperties(&properties, device_index);
    if (err != cudaSuccess) {
        name_out[0] = '\0';
        return finish_cuda_call("cudaGetDeviceProperties", err);
    }

    std::snprintf(name_out, name_out_size, "%s", properties.name);
    set_error_message("ok");
    return 0;
}

int aura_cuda_histogram_u8(const unsigned char *data, size_t size, unsigned int *histogram_out) {
    return compute_histogram_device(data, size, histogram_out);
}

int aura_cuda_shannon_entropy_u8(const unsigned char *data, size_t size, double *entropy_out) {
    if (entropy_out == nullptr) {
        set_error_message("entropy output pointer is null");
        return -1;
    }

    *entropy_out = 0.0;
    if (size == 0) {
        set_error_message("ok");
        return 0;
    }

    unsigned int host_histogram[256];
    int rc = compute_histogram_device(data, size, host_histogram);
    if (rc != 0) {
        return rc;
    }

    unsigned int *device_histogram = nullptr;
    double *device_entropy = nullptr;

    cudaError_t err = cudaMalloc(reinterpret_cast<void **>(&device_histogram), sizeof(unsigned int) * 256);
    if (err != cudaSuccess) {
        return finish_cuda_call("cudaMalloc(entropy histogram)", err);
    }

    err = cudaMalloc(reinterpret_cast<void **>(&device_entropy), sizeof(double));
    if (err != cudaSuccess) {
        cudaFree(device_histogram);
        return finish_cuda_call("cudaMalloc(entropy output)", err);
    }

    err = cudaMemcpy(device_histogram, host_histogram, sizeof(unsigned int) * 256, cudaMemcpyHostToDevice);
    if (err != cudaSuccess) {
        cudaFree(device_entropy);
        cudaFree(device_histogram);
        return finish_cuda_call("cudaMemcpy(entropy histogram)", err);
    }

    entropy_kernel<<<1, 256>>>(device_histogram, size, device_entropy);

    err = cudaGetLastError();
    if (err != cudaSuccess) {
        cudaFree(device_entropy);
        cudaFree(device_histogram);
        return finish_cuda_call("entropy_kernel", err);
    }

    err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {
        cudaFree(device_entropy);
        cudaFree(device_histogram);
        return finish_cuda_call("cudaDeviceSynchronize(entropy)", err);
    }

    err = cudaMemcpy(entropy_out, device_entropy, sizeof(double), cudaMemcpyDeviceToHost);
    cudaFree(device_entropy);
    cudaFree(device_histogram);
    return finish_cuda_call("cudaMemcpy(entropy)", err);
}

int aura_cuda_rolling_hash3_u8(
    const unsigned char *data,
    size_t size,
    unsigned int *hashes_out) {
    return compute_rolling_hash3_device(data, size, hashes_out);
}

int aura_cuda_lz_match_candidates_u8(
    const unsigned char *data,
    size_t size,
    unsigned int window_size,
    unsigned int min_match,
    unsigned int max_match,
    unsigned int *distances_out,
    unsigned char *lengths_out) {
    return compute_lz_match_candidates_device(
        data,
        size,
        window_size,
        min_match,
        max_match,
        distances_out,
        lengths_out);
}

}  // extern "C"
