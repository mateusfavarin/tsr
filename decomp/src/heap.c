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

HeapBlock* Heap_MergeFreeBlocks(u16 words)
{
    HeapBlock* previousBlock = nullptr;
    HeapBlock* currentBlock = &g_heapStart;
    const HeapBlock* const heapEnd = (HeapBlock*)(((u16*)(&g_heapStart)) + HEAP_SIZE);
    bool trackingFreeRun = false;

    for (; currentBlock < heapEnd; currentBlock = Heap_NextBlock(currentBlock))
    {
        if (!trackingFreeRun)
        {
            previousBlock = currentBlock;
            if (!currentBlock->header.isInUse) { trackingFreeRun = true; }
            continue;
        }

        if (!currentBlock->header.isInUse)
        {
            const u16 mergedWords = previousBlock->header.sizeWords + currentBlock->header.sizeWords;
            previousBlock->header.sizeWords = mergedWords;
            if (words <= mergedWords) { return previousBlock; }
            continue;
        }

        if (currentBlock->header.isInUse)
        {
            const u16 oldFreeWords = previousBlock->header.sizeWords;
            const u16 movedBlockWords = currentBlock->header.sizeWords;
            const s32 movedCopyWordCount = (s32) movedBlockWords - ((sizeof(currentBlock->header.isInUse) + sizeof(currentBlock->header.sizeWords)) / WORD_SIZE);
            const s32 movedCopyDwordCount = movedCopyWordCount / (sizeof(u32) / WORD_SIZE);
            const s32* source = (const s32*) &currentBlock->header.owner;
            s32* destination = (s32*) &previousBlock->header.owner;

            previousBlock->header.sizeWords = movedBlockWords;
            if (movedCopyDwordCount > 0)
            {
                for (s32 i = 0; i < movedCopyDwordCount; i++)
                {
                    destination[i] = source[i];
                }
            }

            *previousBlock->header.owner = previousBlock->payload;
            previousBlock->header.isInUse = true;

            HeapBlock* const trailingFreeBlock = Heap_AdvanceWords(previousBlock, movedBlockWords);
            trailingFreeBlock->header.isInUse = false;
            trailingFreeBlock->header.sizeWords = oldFreeWords;

            if (words == 0) { return nullptr; }

            trackingFreeRun = false;
            currentBlock = previousBlock;
        }
    }

    return nullptr;
}

HeapBlock* Heap_Alloc(u16 words, void** owner)
{
    const u16 headerWords = (sizeof(BlockHeader) / WORD_SIZE);
    const u16 totalWords = ((words + 1) & 0xFFFE) + headerWords;
    const HeapBlock* const heapEnd = (HeapBlock*)(((u16*)(&g_heapStart)) + HEAP_SIZE);
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
