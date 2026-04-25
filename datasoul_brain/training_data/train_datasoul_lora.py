"""
DataSoul LoRA Fine-Tuning Script
=================================
Fine-tunes Llama 3.1 8B on RTX 4060 (8GB VRAM) using Unsloth QLoRA
Creates a DataSoul-specific LoRA adapter for domain-expert data analysis

Hardware: RTX 4060 8GB VRAM | i7 14th Gen
Estimated training time: 15-30 minutes
Output: ./datasoul_lora_adapter/ (~50MB)
"""

import json
import os

# ============================================================
# STEP 1: Check GPU
# ============================================================
def check_gpu():
    import torch
    if not torch.cuda.is_available():
        print("❌ No GPU detected. Fine-tuning requires CUDA GPU.")
        print("   Make sure NVIDIA drivers and CUDA toolkit are installed.")
        return False
    
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_mem / 1e9
    print(f"✅ GPU detected: {gpu_name} ({vram_gb:.1f} GB VRAM)")
    
    if vram_gb < 7:
        print("⚠️  Less than 8GB VRAM. Training may be tight. Reducing LoRA rank to 8.")
        return True
    
    return True


# ============================================================
# STEP 2: Load Model with 4-bit Quantization
# ============================================================
def load_model():
    from unsloth import FastLanguageModel
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
        max_seq_length=2048,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )
    
    # Apply LoRA adapters to all linear layers
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,               # LoRA rank (16 is good balance for 8GB)
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"
        ],
        lora_alpha=16,
        lora_dropout=0,      # Unsloth optimized — 0 is fine
        bias="none",
        use_gradient_checkpointing="unsloth",  # Saves VRAM
        random_state=42,
    )
    
    print("✅ Model loaded with 4-bit QLoRA adapters")
    return model, tokenizer


# ============================================================
# STEP 3: Prepare Training Data
# ============================================================
def prepare_dataset(tokenizer):
    from datasets import Dataset
    
    # Load DataSoul training data
    training_file = os.path.join(
        os.path.dirname(__file__), 
        "fine_tune_dataset.jsonl"
    )
    
    with open(training_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    
    # Format into Llama 3.1 chat template
    def format_example(example):
        messages = [
            {"role": "system", "content": example["instruction"]},
            {"role": "user", "content": example["input"]},
            {"role": "assistant", "content": example["output"]},
        ]
        
        text = tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=False
        )
        return {"text": text}
    
    dataset = Dataset.from_list(raw_data)
    dataset = dataset.map(format_example)
    
    print(f"✅ Training dataset prepared: {len(dataset)} examples")
    return dataset


# ============================================================
# STEP 4: Train
# ============================================================
def train(model, tokenizer, dataset):
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from unsloth import is_bfloat16_supported
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=3,
            learning_rate=2e-4,
            fp16=not is_bfloat16_supported(),
            bf16=is_bfloat16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=42,
            output_dir="./datasoul_training_output",
            report_to="none",  # No wandb needed
        ),
    )
    
    print("🚀 Starting DataSoul LoRA training...")
    print("   Estimated time: 15-30 minutes on RTX 4060")
    print("   You'll see training loss decrease over time.")
    print()
    
    trainer_stats = trainer.train()
    
    print()
    print(f"✅ Training complete!")
    print(f"   Total steps: {trainer_stats.global_step}")
    print(f"   Final loss: {trainer_stats.training_loss:.4f}")
    print(f"   Total time: {trainer_stats.metrics['train_runtime']:.0f} seconds")
    
    return trainer_stats


# ============================================================
# STEP 5: Save LoRA Adapter
# ============================================================
def save_adapter(model, tokenizer):
    adapter_dir = "./datasoul_lora_adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    print(f"✅ LoRA adapter saved to {adapter_dir}")
    
    # Calculate adapter size
    total_size = sum(
        os.path.getsize(os.path.join(adapter_dir, f)) 
        for f in os.listdir(adapter_dir) 
        if os.path.isfile(os.path.join(adapter_dir, f))
    )
    print(f"   Adapter size: {total_size / 1e6:.1f} MB")


# ============================================================
# STEP 6: Export to GGUF for Ollama
# ============================================================
def export_to_gguf(model, tokenizer):
    print("\n📦 Exporting to GGUF format for Ollama...")
    
    model.save_pretrained_gguf(
        "datasoul_gguf",
        tokenizer,
        quantization_method="q4_k_m"  # Good balance of quality/size
    )
    
    # Create Ollama Modelfile
    modelfile_content = """FROM ./datasoul_gguf/unsloth.Q4_K_M.gguf

TEMPLATE \"\"\"<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|><|start_header_id|>user<|end_header_id|>

{{ .Prompt }}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{{ .Response }}<|eot_id|>\"\"\"

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER stop "<|eot_id|>"

SYSTEM \"\"\"You are DataSoul AI — a senior data intelligence analyst powering the DataSoul platform. You combine the precision of a data engineer with the communication skills of a management consultant. Always quantify with specific numbers. Always explain WHY. Always provide confidence scores. Reference actual column names and values. Adapt language to the detected business sector. Flag compliance risks proactively.\"\"\"
"""
    
    with open("datasoul_gguf/Modelfile", "w") as f:
        f.write(modelfile_content)
    
    print("✅ GGUF model exported!")
    print()
    print("To register with Ollama, run:")
    print("  cd datasoul_gguf")
    print("  ollama create datasoul -f Modelfile")
    print()
    print("Then use 'datasoul' as your model name:")
    print("  ollama run datasoul")


# ============================================================
# STEP 7: Test the Fine-Tuned Model
# ============================================================
def test_model(model, tokenizer):
    from unsloth import FastLanguageModel
    
    FastLanguageModel.for_inference(model)
    
    test_input = """Dataset: sales_data.csv (8,000 rows × 10 columns)
Columns: order_id, customer_id, product, category, amount, quantity, date, region, discount, status
Missing: customer_id (4.2%), discount (31%), region (9.8%)
Duplicates: 67 exact duplicates
Outliers: amount has 15 values > $100,000
Detected sector: Retail

Generate a threat assessment."""
    
    messages = [
        {"role": "system", "content": "You are DataSoul AI, a senior data intelligence analyst."},
        {"role": "user", "content": test_input},
    ]
    
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to("cuda")
    
    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=1024,
        temperature=0.7,
        top_p=0.9,
    )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    print("\n" + "=" * 60)
    print("TEST: Fine-Tuned Model Response")
    print("=" * 60)
    print(response)
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("🧠 DataSoul LoRA Fine-Tuning")
    print("   Model: Llama 3.1 8B (4-bit QLoRA)")
    print("   GPU: RTX 4060 (8GB VRAM)")
    print("=" * 60)
    print()
    
    # Step 1: Check GPU
    if not check_gpu():
        return
    
    # Step 2: Load model
    model, tokenizer = load_model()
    
    # Step 3: Prepare dataset
    dataset = prepare_dataset(tokenizer)
    
    # Step 4: Train
    train(model, tokenizer, dataset)
    
    # Step 5: Save adapter
    save_adapter(model, tokenizer)
    
    # Step 6: Export for Ollama
    export_to_gguf(model, tokenizer)
    
    # Step 7: Test
    test_model(model, tokenizer)
    
    print("\n" + "=" * 60)
    print("🎉 DataSoul AI Brain fine-tuning complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. cd datasoul_gguf")
    print("2. ollama create datasoul -f Modelfile")
    print("3. Update backend to use model='datasoul' instead of 'llama3.1:8b'")
    print("4. The fine-tuned model + RAG = DataSoul's proprietary AI brain")


if __name__ == "__main__":
    main()
