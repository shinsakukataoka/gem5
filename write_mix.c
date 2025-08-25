#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HOT_BYTES    (64 * 1024)        // 64 KiB fits in L2
#define STREAM_BYTES (16 * 1024 * 1024) // 16 MiB, will thrash L2
#define HOT_REPEATS  200                // make hot bursts very writey
#define OUTER_ITERS  4                  // A-B-A-B... a few times

static inline void clobber(uint8_t *p, size_t n, uint8_t v) {
    for (size_t i = 0; i < n; i += 64) p[i] = v;   // one write per cache line
}

int main() {
    uint8_t *hot, *stream;
    posix_memalign((void**)&hot,    64, HOT_BYTES);
    posix_memalign((void**)&stream, 64, STREAM_BYTES);
    memset(hot, 0, HOT_BYTES); memset(stream, 0, STREAM_BYTES);

    for (int it = 0; it < OUTER_ITERS; ++it) {
        // Phase A: repeat writes to the same hot region (low entropy)
        for (int r = 0; r < HOT_REPEATS; ++r) clobber(hot, HOT_BYTES, (uint8_t)(it + r));

        // Phase B: write a big streaming region once (high entropy)
        clobber(stream, STREAM_BYTES, (uint8_t)it);
    }

    // keep the compiler honest
    size_t sum = 0;
    for (size_t i = 0; i < HOT_BYTES; i += 4096) sum += hot[i];
    printf("%zu\n", sum);
    return 0;
}

