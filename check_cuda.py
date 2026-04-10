import torch
import onnxruntime as ort
import sys

def main():
    print(f"Python: {sys.version}")
    print(f"Torch Version: {torch.__version__}")
    
    cuda_available = torch.cuda.is_available()
    print(f"Torch CUDA Available: {cuda_available}")
    if cuda_available:
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    print(f"ONNX Runtime Providers: {ort.get_available_providers()}")
    if 'CUDAExecutionProvider' in ort.get_available_providers():
        print("ONNX Runtime: CUDA Acceleration Ready")
    else:
        print("ONNX Runtime: CPU Only (Warning: Latency will be higher)")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
