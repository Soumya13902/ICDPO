import sys
sys.path.append("..")
from utils.utils import load_raw_dataset, save_dataset, early_truncation
Motive of this file: 

def parse(line):
    #parses a line to get prompt, pos repsonse, negative response and other info pair
    #So the data is in the form of prompt, pos data, negative data
    p = line["prefix"][0]
    rs = line["suffix"]

    p = "".join(p[:-1])
    p = p.replace("<|prompter|>", "\n\nHuman: ").replace("<|assistant|>", "\n\nAssistant: ")
    
    return {
        "prompt": p.rstrip(),
        "pos_response": rs[0].strip(),
        "neg_response": rs[-1].strip(),
        "meta": line["meta"],
    }

def retrieval(
    train_path,
    test_path,
    retrieval_func,
    num_demonstrations,
): 
    #fetches demonstrations for the icl 
    trainset = load_raw_dataset(train_path)
    testset = load_raw_dataset(test_path)
    parsed_testset = [parse(line) for line in testset]
    
    demos = retrieval_func(
        trainset,
        num_demonstrations,
        parsed_testset,
    )

    parsed_testset_with_demos = []
    for sample, demo in zip(testset, demos):
        sample["demos"] = demo
        parsed_testset_with_demos.append(sample)

    return parsed_testset_with_demos

def get_icl_context(
    sample,
    num_demonstrations,
    favor,
):
    if favor == "pos":
        instruction = "#You are asked to generate a response for each given dialogue context. The last response is generated by you, which should be as **polite/harmless/helpful/honest** as possible:"
    elif favor == "neg":
        instruction = "#You are asked to generate a response for each given dialogue context. The last response is generated by you, which should be as **offensive/harmful/helpless/misleading** as possible:"
    else:
        raise NotImplementedError
    
    context = instruction
    demos = sample["demos"][0:num_demonstrations]
    demos = demos[::-1]
    for index in range(num_demonstrations):
        if favor == "pos":
            context += "\n\n##" + demos[index]["prompt"] + "\n###Generate a **polite/harmless/helpful/honest** response: " + demos[index]["pos_response"]
        elif favor == "neg":
            context += "\n\n##" + demos[index]["prompt"] + "\n###Generate an **offensive/harmful/helpless/misleading** response: " + demos[index]["neg_response"]
        else:
            raise NotImplementedError

    sample = parse(sample)
    if favor == "pos":
        new_prompt = "\n\n##" + sample["prompt"] + "\n###Generate a **polite/harmless/helpful/honest** response:"
    elif favor == "neg":
        new_prompt = "\n\n##" + sample["prompt"] + "\n###Generate an **offensive/harmful/helpless/misleading** response:"
    else:
        raise NotImplementedError
    
    context += new_prompt

    return context

def get_base_context(
    sample,
):
    sample = parse(sample)
    context = sample["prompt"] + "\n\nAssistant:"

    return context

def get_raw_text(
    sample,
):
    return sample["prefix"][0]

def postpreprocess(
    text,
    do_early_truncation = True,
):
    if do_early_truncation:
        text = early_truncation(
            text = text,
            stop_sequences = ["##", "Human:", "human:", "Assistant:", "assistant:"]
        ).strip()
    return text.strip()

if __name__ == "__main__":
    retriever = "random" # "bm25", "sbert"
    demoset = "hh" # "hh_llama_chat"

    if retriever == "random":
        from retriever.randomly import random_retrieval
        for meta_key in [
            "harmless_base",
            "helpful_base",
        ]:
            parsed_testset_with_demos = retrieval(
                train_path = f"../data/demos/{demoset}/{meta_key}/train.json",
                test_path = f"../data/hh_test/{meta_key}.json",
                retrieval_func = random_retrieval,
                num_demonstrations = 3,
            )

            save_dataset(
                parsed_testset_with_demos, 
                f"../data/{demoset}_test_random_demos/{meta_key}.json"
            )
    elif retriever == "bm25":
        from retriever.bm25 import bm25_retrieval
        for meta_key in [
            "harmless_base",
            "helpful_base",
        ]:
            parsed_testset_with_demos = retrieval(
                train_path = f"../data/demos/{demoset}/{meta_key}/train.json",
                test_path = f"../data/hh_test/{meta_key}.json",
                retrieval_func = bm25_retrieval,
                num_demonstrations = 20,
            )

            save_dataset(
                parsed_testset_with_demos, 
                f"../data/{demoset}_test_bm25_demos/{meta_key}.json"
            )
    elif retriever == "sbert":
        from retriever.sbert import sbert_retrieval, sbert_retrieval_with_bm25_res
        for meta_key in [
            "harmless_base",
            "helpful_base",
        ]:
            bm25_testset = load_raw_dataset(f"../data/{demoset}_test_bm25_demos/{meta_key}.json")
            demos = [sample["demos"] for sample in bm25_testset]
            parsed_testset = [parse(sample) for sample in bm25_testset]
            
            new_demos, sorted_indices = sbert_retrieval_with_bm25_res(
                demos,
                3,
                parsed_testset,
            )
            sbert_testset = bm25_testset
            for index, sample in enumerate(sbert_testset):
                sample["demos"] = new_demos[index]
                sample["resorted_indices"] = [int(i) for i in sorted_indices[index]]
            
            save_dataset(
                sbert_testset, 
                f"../data/{demoset}_test_sbert_demos/{meta_key}.json"
            )
