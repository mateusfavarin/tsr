#pragma once

#include "types.h"

#define HEAP_SIZE 14000
#define WORD_SIZE (sizeof(u16))

typedef struct BlockHeader
{
    u16 isInUse;
    u16 sizeWords; // 1 word = 2 bytes
    void** owner;
} BlockHeader;

typedef struct HeapBlock
{
    BlockHeader header;
    u16 payload[];
} HeapBlock;

HeapBlock* Heap_Alloc(u16 words, void** owner);
HeapBlock* Heap_MergeFreeBlocks(u16 words);

extern HeapBlock g_heapStart;