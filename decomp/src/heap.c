#include <heap.h>
#include <extern.h>

static inline HeapBlock* Heap_AdvanceWords(HeapBlock* block, u16 words)
{
    return (HeapBlock*)(((u16*)block) + words);
}

static inline HeapBlock* Heap_NextBlock(HeapBlock* block)
{
    return Heap_AdvanceWords(block, block->header.sizeWords);
}

HeapBlock* Heap_Alloc(u16 words, void** owner)
{
    const u16 headerWords = (sizeof(BlockHeader) / WORD_SIZE);
    const u16 totalWords = ((words + 1) & 0xFFFE) + headerWords;
    const HeapBlock* heapEnd = (HeapBlock*)(((u16*)(&g_heapStart)) + HEAP_SIZE);
    HeapBlock* currBlock = &g_heapStart;
    HeapBlock* chosenBlock = nullptr;

    while (currBlock < heapEnd)
    {
        if ((!currBlock->header.isInUse) && (totalWords <= currBlock->header.sizeWords))
        {
            chosenBlock = currBlock;
            break;
        }
        currBlock = Heap_NextBlock(currBlock);
    }

    if (chosenBlock == nullptr)
    {
        chosenBlock = Heap_MergeFreeBlocks(totalWords);
        if (chosenBlock == nullptr)
        {
            *owner = nullptr;
            return chosenBlock;
        }
    }

    if ((totalWords + headerWords) <= chosenBlock->header.sizeWords)
    {
        HeapBlock* tail = Heap_AdvanceWords(chosenBlock, totalWords);
        tail->header.isInUse = false;
        tail->header.sizeWords = chosenBlock->header.sizeWords - totalWords;
        chosenBlock->header.sizeWords = totalWords;
    }

    chosenBlock->header.isInUse = true;
    chosenBlock->header.owner = owner;
    *owner = chosenBlock->payload;
    memset(chosenBlock->payload, 0, (chosenBlock->header.sizeWords - headerWords) * WORD_SIZE);
    return chosenBlock;
}